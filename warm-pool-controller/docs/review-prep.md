# Review prep: warm-pool-controller

Notes for the code review session. The code in this directory is the submission,
unchanged (byte-identical to the uploaded `warm-pool-controller_1.zip`). Nothing
below has been applied to it; the fixes in section 5 were tested on a scratch copy.

## 1. Verified state (2026-10-19)

| Check | Result |
|---|---|
| `go build ./...`, `go vet ./...`, `gofmt -l .` | Clean (Go 1.26.0) |
| Unit tests (8) + envtest suite (16 specs, kube-apiserver/etcd 1.37) | Pass, with `-race`. Suite ~50 s; first run ~3.5 min wall with compile |
| `make lint` (golangci-lint v2.13.1 + logcheck plugin) | 0 issues |
| `make manifests generate` | No diff: CRDs, RBAC and deepcopy match the source |
| `hack/demo.sh` on kind | **Not re-run.** The verification sandbox can't run containers inside a kind node. Last real run: [demo-transcript.md](demo-transcript.md), 2026-10-07, Kubernetes 1.34.11 |
| `make test-e2e` | Never run (Kubebuilder scaffold). The README says so |
| CI | **None runs.** The workflows live in `warm-pool-controller/.github/workflows/`, and GitHub only reads `.github/workflows/` at the repo root, so nothing checks PR #1 |

## 2. Before the call (15 minutes)

```sh
git clone https://github.com/areddy1213/gcp && cd gcp/warm-pool-controller
git checkout claude/kind-clarke-14a2ge   # PR #1's code plus these notes
go version                       # needs 1.26; with Go >= 1.21, GOTOOLCHAIN=auto fetches it
make setup-envtest && make test  # first run downloads tools; do it before the call
make lint

kind create cluster --name warm-pool
docker pull nginx:alpine && kind load docker-image nginx:alpine --name warm-pool  # no image pulls on screen
make install && make run         # terminal 1
hack/demo.sh                     # terminal 2
```

Run one controller at a time (`make run` *or* `make deploy`, never both). Two
active controllers can briefly bind two Pods to one claim (README failure matrix).

## 3. Five-minute walkthrough (presentation order)

1. **API.** `api/v1alpha1/workerpool_types.go`, `workerclaim_types.go`. "`spec.replicas`
   counts warm Pods only, so total Pods grow with claims. A claim names one pool,
   and `poolName` is immutable (CEL)."
2. **Source of truth.** `api/v1alpha1/labels.go`. "An assignment is a label on the Pod.
   The claim UID is the key, because names get reused. Status is a projection."
3. **The bind.** `internal/controller/workerclaim_controller.go:202`. "One `Update`
   carrying the Pod's `resourceVersion`. If two claims race, the API server gives the
   loser a 409. The Pod is the lock."
4. **Observe before bind.** `workerclaim_controller.go:99-133` and `:247`. "The claim
   looks for its own Pods on the API server, not the cache. Otherwise its own status
   write can retrigger it before the cache sees the label, and it binds a second Pod.
   `stale_cache_test.go` reproduces that."
5. **The pool loop.** `workerpool_controller.go:75-138`, `pods.go:150`. "Uncached
   list, starting Pods count toward the target so it doesn't over-create while Pods
   boot, scale-down only touches unclaimed Pods and carries UID + resourceVersion
   preconditions."
6. **Restart.** `restart_test.go`. "No in-memory state. Wipe a status, delete a bound
   Pod, delete a claim, leave a half-finished bind: a fresh process rebuilds it all."

## 4. Issues found reading the code

Ranked by what I'd most expect a reviewer to find. Raising the first two yourself
beats being asked.

### 4.1 A lost Pod keeps being reported while rebinding loses races (correctness)

`workerclaim_controller.go:135-185`. When the bound Pod is gone, the reconciler
emits `AssignedPodLost` and tries to bind. If every candidate returns 409, it returns
at line 183 **without writing status**. The claim still says `Claimed` with the dead
Pod's name and IP, and the event repeats on every 200 ms retry.

Reproduced with a fake-client test (Pod gone, the only candidate returns 409): after
reconcile, status is `Claimed / dead-pod / 10.0.0.99 / Assigned`.

Why it matters: races are most likely exactly when the pool is drained (see 4.3), and
the CNI can reuse a deleted Pod's IP for another Pod. For sandboxes that means a
consumer could connect to someone else's workload. Fix in 5.1.

### 4.2 Pool reconcile costs one uncached GET per claimed Pod (scale)

`workerpool_controller.go:84-97`, `:163`. The orphan check reads every claimed Pod's
claim from the API server, on every pool reconcile. `Owns(&corev1.Pod{})` (line 194)
triggers a reconcile on any change to any Pod in the pool, including claimed Pods'
status updates. With C claimed Pods, each event costs 1 LIST + C GETs, so the load grows
as C². Orphans only exist when someone removes a finalizer by hand, so this pays an
expensive check for a rare case. Fix in 5.2; also add a predicate on `Owns` that
ignores Pod updates which don't change phase, Ready, labels or `deletionTimestamp`.

### 4.3 Thundering herd, amplified (scale; README acknowledges the herd)

`podToClaims` (`workerclaim_controller.go:331`) wakes every pending claim of the pool
when a Pod is warm. controller-runtime's `EnqueueRequestsFromMapFunc` maps **both** the
old and new object on update, so the bind that takes the Pod (old object = warm)
wakes them all a second time. Every wake does an uncached LIST by `claim-uid`
(`boundPods`, line 247). Label selectors aren't indexed, so the API server filters every Pod
in the namespace for each call. Pending claims also requeue every 5 s (line 45).

With N pending claims: about 2N uncached LISTs per warm Pod, plus N/5 per second at
idle. Refilling N claims is O(N²).

Fix: wake only the oldest k pending claims (field index on `spec.poolName`, sort by
`creationTimestamp`). That also gives FIFO fairness, which the README lists as not
built. Replace the LIST with expectations: an in-memory map from claim UID to the Pod
it just bound, plus an uncached GET of `status.podName`. LIST only when both are
empty.

### 4.4 Pods that never become Ready wedge the pool (robustness)

`pods.go:150`. Starting Pods count toward the target indefinitely. Under
`ImagePullBackOff`, a crash-looping container or a readiness probe that never passes,
the pool shows N pending and 0 warm forever and never replaces them. Claims sit in
`NoWarmPodsAvailable`. ReplicaSet behaves the same, but a warm pool exists to supply
Ready capacity. Fix: `spec.startupTimeoutSeconds`. Delete starting Pods older than
it (count restarts too) and surface a `Progressing=False` condition.

### 4.5 Failover gap (availability)

`cmd/main.go:165-185`. Leader election uses the defaults (15 s lease), and
`LeaderElectionReleaseOnCancel` is commented out (line 184). A rolling update can
leave up to ~15 s with no assignments. Enabling it is safe here: the binary exits as soon
as the manager stops, which is the condition the scaffold comment names. The pool
controller also runs the default single worker for all pools.

### 4.6 Security and multi-tenancy (Replit will care)

- **WorkerPool create is equivalent to Pod create.** Anyone who can create a pool can run
  any PodSpec, as any ServiceAccount in the namespace. A Deployment has the same property.
  Grant `workerpools` RBAC as carefully as `pods`, and enforce Pod Security
  `restricted` or a ValidatingAdmissionPolicy on the template.
- **Cluster-wide Pod write access.** `config/rbac/role.yaml` +
  `role_binding.yaml` is a ClusterRole/ClusterRoleBinding with Pod
  create/update/delete everywhere. Narrow it to namespaced RoleBindings if pools
  live in known namespaces.
- **An assignment is just a label.** Anyone with `pods patch` in the namespace can remove
  `claim-uid` and turn a used Pod warm again, so another claim gets a dirty
  sandbox. Fix: a ValidatingAdmissionPolicy that allows only the controller's SA to change
  `takehome.replit.com/*` labels on Pods.
- **The sample template is not a sandbox.** It automounts the SA token, sets no
  `runtimeClassName` (gVisor/Kata) and has no NetworkPolicy. For untrusted code:
  `automountServiceAccountToken: false`, a sandboxed runtime, default-deny egress.

### 4.7 Deleting a pool kills in-use sandboxes (design)

Claimed Pods keep `controller: true` ownerReferences to the pool, so the garbage
collector deletes them with the pool. The README documents this ("Pool deleted"),
but be ready to defend it or offer the alternatives: transfer ownership to the claim
at bind time, or put a finalizer on the pool that waits for claims to drain.

### 4.8 Test gaps

- I5 (scale-down racing a bind) is "design" only. A deterministic test would use a
  fake client with an interceptor that labels the Pod between the list and the delete.
- Two active controllers: observed on kind, not tested.
- Pool deletion and GC: kind only (envtest has no garbage collector).
- `make test-e2e` never run; no CI (section 1).

## 5. Patches ready if asked (tested, not applied)

Both pass the full suite with `-race`. With 5.1, the 4.1 repro reports
`Pending / AssignedPodLost` with the name and IP cleared.

### 5.1 Stop reporting a lost Pod while retrying

```diff
--- a/internal/controller/workerclaim_controller.go
+++ b/internal/controller/workerclaim_controller.go
@@ -181,6 +181,11 @@
 		}
 	}
 	if lostRaces > 0 {
+		if claim.Status.PodName != "" {
+			// The old Pod is gone: stop reporting its name and IP while we retry.
+			return r.setPending(ctx, claim, takehomev1alpha1.ReasonAssignedPodLost,
+				fmt.Sprintf("Pod %s was lost; retrying", claim.Status.PodName), conflictRequeue)
+		}
 		return ctrl.Result{RequeueAfter: conflictRequeue}, nil
 	}
```

`attempts` still counts correctly: `setClaimed` increments it when the reported Pod
changes, and `""` to a new Pod is a change.

### 5.2 Orphan check: cache first, API server only to confirm

```diff
--- a/internal/controller/workerpool_controller.go
+++ b/internal/controller/workerpool_controller.go
@@ -166,6 +166,12 @@
 	if key.Name == "" {
 		return true, nil
 	}
+	// Fast path: a cached claim with the Pod's UID means not an orphan. If that
+	// claim is really gone, its delete event requeues this pool.
+	if err := r.Get(ctx, key, claim); err == nil && string(claim.UID) == pod.Labels[takehomev1alpha1.LabelClaimUID] {
+		return false, nil
+	}
+	// Slow path: confirm on the API server before deleting anything.
 	if err := r.APIReader.Get(ctx, key, claim); err != nil {
```

Why it's safe: the informer updates its store before it dispatches handlers. So when the
claim's delete event requeues the pool (the existing `claimToPool` watch), the cache
already misses, and the slow path confirms before anything is deleted.

## 6. Questions to expect

**"Why labels on the Pod and not the claim's status?"**
> "The Pod is the contended resource, so the lock has to be on the Pod. A single
> conditional write on one object is atomic; making status authoritative needs a
> two-object commit, and Kubernetes has no transactions. Status can lag; it can't lie
> for long, because every reconcile re-derives it."

**"Why `Update` rather than a patch?"**
> "A plain merge patch is last-writer-wins. But there's a middle option I'd use next
> time: `client.MergeFromWithOptimisticLock`. It sends `resourceVersion` in a small patch,
> so the 409 behaviour is the same without sending the whole Pod. Either way the precondition
> is on `resourceVersion`, which kubelet status writes also bump. A warm Pod with chatty
> status can 409 for reasons that aren't a competing claim. That only costs a retry."

**"What does a claim cost the API server?"**
> "Happy path: 3 writes (finalizer, Pod label, status) and 1 uncached LIST. Then a few
> no-op reconciles triggered by its own writes (some get merged in the queue), each
> doing an uncached LIST. The LISTs are what I'd remove first, with expectations" (4.3).

**"How would this hold up at Replit scale, say thousands of claims a minute?"**
> Lead with 4.2 and 4.3 (O(N²) paths), then: expectations so both controllers read
> from the cache; wake k oldest claims instead of all; more pool workers; shard by
> namespace if one controller can't keep up. Then the bigger lever, pool sizing (next question).

**"How do you size `replicas`?"**
> "Little's law: warm Pods needed ≈ claim arrival rate × Pod boot time, plus headroom
> for bursts. Today it's static. I'd add `+kubebuilder:subresource:scale` (the CRD has
> only `status`, `workerpool_types.go:72`) so KEDA or an HPA on claim rate can drive it."

**"What breaks if two controllers run?"**
> I1 and I5 hold, because they're single-object conditional writes. I2 can break
> briefly, and the next reconcile repairs it (README matrix). Leader election is the
> guard; true cross-process I2 would need a cross-object protocol.

**"Why consume Pods instead of returning them?"**
> A used sandbox is dirty; a fresh Pod is cheaper than trusting a cleanup. Offer
> `releasePolicy` for trusted workloads.

**"What isn't finished?"**
> Point at the README's "Not built" list (metrics, conditions, expectations, rolling
> updates, fail policy, FIFO), then add 4.1, 4.4 and 4.5 from here: "I found these
> re-reading it, and here's the patch for the first one."
