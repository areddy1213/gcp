#!/usr/bin/env bash
# First 5 minutes in a sandbox: who am I, what can I do, what already exists,
# what tools do I have. Read-only: this script changes nothing.
# Usage: ./scripts/orient.sh [PROJECT_ID]
set -uo pipefail

PROJECT="${1:-$(gcloud config get-value project 2>/dev/null)}"
MD="http://metadata.google.internal/computeMetadata/v1"

section() { printf '\n=== %s ===\n' "$1"; }

section "1. Who am I?"
gcloud auth list
gcloud config list
SA=$(curl -s -m 2 -H "Metadata-Flavor: Google" "$MD/instance/service-accounts/default/email" || true)
if [[ -n "$SA" ]]; then
  echo "VM service account: $SA   (credentials come from the metadata server, no key on disk)"
  echo "Access scopes:"
  curl -s -m 2 -H "Metadata-Flavor: Google" "$MD/instance/service-accounts/default/scopes"
else
  echo "No metadata server: not on a GCE VM (or it's blocked)."
  SA=$(gcloud config get-value account 2>/dev/null)
fi
ls ~/.config/gcloud/*.json 2>/dev/null && echo "WARNING: found JSON files in the gcloud config dir. Check for key files."
[[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]] && echo "WARNING: GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS (a key file?)"

if [[ -z "$PROJECT" ]]; then
  echo "No project set. Run: gcloud config set project <id>"; exit 1
fi

section "2. What am I allowed to do? (roles for $SA in $PROJECT)"
gcloud projects get-iam-policy "$PROJECT" \
  --flatten="bindings[].members" \
  --filter="bindings.members:$SA" \
  --format="table(bindings.role)"
if gcloud projects get-iam-policy "$PROJECT" --flatten="bindings[].members" \
     --filter="bindings.members:$SA" --format="value(bindings.role)" \
     | grep -qE '^roles/(owner|editor)$'; then
  echo ">> Basic role detected. Say it out loud: 'Fine for a sandbox, but in prod I'd scope this down.'"
fi

section "3. What already exists?"
echo "-- Enabled APIs"
gcloud services list --enabled --format="value(config.name)" | sort
echo "-- Networks";      gcloud compute networks list 2>/dev/null
echo "-- Buckets";       gcloud storage buckets list --format="value(name)" 2>/dev/null
echo "-- SQL instances"; gcloud sql instances list 2>/dev/null
echo "-- Cloud Run";     gcloud run services list 2>/dev/null
echo "-- GKE";           gcloud container clusters list 2>/dev/null
echo "-- Org policies";  gcloud resource-manager org-policies list --project="$PROJECT" 2>/dev/null

section "4. Tools"
terraform -version 2>/dev/null | head -1 || echo "terraform: missing"
for t in gcloud tmux jq claude opencode git; do
  printf '%-9s %s\n' "$t" "$(command -v "$t" || echo missing)"
done

section "5. Now, before prompting: state the architecture and constraints, then add AGENTS.md"
