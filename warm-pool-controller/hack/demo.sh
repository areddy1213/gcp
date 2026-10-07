#!/usr/bin/env bash
# Walks through the behaviour the brief asks to demonstrate, against the
# current kubectl context, and checks the invariants after every step.
#
# Prerequisites: CRDs installed (make install) and the controller running
# (make run) in another terminal.
#
#   hack/demo.sh                 pool, claims, refill, Pod loss, claim deletion
#   hack/demo.sh while-down      run after stopping the controller: records the
#                                assignments, then changes things behind its back
#   hack/demo.sh after-restart   run after starting it again: checks nothing was
#                                lost or duplicated
#
# Only kubectl and standard shell tools are needed.
set -euo pipefail

NS=${NS:-default}
cd "$(dirname "$0")/.."
SAMPLES=config/samples
SNAPSHOT=${SNAPSHOT:-${TMPDIR:-/tmp}/warm-pool-demo.snapshot}
CLAIM_UID_COL='.metadata.labels.takehome\.replit\.com/claim-uid'
CLAIM_COL='.metadata.labels.takehome\.replit\.com/claim'

k() { kubectl -n "$NS" "$@"; }
step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
show() { printf '$ kubectl %s\n' "$*"; k "$@"; }
ok() { printf '\033[32mok\033[0m  %s\n' "$*"; }
fail() { printf '\033[31mFAIL\033[0m %s\n' "$*"; exit 1; }

# wait_until DESCRIPTION TIMEOUT_SECONDS COMMAND...: retry COMMAND until it succeeds.
wait_until() {
  local what=$1 timeout=$2; shift 2
  local deadline=$((SECONDS + timeout))
  until "$@" >/dev/null 2>&1; do
    ((SECONDS < deadline)) || fail "timed out waiting for: $what"
    sleep 1
  done
  ok "$what"
}

pool_field() { k get workerpool default -o "jsonpath={.status.$1}"; }
claim_field() { k get workerclaim "$1" -o "jsonpath={.status.$2}"; }
pool_is() { [[ "$(pool_field availableReplicas)" == "$1" && "$(pool_field claimedReplicas)" == "$2" ]]; }
claim_phase_is() { [[ "$(claim_field "$1" phase)" == "$2" ]]; }
claim_gone() { ! k get workerclaim "$1" >/dev/null 2>&1; }
pod_gone() { ! k get pod "$1" >/dev/null 2>&1; }
no_pool_pods() { [[ -z "$(k get pods -l takehome.replit.com/pool -o name)" ]]; }
all_claimed() {
  local phases
  phases=$(k get workerclaims -o jsonpath='{range .items[*]}{.status.phase}{"\n"}{end}')
  [[ -n "$phases" ]] && ! grep -qv '^Claimed$' <<<"$phases"
}

# check_invariants: no claim UID on two live Pods, no Pod reported by two
# claims, and every reported Pod carries its claim's UID.
check_invariants() {
  local dup
  dup=$(k get pods -l takehome.replit.com/claim-uid --no-headers \
        -o custom-columns="UID:$CLAIM_UID_COL,DEL:.metadata.deletionTimestamp,PHASE:.status.phase" |
        awk '$2 == "<none>" && $3 != "Failed" && $3 != "Succeeded" {print $1}' | sort | uniq -d)
  [[ -z "$dup" ]] || fail "a claim holds more than one live Pod: $dup"
  dup=$(k get workerclaims --no-headers -o custom-columns='PHASE:.status.phase,POD:.status.podName' |
        awk '$1 == "Claimed" {print $2}' | sort | uniq -d)
  [[ -z "$dup" ]] || fail "a Pod is reported by more than one claim: $dup"
  local name uid pod label
  while read -r name uid pod; do
    [[ "$pod" == "<none>" ]] && continue
    label=$(k get pod "$pod" -o "jsonpath={.metadata.labels.takehome\.replit\.com/claim-uid}" 2>/dev/null || true)
    [[ -z "$label" || "$label" == "$uid" ]] || fail "claim $name reports Pod $pod, which belongs to another claim"
  done < <(k get workerclaims --no-headers -o custom-columns='N:.metadata.name,U:.metadata.uid,P:.status.podName')
  ok "invariants: one Pod per claim, one claim per Pod, statuses match Pod labels"
}

show_state() {
  show get workerpools
  show get workerclaims
  printf '$ kubectl get pods -L takehome.replit.com/claim\n'
  k get pods -l takehome.replit.com/pool -L takehome.replit.com/claim
}

demo() {
  step "Clean slate"
  k delete workerclaims --all --wait=false >/dev/null 2>&1 || true
  wait_until "no claims left" 60 bash -c "[[ -z \"\$(kubectl -n $NS get workerclaims -o name)\" ]]"
  k delete workerpool default --ignore-not-found >/dev/null
  wait_until "no pool Pods left" 120 no_pool_pods

  step "1. A pool of 3 results in three ready, unclaimed Pods"
  show apply -f "$SAMPLES/workerpool.yaml"
  wait_until "pool reports 3 warm, 0 claimed" 120 pool_is 3 0
  show_state
  [[ $(k get pods -l takehome.replit.com/pool,'!takehome.replit.com/claim-uid' -o name | wc -l) -eq 3 ]] ||
    fail "expected exactly 3 unclaimed Pods"
  ok "exactly 3 Pods, none claimed"

  step "2. A claim is assigned exactly one ready Pod"
  show apply -f "$SAMPLES/workerclaim.yaml"
  wait_until "claim-a is Claimed" 60 claim_phase_is claim-a Claimed
  local pod uid ip
  pod=$(claim_field claim-a podName)
  uid=$(k get workerclaim claim-a -o jsonpath='{.metadata.uid}')
  ip=$(claim_field claim-a podIP)
  [[ $(k get pods -l "takehome.replit.com/claim-uid=$uid" -o name | wc -l) -eq 1 ]] ||
    fail "expected exactly one Pod labelled for claim-a"
  [[ "$(k get pod "$pod" -o jsonpath='{.status.podIP}')" == "$ip" ]] || fail "status.podIP does not match the Pod"
  ok "claim-a -> $pod ($ip); exactly one Pod carries its UID"
  printf '$ kubectl get workerclaim claim-a -o yaml   (status)\n'
  k get workerclaim claim-a -o yaml | sed -n '/^status:/,$p'

  step "3. The pool replaces the claimed Pod, so warm capacity returns to 3"
  wait_until "pool reports 3 warm, 1 claimed" 120 pool_is 3 1
  show_state

  step "4. Several claims never share a Pod"
  show apply -f "$SAMPLES/claims-x5.yaml"
  check_invariants
  wait_until "all 6 claims Claimed" 120 all_claimed
  show get workerclaims
  [[ $(k get workerclaims -o jsonpath='{range .items[*]}{.status.podName}{"\n"}{end}' | sort -u | wc -l) -eq 6 ]] ||
    fail "6 claims should hold 6 different Pods"
  ok "6 claims hold 6 different Pods"
  check_invariants
  wait_until "pool refilled: 3 warm, 6 claimed" 120 pool_is 3 6

  step "5. Deleting an assigned Pod: the claim is re-assigned (AssignedPodLost)"
  pod=$(claim_field claim-a podName)
  show delete pod "$pod" --wait=false
  wait_until "claim-a moved off $pod" 120 bash -c "p=\$(kubectl -n $NS get workerclaim claim-a -o jsonpath='{.status.podName}'); [[ -n \"\$p\" && \"\$p\" != $pod ]]"
  wait_until "claim-a is Claimed again" 60 claim_phase_is claim-a Claimed
  [[ "$(claim_field claim-a attempts)" -ge 2 ]] || fail "attempts should count the lost Pod"
  ok "claim-a -> $(claim_field claim-a podName), attempts=$(claim_field claim-a attempts)"
  printf '$ kubectl get events --field-selector involvedObject.name=claim-a\n'
  k get events --field-selector involvedObject.name=claim-a --sort-by=.lastTimestamp | tail -n 4
  check_invariants

  step "6. Deleting a claim deletes its Pod (a used sandbox is not reused)"
  pod=$(claim_field claim-a podName)
  show delete workerclaim claim-a
  wait_until "claim-a is gone" 60 claim_gone claim-a
  wait_until "its Pod $pod is gone" 120 pod_gone "$pod"
  wait_until "pool still has 3 warm, now 5 claimed" 120 pool_is 3 5
  show_state
  check_invariants

  printf '\nNext: stop the controller (Ctrl-C), run "hack/demo.sh while-down",\n'
  printf 'start it again (make run), then run "hack/demo.sh after-restart".\n'
}

# while-down records who holds which Pod, then changes things the controller
# cannot see: a wiped status, a deleted bound Pod, a deleted claim, a new claim.
while_down() {
  step "Controller is down: record assignments, then change things behind its back"
  k get workerclaims --no-headers -o custom-columns='N:.metadata.name,P:.status.podName' >"$SNAPSHOT"
  cat "$SNAPSHOT"
  local wiped lost deleted
  read -r wiped _ < <(sed -n 1p "$SNAPSHOT")
  read -r lost lostpod < <(sed -n 2p "$SNAPSHOT")
  read -r deleted deletedpod < <(sed -n 3p "$SNAPSHOT")
  [[ -n "${deleted:-}" ]] || fail "run hack/demo.sh first; it needs at least 3 claims"
  printf 'wiped=%s\nlost=%s %s\ndeleted=%s %s\n' "$wiped" "$lost" "$lostpod" "$deleted" "$deletedpod" >>"$SNAPSHOT.meta"

  show patch workerclaim "$wiped" --subresource=status --type=merge -p '{"status":null}'
  show delete pod "$lostpod" --wait=false
  show delete workerclaim "$deleted" --wait=false
  show apply -f - <<'EOF'
apiVersion: takehome.replit.com/v1alpha1
kind: WorkerClaim
metadata:
  name: claim-while-down
spec:
  poolName: default
EOF
  show get workerclaims
  printf '\nNow start the controller again and run "hack/demo.sh after-restart".\n'
}

after_restart() {
  [[ -f "$SNAPSHOT.meta" ]] || fail "run hack/demo.sh while-down first"
  local wiped lost lostpod deleted deletedpod
  wiped=$(sed -n 's/^wiped=//p' "$SNAPSHOT.meta" | tail -1)
  read -r lost lostpod < <(sed -n 's/^lost=//p' "$SNAPSHOT.meta" | tail -1)
  read -r deleted deletedpod < <(sed -n 's/^deleted=//p' "$SNAPSHOT.meta" | tail -1)
  step "Controller restarted: state is rebuilt from Pod labels"
  wait_until "every claim is Claimed" 120 all_claimed
  local expect
  expect=$(awk -v n="$wiped" '$1 == n {print $2}' "$SNAPSHOT")
  [[ "$(claim_field "$wiped" podName)" == "$expect" ]] || fail "$wiped should be rebuilt onto $expect"
  ok "$wiped: wiped status rebuilt onto the same Pod $expect"
  [[ "$(claim_field "$lost" podName)" != "$lostpod" ]] || fail "$lost should have a new Pod"
  ok "$lost: Pod $lostpod was deleted while down; re-assigned to $(claim_field "$lost" podName)"
  wait_until "$deleted: finalizer ran after the restart" 60 claim_gone "$deleted"
  wait_until "$deleted: its Pod $deletedpod was deleted" 120 pod_gone "$deletedpod"
  ok "claim-while-down -> $(claim_field claim-while-down podName)"
  check_invariants
  wait_until "pool back to 3 warm" 120 bash -c "[[ \$(kubectl -n $NS get workerpool default -o jsonpath='{.status.availableReplicas}') == 3 ]]"
  show_state
  rm -f "$SNAPSHOT" "$SNAPSHOT.meta"
}

case "${1:-demo}" in
  demo) demo ;;
  while-down) while_down ;;
  after-restart) after_restart ;;
  *) echo "usage: $0 [demo|while-down|after-restart]" >&2; exit 2 ;;
esac
