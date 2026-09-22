#!/usr/bin/env bash
# After an apply: verify outside Terraform that nothing broad got granted.
# Usage: ./scripts/iam-audit.sh [PROJECT_ID]
set -uo pipefail
PROJECT="${1:-$(gcloud config get-value project 2>/dev/null)}"

echo "=== Project-level basic roles ==="
gcloud projects get-iam-policy "$PROJECT" --flatten="bindings[].members" \
  --filter="bindings.role:(roles/owner OR roles/editor OR roles/viewer)" \
  --format="table(bindings.role, bindings.members)"

echo; echo "=== Public principals at project level ==="
gcloud projects get-iam-policy "$PROJECT" --format=json | jq -r \
  '.bindings[] | select(.members[] | test("allUsers|allAuthenticatedUsers")) | .role' || true

echo; echo "=== Public buckets ==="
for b in $(gcloud storage buckets list --format="value(name)" 2>/dev/null); do
  gcloud storage buckets get-iam-policy "gs://$b" --format=json 2>/dev/null \
    | jq -e '.bindings[]? | select(.members[] | test("allUsers|allAuthenticatedUsers"))' >/dev/null \
    && echo "PUBLIC: gs://$b"
done

echo; echo "=== Cloud Run services and who can invoke them ==="
gcloud run services list --format="value(metadata.name,region)" 2>/dev/null | while read -r svc region; do
  ingress=$(gcloud run services describe "$svc" --region "$region" --format="value(metadata.annotations['run.googleapis.com/ingress'])")
  invokers=$(gcloud run services get-iam-policy "$svc" --region "$region" --format=json \
    | jq -r '[.bindings[]? | select(.role=="roles/run.invoker") | .members[]] | join(",")')
  echo "$svc  ingress=$ingress  invokers=${invokers:-none}"
done

echo; echo "=== Service account keys (user-managed) ==="
for sa in $(gcloud iam service-accounts list --format="value(email)"); do
  n=$(gcloud iam service-accounts keys list --iam-account "$sa" --managed-by=user --format="value(name)" | wc -l)
  [[ "$n" -gt 0 ]] && echo "KEYS: $sa has $n user-managed key(s)"
done
echo "(done)"
