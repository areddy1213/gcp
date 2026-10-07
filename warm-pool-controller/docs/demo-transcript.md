# Demo transcript

Recorded on 2026-10-07 against a kind cluster (Kubernetes v1.34.11), with the
controller started by `make run`. This is the unedited output of
`hack/demo.sh`, apart from terminal colours. Pod names are random.

## `hack/demo.sh`

```text

== Clean slate
ok  no claims left
ok  no pool Pods left

== 1. A pool of 3 results in three ready, unclaimed Pods
$ kubectl apply -f config/samples/workerpool.yaml
workerpool.takehome.replit.com/default created
ok  pool reports 3 warm, 0 claimed
$ kubectl get workerpools
NAME      DESIRED   WARM   PENDING   CLAIMED   TOTAL   AGE
default   3         3      0         0         3       3s
$ kubectl get workerclaims
No resources found in default namespace.
$ kubectl get pods -L takehome.replit.com/claim
NAME            READY   STATUS    RESTARTS   AGE   CLAIM
default-6zztv   1/1     Running   0          4s    
default-75f9l   1/1     Running   0          4s    
default-l89nj   1/1     Running   0          4s    
ok  exactly 3 Pods, none claimed

== 2. A claim is assigned exactly one ready Pod
$ kubectl apply -f config/samples/workerclaim.yaml
workerclaim.takehome.replit.com/claim-a created
ok  claim-a is Claimed
ok  claim-a -> default-6zztv (10.244.0.10); exactly one Pod carries its UID
$ kubectl get workerclaim claim-a -o yaml   (status)
status:
  assignedAt: "2026-10-07T05:03:36Z"
  attempts: 1
  message: Assigned Pod default-6zztv from pool default
  phase: Claimed
  podIP: 10.244.0.10
  podName: default-6zztv
  reason: Assigned

== 3. The pool replaces the claimed Pod, so warm capacity returns to 3
ok  pool reports 3 warm, 1 claimed
$ kubectl get workerpools
NAME      DESIRED   WARM   PENDING   CLAIMED   TOTAL   AGE
default   3         3      0         1         4       6s
$ kubectl get workerclaims
NAME      POOL      PHASE     POD             IP            REASON     AGE
claim-a   default   Claimed   default-6zztv   10.244.0.10   Assigned   2s
$ kubectl get pods -L takehome.replit.com/claim
NAME            READY   STATUS    RESTARTS   AGE   CLAIM
default-6zztv   1/1     Running   0          6s    claim-a
default-75f9l   1/1     Running   0          6s    
default-l89nj   1/1     Running   0          6s    
default-qnqkt   1/1     Running   0          2s    

== 4. Several claims never share a Pod
$ kubectl apply -f config/samples/claims-x5.yaml
workerclaim.takehome.replit.com/claim-1 created
workerclaim.takehome.replit.com/claim-2 created
workerclaim.takehome.replit.com/claim-3 created
workerclaim.takehome.replit.com/claim-4 created
workerclaim.takehome.replit.com/claim-5 created
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels
ok  all 6 claims Claimed
$ kubectl get workerclaims
NAME      POOL      PHASE     POD             IP            REASON     AGE
claim-1   default   Claimed   default-75f9l   10.244.0.9    Assigned   3s
claim-2   default   Claimed   default-l89nj   10.244.0.8    Assigned   3s
claim-3   default   Claimed   default-phfxz   10.244.0.14   Assigned   3s
claim-4   default   Claimed   default-qnqkt   10.244.0.11   Assigned   3s
claim-5   default   Claimed   default-4mr6v   10.244.0.13   Assigned   3s
claim-a   default   Claimed   default-6zztv   10.244.0.10   Assigned   5s
ok  6 claims hold 6 different Pods
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels
ok  pool refilled: 3 warm, 6 claimed

== 5. Deleting an assigned Pod: the claim is re-assigned (AssignedPodLost)
$ kubectl delete pod default-6zztv --wait=false
pod "default-6zztv" deleted from default namespace
ok  claim-a moved off default-6zztv
ok  claim-a is Claimed again
ok  claim-a -> default-kplmc, attempts=2
$ kubectl get events --field-selector involvedObject.name=claim-a
LAST SEEN   TYPE      REASON            OBJECT                MESSAGE
8s          Normal    Assigned          workerclaim/claim-a   Assigned Pod default-6zztv from pool default
0s          Warning   AssignedPodLost   workerclaim/claim-a   Pod default-6zztv was deleted or failed; looking for another warm Pod
0s          Normal    Assigned          workerclaim/claim-a   Assigned Pod default-kplmc from pool default
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels

== 6. Deleting a claim deletes its Pod (a used sandbox is not reused)
$ kubectl delete workerclaim claim-a
workerclaim.takehome.replit.com "claim-a" deleted from default namespace
ok  claim-a is gone
ok  its Pod default-kplmc is gone
ok  pool still has 3 warm, now 5 claimed
$ kubectl get workerpools
NAME      DESIRED   WARM   PENDING   CLAIMED   TOTAL   AGE
default   3         3      0         5         8       15s
$ kubectl get workerclaims
NAME      POOL      PHASE     POD             IP            REASON     AGE
claim-1   default   Claimed   default-75f9l   10.244.0.9    Assigned   9s
claim-2   default   Claimed   default-l89nj   10.244.0.8    Assigned   9s
claim-3   default   Claimed   default-phfxz   10.244.0.14   Assigned   9s
claim-4   default   Claimed   default-qnqkt   10.244.0.11   Assigned   9s
claim-5   default   Claimed   default-4mr6v   10.244.0.13   Assigned   9s
$ kubectl get pods -L takehome.replit.com/claim
NAME            READY   STATUS    RESTARTS   AGE   CLAIM
default-4mr6v   1/1     Running   0          9s    claim-5
default-4plhk   1/1     Running   0          7s    
default-5vzqz   1/1     Running   0          3s    
default-75f9l   1/1     Running   0          15s   claim-1
default-jxqcc   1/1     Running   0          7s    
default-l89nj   1/1     Running   0          15s   claim-2
default-phfxz   1/1     Running   0          9s    claim-3
default-qnqkt   1/1     Running   0          11s   claim-4
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels

Next: stop the controller (Ctrl-C), run "hack/demo.sh while-down",
start it again (make run), then run "hack/demo.sh after-restart".
```

## Ctrl-C the controller, then `hack/demo.sh while-down`

```text

== Controller is down: record assignments, then change things behind its back
claim-1   default-75f9l
claim-2   default-l89nj
claim-3   default-phfxz
claim-4   default-qnqkt
claim-5   default-4mr6v
$ kubectl patch workerclaim claim-1 --subresource=status --type=merge -p {"status":null}
workerclaim.takehome.replit.com/claim-1 patched
$ kubectl delete pod default-l89nj --wait=false
pod "default-l89nj" deleted from default namespace
$ kubectl delete workerclaim claim-3 --wait=false
workerclaim.takehome.replit.com "claim-3" deleted from default namespace
$ kubectl apply -f -
workerclaim.takehome.replit.com/claim-while-down created
$ kubectl get workerclaims
NAME               POOL      PHASE     POD             IP            REASON     AGE
claim-1            default                                                      20s
claim-2            default   Claimed   default-l89nj   10.244.0.8    Assigned   20s
claim-3            default   Claimed   default-phfxz   10.244.0.14   Assigned   20s
claim-4            default   Claimed   default-qnqkt   10.244.0.11   Assigned   20s
claim-5            default   Claimed   default-4mr6v   10.244.0.13   Assigned   20s
claim-while-down   default                                                      0s

Now start the controller again and run "hack/demo.sh after-restart".
```

## `make run` again, then `hack/demo.sh after-restart`

```text

== Controller restarted: state is rebuilt from Pod labels
ok  every claim is Claimed
ok  claim-1: wiped status rebuilt onto the same Pod default-75f9l
ok  claim-2: Pod default-l89nj was deleted while down; re-assigned to default-4plhk
ok  claim-3: finalizer ran after the restart
ok  claim-3: its Pod default-phfxz was deleted
ok  claim-while-down -> default-jxqcc
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels
ok  pool back to 3 warm
$ kubectl get workerpools
NAME      DESIRED   WARM   PENDING   CLAIMED   TOTAL   AGE
default   3         3      0         5         8       42s
$ kubectl get workerclaims
NAME               POOL      PHASE     POD             IP            REASON     AGE
claim-1            default   Claimed   default-75f9l   10.244.0.9    Assigned   36s
claim-2            default   Claimed   default-4plhk   10.244.0.16   Assigned   36s
claim-4            default   Claimed   default-qnqkt   10.244.0.11   Assigned   36s
claim-5            default   Claimed   default-4mr6v   10.244.0.13   Assigned   36s
claim-while-down   default   Claimed   default-jxqcc   10.244.0.15   Assigned   16s
$ kubectl get pods -L takehome.replit.com/claim
NAME            READY   STATUS    RESTARTS   AGE   CLAIM
default-4mr6v   1/1     Running   0          36s   claim-5
default-4plhk   1/1     Running   0          34s   claim-2
default-5vzqz   1/1     Running   0          30s   
default-75f9l   1/1     Running   0          42s   claim-1
default-h5sd8   1/1     Running   0          2s    
default-jxqcc   1/1     Running   0          34s   claim-while-down
default-q5z2f   1/1     Running   0          2s    
default-qnqkt   1/1     Running   0          38s   claim-4
```

## Deleting the pool

The garbage collector deletes the pool's Pods through their ownerReference. The
claims go back to `Pending` with `PoolNotFound`, and recreating the pool assigns
them again.

```text
$ kubectl delete workerpool default
workerpool.takehome.replit.com "default" deleted from default namespace
$ kubectl get workerclaims
NAME               POOL      PHASE     POD   IP    REASON         AGE
claim-1            default   Pending               PoolNotFound   107s
claim-2            default   Pending               PoolNotFound   107s
claim-4            default   Pending               PoolNotFound   107s
claim-5            default   Pending               PoolNotFound   107s
claim-while-down   default   Pending               PoolNotFound   87s
$ kubectl get workerclaim claim-1 -o jsonpath='{.status}' | jq .
{
  "attempts": 1,
  "message": "WorkerPool \"default\" does not exist in namespace \"default\"",
  "phase": "Pending",
  "reason": "PoolNotFound"
}
$ kubectl apply -f config/samples/workerpool.yaml
$ kubectl get workerpools
NAME      DESIRED   WARM   PENDING   CLAIMED   TOTAL   AGE
default   3         3      0         5         8       5s
$ kubectl get workerclaims
NAME               POOL      PHASE     POD             IP            REASON     AGE
claim-1            default   Claimed   default-z9bsf   10.244.0.23   Assigned   113s
claim-2            default   Claimed   default-xl67z   10.244.0.20   Assigned   113s
claim-4            default   Claimed   default-9k599   10.244.0.25   Assigned   113s
claim-5            default   Claimed   default-7j7lm   10.244.0.22   Assigned   113s
claim-while-down   default   Claimed   default-4ds8h   10.244.0.21   Assigned   93s
```

## The same demo with the controller running in the cluster

The controller was deployed with `make deploy` (leader election on), and the
restart was `kubectl scale --replicas=0` followed by `--replicas=1`. Every check
passed, and the controller logged no errors:

```text
ok  no claims left
ok  no pool Pods left
ok  pool reports 3 warm, 0 claimed
ok  exactly 3 Pods, none claimed
ok  claim-a is Claimed
ok  claim-a -> default-8xp7x (10.244.0.42); exactly one Pod carries its UID
ok  pool reports 3 warm, 1 claimed
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels
ok  all 6 claims Claimed
ok  6 claims hold 6 different Pods
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels
ok  pool refilled: 3 warm, 6 claimed
ok  claim-a moved off default-8xp7x
ok  claim-a is Claimed again
ok  claim-a -> default-srcln, attempts=2
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels
ok  claim-a is gone
ok  its Pod default-srcln is gone
ok  pool still has 3 warm, now 5 claimed
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels
$ kubectl -n warm-pool-controller-system scale deploy/warm-pool-controller-controller-manager --replicas=0
$ kubectl -n warm-pool-controller-system scale deploy/warm-pool-controller-controller-manager --replicas=1
ok  every claim is Claimed
ok  claim-1: wiped status rebuilt onto the same Pod default-b2g6h
ok  claim-2: Pod default-rjrfp was deleted while down; re-assigned to default-wsmp4
ok  claim-3: finalizer ran after the restart
ok  claim-3: its Pod default-xvbdf was deleted
ok  claim-while-down -> default-vvknn
ok  invariants: one Pod per claim, one claim per Pod, statuses match Pod labels
ok  pool back to 3 warm
```
