# warm-pool-controller

A Kubernetes controller that keeps a pool of warm worker Pods and hands one to
each incoming claim.

Starting a sandbox cold means scheduling a Pod, pulling an image and waiting for
health checks. A **WorkerPool** keeps `spec.replicas` Pods booted, Ready and
unassigned. A **WorkerClaim** asks for one of them. The controller assigns
each claim exactly one Ready Pod, refills the pool, and recovers when Pods die,
claims are deleted or the controller itself restarts.

The controller keeps no state of its own. Every assignment is a label on the
Pod, written with a single conditional update. After a restart the controller
re-lists Pods and claims and rebuilds every status from those labels.

Built with Go, Kubebuilder v4.16 and controller-runtime v0.25.

---

## Quick start

Requires Go 1.26+, Docker, [kind](https://kind.sigs.k8s.io/) and kubectl.

```sh
kind create cluster --name warm-pool
make install        # register the two CRDs
make run            # run the controller on your machine against the kind cluster
```

In another terminal:

```sh
kubectl apply -f config/samples/workerpool.yaml    # 3 warm nginx Pods
kubectl get workerpools -w                         # WARM goes 0 -> 3
kubectl apply -f config/samples/workerclaim.yaml   # claim-a
kubectl get workerclaims -o yaml
kubectl get pods -L takehome.replit.com/claim      # one Pod labelled claim-a, 3 warm
kubectl apply -f config/samples/claims-x5.yaml     # five more claims, all different Pods
```

### Scripted demo

`hack/demo.sh` runs every behaviour the brief asks to demonstrate against the
current cluster and checks the invariants after each step (needs only kubectl):

```sh
hack/demo.sh                 # pool of 3, one claim, refill, 5 claims, Pod loss, claim deletion
# Ctrl-C the controller, then:
hack/demo.sh while-down      # wipe a status, delete a bound Pod, delete a claim, add a claim
make run                     # start it again, then in the other terminal:
hack/demo.sh after-restart   # all rebuilt; nothing lost, nothing duplicated
```

[docs/demo-transcript.md](docs/demo-transcript.md) is the output of a real run
on kind (Kubernetes 1.34).

### Running in the cluster

`make docker-build IMG=warm-pool-controller:dev`, `kind load docker-image
warm-pool-controller:dev --name warm-pool`, then `make deploy
IMG=warm-pool-controller:dev`. The Deployment runs with leader election on.
The demo above also passes with the controller deployed this way (restart =
scale the Deployment to 0 and back to 1).

**Run one controller at a time**: `make run` *or* the Deployment, not both. Two
active controllers keep I1 and I5, but can briefly assign two Pods to one claim
(see the failure matrix).

---

## API

```yaml
apiVersion: takehome.replit.com/v1alpha1
kind: WorkerPool
metadata:
  name: default
spec:
  replicas: 3          # ready, unclaimed Pods to keep (claimed Pods do not count)
  template:            # a normal PodTemplateSpec
    spec:
      containers:
        - name: worker
          image: nginx:alpine
          readinessProbe: {httpGet: {path: /, port: 80}, periodSeconds: 1}
status:
  replicas: 4          # live Pods: warm + starting + claimed
  readyReplicas: 4     # live Pods that are Ready, claimed or not
  availableReplicas: 3 # warm = Ready and unclaimed; driven toward spec.replicas
  claimedReplicas: 1
  pendingReplicas: 0   # unclaimed, not Ready yet
  observedGeneration: 1
---
apiVersion: takehome.replit.com/v1alpha1
kind: WorkerClaim
metadata:
  name: claim-a
spec:
  poolName: default    # same namespace; immutable
status:
  phase: Claimed       # Pending | Claimed
  podName: default-6zztv
  podIP: 10.244.0.10
  reason: Assigned     # Assigned | NoWarmPodsAvailable | PoolNotFound | AssignedPodLost
  message: Assigned Pod default-6zztv from pool default
  assignedAt: "2026-10-07T05:03:36Z"
  attempts: 1          # Pods assigned over the claim's life; >1 means earlier Pods were lost
```

```
$ kubectl get workerpools
NAME      DESIRED   WARM   PENDING   CLAIMED   TOTAL   AGE
default   3         3      0         5         8       15s
$ kubectl get workerclaims
NAME      POOL      PHASE     POD             IP            REASON     AGE
claim-1   default   Claimed   default-75f9l   10.244.0.9    Assigned   9s
```

Validation: `replicas >= 0`; `poolName` is required and immutable; pool and
claim names are at most 63 characters, because they become label values.
Labels and annotations under `takehome.replit.com/` in a pool template are
dropped, so a template cannot create a Pod that looks already claimed.

**Consumers must treat `status.podName` and `status.podIP` as mutable.** If the
Pod is lost, the claim goes back to `Pending` and later gets a different Pod.

**Release behaviour: a claimed Pod is consumed, not returned.** Deleting a
claim deletes its Pod, and the pool refills with a fresh one. A used sandbox is
dirty; replacing it is cheaper than trusting a cleanup.

---

## How it works

### The Pod is the source of truth

Every Pod the pool creates is owned by the pool (`ownerReference`,
`controller: true`) and labelled. An assignment is three keys written in one
update:

```yaml
metadata:
  generateName: default-
  labels:
    takehome.replit.com/pool: default        # set at creation
    takehome.replit.com/claim: claim-a       # added on assignment, for humans and event routing
    takehome.replit.com/claim-uid: 3f1c...   # added on assignment, the authoritative key
  annotations:
    takehome.replit.com/claimed-at: "2026-10-07T05:03:36Z"
  ownerReferences: [{kind: WorkerPool, name: default, controller: true}]
```

The claim carries the finalizer `takehome.replit.com/release-pod`.
`claim.status` is a projection of these labels, never the other way round.

The UID label is the key because names get reused and UIDs do not. If
`claim-a` is deleted and recreated, the new claim must not inherit the old Pod.

### Invariants

| # | Invariant | Enforced by |
|---|---|---|
| I1 | A Pod is assigned to at most one claim | The assignment is an `Update` that carries the Pod's `resourceVersion`. If another claim labelled the Pod first, the API server rejects the loser with 409. A label key holds one value. |
| I2 | A claim is assigned at most one Pod | Before binding, the claim lists Pods labelled with its UID **from the API server, not the cache**, and binds only if there are none. controller-runtime never reconciles the same claim concurrently. A sweep keeps one Pod and deletes the rest if more than one is ever found. |
| I3 | `availableReplicas` = owned Pods that are Running, Ready, unclaimed and not terminating | Recomputed from a fresh list on every reconcile; never kept in memory. |
| I4 | Every claimed Pod's claim exists (same UID) | The claim's finalizer deletes its Pod. The pool deletes claimed Pods whose claim is gone, which covers a finalizer removed by hand. |
| I5 | Scaling never touches claimed Pods | Scale-down candidates are unclaimed Pods only, and each delete carries `resourceVersion` and UID preconditions. If a claim takes the Pod in between, the delete fails with 409 and the Pod survives. |

### WorkerPool reconciler

```
pods := LIST Pods labelled pool=<name> from the API server; keep those controlled by this pool (owner UID)
for each Pod with a claim-uid label:
    claim := GET claim named on the Pod from the API server
    missing, or UID differs → delete the Pod (orphan, I4)
delete Failed/Succeeded unclaimed Pods
delta := spec.replicas − (warm + starting)        # starting Pods count toward the target
delta > 0 → create delta Pods from the template
delta < 0 → delete −delta unclaimed Pods, not-Ready first then youngest,
            each with preconditions {uid, resourceVersion}   (I5)
status := counts from the list; write only if it changed
```

There are two different counts here. Not-Ready Pods are excluded from
`availableReplicas`, as the brief requires, but included in the scaling
arithmetic. Otherwise the loop would keep creating Pods for as long as the
first batch takes to boot.

The list is read from the API server rather than the cache. With a cached
list, the reconcile triggered by the first Pod's create event can run before
the other Pods are in the cache and create them again. ReplicaSet solves this
with "expectations". An uncached list is the simplest correct answer at this
size (see tradeoffs).

Watches: the pool itself (spec changes only, so its own status writes do not
retrigger it), its Pods (`Owns`), and claim deletions (to sweep orphans
promptly).

### WorkerClaim reconciler

```
if deleting: delete Pods labelled claim-uid=<uid> (API server list); remove finalizer; done
ensure the finalizer is present (its own write, before any binding)

bound := LIST Pods labelled claim-uid=<uid> from the API server   # 1. observe, do not assume
    terminating → ignore; Failed/Succeeded → delete; the rest are live
live ≥ 1 → keep the one status reports (else earliest claimed-at), delete extras (I2),
           status Claimed; done
status.podName set but no live Pod → the Pod was lost: event AssignedPodLost

pool missing → Pending / PoolNotFound, retry in 10s                # 2. bind
for pod in warm Pods of the pool (from the cache), longest-Ready first:
    add labels claim, claim-uid and annotation claimed-at; Update (carries resourceVersion)
    ok       → status Claimed (attempts++ if the Pod changed), event Assigned; done
    409/404  → someone else won this Pod, or the cache was stale: try the next one
lost every race → retry in 200ms
no candidates   → Pending / AssignedPodLost if attempts > 0, else NoWarmPodsAvailable; retry in 5s
```

**Why `Update` and not a merge patch.** A merge patch without a precondition is
last-writer-wins. Two reconcilers could both "succeed" on the same Pod, and the
second would silently overwrite the first's label. The Pod object is the lock
and the API server is the arbiter.

**Why the observe step reads from the API server.** After binding Pod A, the
claim's own status write triggers another reconcile. That event can arrive
before the cache has seen Pod A's new label. A cached lookup would find no Pod
and bind Pod B; the conditional write would not stop it, because Pod B is
untouched. `TestClaimDoesNotBindTwiceOnStaleCache` reproduces this, and it fails
if the reconciler reads its own Pods from the cache. Candidates *can* come from
the cache: a stale candidate costs at most a 409.

**Crash between the label write and the status write** is harmless. The next
reconcile finds the Pod by its UID label and fills in the status. No second Pod
is bound.

Watches: claims, and Pods. A claimed Pod's events go to its claim (that is how a
deleted or failed Pod is noticed). An unclaimed Pod that becomes warm wakes
every waiting claim of its pool. Claims are reconciled 4 at a time
(`--claim-workers`), so different claims really do race for the same Pod. The
conditional write keeps that safe, and the tests run with 10.

The Pod informer only caches Pods with the `takehome.replit.com/pool` label.

### Failure and restart matrix

| Scenario | What the server holds | Recovery | Covered by |
|---|---|---|---|
| Crash after a Pod is labelled, before the claim's status is written | Pod has claim-uid; claim status empty | Observe step finds the Pod; status filled in; no second Pod | envtest restart spec |
| Cache has not seen the claim's own label yet | Stale cache | Observe step reads the API server | unit test |
| Two claims race for one Pod | — | Second `Update` gets 409, tries the next Pod or waits | envtest: 20 claims, 3 Pods, 10 workers |
| Scale-down races with a bind | — | Delete precondition fails with 409; the claimed Pod survives | design (I5) |
| Bound Pod deleted, Failed, or stuck Terminating | Pod gone, terminal, or has deletionTimestamp | Claim emits `AssignedPodLost`, increments `attempts`, binds another Pod; the pool refills | envtest + kind |
| Claim deleted while the controller is down | Claim Terminating with finalizer | Finalizer path runs on restart and deletes the Pod | envtest restart + kind |
| Finalizer removed by hand (claim may even be recreated with the same name) | Pod labelled with a UID that no longer exists | Pool deletes the orphan; the new claim gets a different Pod | envtest |
| Claim status wiped | Pod labels intact | Status rebuilt onto the same Pod | envtest restart + kind |
| Pool deleted | Garbage collector removes its Pods | Claims go `Pending / PoolNotFound`; recreating the pool re-assigns them | kind |
| `spec.replicas` lowered | — | Unclaimed surplus deleted; claimed Pods untouched | envtest |
| Two controllers active at once (e.g. `make run` while the Deployment runs) | — | I1 and I5 still hold: they are single-object conditional writes. **I2 can break briefly**: each process can bind a different Pod to the same claim. The next reconcile keeps the Pod the status reports and deletes the other (`DuplicateAssignment` Event). The pools also over-create, then scale the surplus down. This happened twice in testing, while a stray `make run` process was still running after `make deploy`. Each time the two binds landed within 50 ms of each other, and the extra Pod was deleted within 50 ms. Making I2 strict across processes would need a cross-object protocol, because Kubernetes has no multi-object transactions. Leader election is the standard guard, and the Deployment enables it | observed on kind |
| A claimed Pod's readiness probe starts failing | Pod Running, not Ready | Claim stays `Claimed`: `Claimed` means assigned, not "Ready right now" | design choice |

---

## Tests

```sh
make test     # unit tests + envtest (real kube-apiserver and etcd)
```

**Unit tests** (`pods_test.go`): Pod classification, grouping (ownership
filter, terminal claimed Pods left to the claim), scaling arithmetic, scale-down
order (never a claimed Pod), bind-candidate order, which Pod a claim keeps, and
template sanitising. `stale_cache_test.go` covers the stale-cache double bind
described above.

**envtest specs** (16, `internal/controller/*_test.go`). envtest has no kubelet,
scheduler, garbage collector or namespace controller, so the tests play the
kubelet. They set Pod phase, Ready and IP themselves, which doubles as failure
injection. Each test uses its own namespace and its own manager, wired by the
same `SetupWithManager` as `main.go`.

- A pool of 3 creates exactly 3 Pods, and no 4th while they boot.
- Terminating, Failed, Succeeded, not-Ready and foreign Pods are never counted
  as warm.
- Scale-down removes only unclaimed Pods.
- One claim gets exactly one Pod, and the pool refills.
- 20 claims against 3 Pods with 10 concurrent workers: 3 assigned on distinct
  Pods, 17 Pending, then all 20 assigned as Pods boot. The invariants are
  checked continuously, not just at the end.
- `PoolNotFound` until the pool exists.
- Deleted, Terminating and Failed bound Pods are re-assigned; `attempts` counts
  them.
- Deleting a claim deletes its Pod.
- Restart: while the controller is down, a status is wiped, a bound Pod
  deleted, a claim deleted, a claim created, and a bind is left half-finished.
  Everything is rebuilt with no duplicates.
- Finalizer removed by hand plus the name reused: the orphan is deleted.
- Churn: random claim and Pod deletions for 8 seconds at 10 workers, invariants
  checked after every operation.
- API validation: negative replicas, long names, immutable `poolName`.

The invariant checker (`checkInvariants`) reads claims before Pods. A claim only
reports a Pod after the Pod's label is written, so a later read of that Pod is
guaranteed to see the label.

The suite runs in about 50 seconds. It passed 8 consecutive runs with `-race`.
Ginkgo cannot rerun a suite in one process, so repeat with a shell loop rather
than `-count`. `make lint` (golangci-lint) is clean.

**On kind**, `hack/demo.sh` is the behavioural end-to-end check (see the
transcript). `make test-e2e` is Kubebuilder's scaffolded smoke test (deploy the
image, check the metrics endpoint); I left it as generated and did not run it.

---

## Design decisions and tradeoffs

| Decision | Why | Cost | At scale I would |
|---|---|---|---|
| Pod labels are the source of truth; claim status is derived | The Pod is the contended resource; one conditional write on it is atomic. Making status authoritative would need a two-phase commit across two objects | Status can lag the labels briefly | Keep it |
| Pool lists its Pods from the API server | Rules out over-creation from cache lag, simply | One LIST per pool reconcile | ReplicaSet-style expectations, then switch back to the cache |
| Claim lists *its own* Pods from the API server; candidates from the cache | Closes the stale-cache double bind (I2); candidates are safe because the bind is conditional | One label-selected LIST per claim reconcile | Remember recent binds in memory with a TTL, falling back to an uncached GET of `status.podName` |
| Bind with `Update` (optimistic concurrency) | A merge patch is last-writer-wins | Conflicts under contention, handled by trying the next Pod | Spread claims across candidates (e.g. hash of claim UID) to reduce 409s |
| Two phases; a lost Pod always re-queues the claim | Simplest behaviour that satisfies "eligible for another assignment" | No terminal Failed state; `podName` is mutable | `spec.onPodLost: Fail` plus `maxAttempts` |
| Claimed Pods are consumed; claim deletion deletes the Pod | A used sandbox is dirty | One Pod per claim lifetime | Optional `releasePolicy` for trusted workloads |
| Finalizer instead of moving the ownerReference to the claim | One mental model: the pool owns all its Pods | A claim stays Terminating while the controller is down | Same, or ownership transfer if GC-only cleanup is preferred |
| Template edits apply only to new Pods | Out of scope for v1 | Old warm Pods keep the old template | Rolling updates (below) |
| Pool and claim in the same namespace; claims name one pool | Keeps RBAC and lookups simple | No cross-namespace pools | Pool selector (below) |
| No field indexer; a newly warm Pod wakes every waiting claim of its pool | Simple, and it exercises the 409 path | Thundering herd: N claims race for one Pod | Index claims by pool and wake the oldest few |
| `attempts` lives only in status | Informational in v1 | Resets if status is wiped | Make it durable on the claim if it ever gates behaviour |
| Pod informer restricted to pool-labelled Pods | Does not cache every Pod in the cluster | — | Keep it |

---

## Not built, and how I would build it

- **Claim-specific config.** Add `spec.config` to the claim. Write it as a Pod
  annotation in the same bind `Update`, and mount it with a Downward API volume
  in the template, so it appears at `/etc/worker/config` without a restart.
  Report a `ConfigDelivered` condition.
- **Rolling updates.** Put a `template-hash` label on Pods, as Deployment does.
  Treat stale-hash *unclaimed* Pods as surplus to replace, within `maxSurge`
  (extra creates) and `maxUnavailable` (deletes before replacements are
  Ready). Never touch claimed Pods; claims prefer current-hash Pods.
- **Metrics.** Gauges for warm, pending and claimed Pods per pool, plus queue
  depth. Counters for assignments, 409 conflicts and lost Pods. A histogram for
  claim-created-to-Claimed latency. Register them on controller-runtime's
  registry (the metrics endpoint is already scaffolded).
- **Conditions.** `metav1.Condition` arrays: `Ready`/`Progressing` on pools,
  `Assigned`/`PodReady` on claims, mirroring the Events.
- **Expectations.** A per-pool set of Pod names created but not yet seen in the
  cache, with a deadline. Skip scaling while it is non-empty. This lets the
  pool list from the cache.
- **Fail policy and attempt cap; FIFO fairness; pool selector; claim TTL.**
  `spec.onPodLost` with a terminal `Failed` phase. Bind only if no older
  pending claim exists for the pool. `spec.poolSelector` over pools with free
  capacity. `spec.ttlSecondsAfterClaimed` with a `RequeueAfter` at bind time.

---

## Repository layout

```
api/v1alpha1/            workerpool_types.go, workerclaim_types.go, labels.go (the Pod metadata contract)
internal/controller/     workerpool_controller.go, workerclaim_controller.go,
                         pods.go (classify, group, choose), setup.go (wiring shared with tests), *_test.go
cmd/main.go              manager entry point (--claim-workers, --leader-elect)
config/crd, rbac, manager, samples/{workerpool,workerclaim,claims-x5}.yaml
hack/demo.sh             scripted demo with invariant checks
docs/demo-transcript.md  output of the demo on kind
```

`make install` uses server-side apply. The WorkerPool CRD embeds a full
PodTemplateSpec schema (about 600 KB), which is over the 256 KB annotation limit
of client-side apply. CRDs are generated with `generateEmbeddedObjectMeta=true`;
without it the API server prunes `template.metadata.labels`.
