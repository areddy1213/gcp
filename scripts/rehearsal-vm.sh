#!/usr/bin/env bash
# Run this on your LAPTOP (once). It creates a rehearsal VM that behaves like the
# interview sandbox: a dedicated service account, no keys, reached with plain ssh.
# Usage: PROJECT=my-sandbox ./scripts/rehearsal-vm.sh
set -euo pipefail

: "${PROJECT:?set PROJECT to your throwaway project id}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-${REGION}-a}"
VM="${VM:-sandbox}"
SA_NAME="${SA_NAME:-sandbox-runner}"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT"
gcloud services enable compute.googleapis.com iam.googleapis.com \
  cloudresourcemanager.googleapis.com serviceusage.googleapis.com

gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name="Rehearsal sandbox runner"

# Interviews often hand you a roughly editor-level identity. We copy that
# ON PURPOSE so rehearsals feel realistic. It's a throwaway project, and saying
# "I'd scope this down in prod" is part of the drill.
# Editor can't grant IAM, so we add the admin roles the builds need.
for ROLE in roles/editor \
            roles/resourcemanager.projectIamAdmin \
            roles/iam.serviceAccountAdmin \
            roles/compute.networkAdmin \
            roles/servicenetworking.networksAdmin \
            roles/run.admin \
            roles/secretmanager.admin \
            roles/cloudkms.admin \
            roles/storage.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" --role="$ROLE" --condition=None >/dev/null
  echo "granted $ROLE"
done

# cloud-platform scope + IAM roles means IAM decides what the VM can do
# (scopes are legacy and too coarse to be a real control).
gcloud compute instances describe "$VM" --zone "$ZONE" >/dev/null 2>&1 || \
  gcloud compute instances create "$VM" \
    --zone "$ZONE" \
    --machine-type e2-standard-2 \
    --image-family debian-12 --image-project debian-cloud \
    --boot-disk-size 30GB \
    --service-account "$SA" \
    --scopes cloud-platform \
    --shielded-secure-boot \
    --metadata enable-oslogin=TRUE

# Allow SSH only from your current public IP, not 0.0.0.0/0.
MYIP=$(curl -s https://ifconfig.me)
gcloud compute firewall-rules describe allow-ssh-me >/dev/null 2>&1 || \
  gcloud compute firewall-rules create allow-ssh-me \
    --network default --allow tcp:22 --source-ranges "${MYIP}/32"

cat <<MSG

VM ready. Connect with plain ssh (like the interview), not the browser console:
  gcloud compute os-login ssh-keys add --key-file ~/.ssh/id_ed25519.pub
  ssh -i ~/.ssh/id_ed25519 \$(gcloud config get-value account | tr '@.' '__')@\$(gcloud compute instances describe $VM --zone $ZONE --format='value(networkInterfaces[0].accessConfigs[0].natIP)')

Then on the VM:  git clone <this repo> && ./gcp/scripts/vm-bootstrap.sh
Stop it when you're done:  gcloud compute instances stop $VM --zone $ZONE
MSG
