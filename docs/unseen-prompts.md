# Mock prompts for timed rehearsals

Have someone pick one at random, or ask Claude: *"Give me one of these at random and
don't show me the others."* Start from an empty directory, with a 45–60 minute
timer and 5 minutes of planning out loud first.

For each one, your first 5 minutes should produce:
1. **Clarifying questions** (ask even if nobody answers: it shows judgment).
2. **An architecture sketch**, the layers, and the order you'll build them in.
3. **Security constraints**, stated before any prompt.
4. **How you'll verify it** at the end (the exact `curl`/`gcloud` command).

---

### A. Internal API with a database (the classic)
> "We need an internal-facing API backed by Postgres. Make it reachable over HTTPS, but don't expose the DB."

Ask: Public internet or corp only? Existing domain? Expected traffic? Build it the way `docs/prompts.md` does.

### B. Static site with a CDN
> "Host our marketing site with a CDN. Only the CDN should serve content."

Build: GCS bucket (no `allUsers`) → backend bucket with `enable_cdn` → URL map → HTTPS proxy.
**Trap:** Agents make the bucket public with `allUsers:objectViewer`. Some setups need that,
so discuss the trade-off and the alternative: a private bucket with signed requests from Cloud CDN.
Verify: `curl -I` shows an `age:` header / cache hit on the second request.

### C. Event pipeline
> "Orders arrive as messages. Process them with a container and don't lose any."

Build: Pub/Sub topic → push subscription → Cloud Run (authenticated push with an OIDC
token from a dedicated SA) → dead-letter topic with `max_delivery_attempts`.
**Trap:** Agents grant the Pub/Sub service agent the wrong role, or forget that the DLQ needs
`roles/pubsub.publisher` on the dead-letter topic *and* `roles/pubsub.subscriber` on the source subscription.
Verify: `gcloud pubsub topics publish`, then check the Cloud Run logs; publish a poison message and see it land in the DLQ.

### D. Encrypted database
> "Compliance says our database must use our own encryption keys."

Build: KMS key ring + key (rotation period set) → grant the **Cloud SQL service agent**
`roles/cloudkms.cryptoKeyEncrypterDecrypter` **on the key** (not the project) → SQL with `encryption_key_name`.
**Trap:** The service agent identity must exist first (`google_project_service_identity`), and
key ring and instance must share a region. Keyrings can't be deleted, so say so before you create one.
Verify: `gcloud sql instances describe ... --format="value(diskEncryptionConfiguration)"`.

### E. Private admin VM
> "Ops need a box to run scripts against internal services. It must not be on the internet."

Build: VM with no external IP, OS Login, Shielded VM, its own SA with minimal roles → IAP
firewall rule (35.235.240.0/20) → `roles/iap.tunnelResourceAccessor` for one user → Cloud NAT if it needs egress.
Verify: `gcloud compute ssh vm --tunnel-through-iap` works, and there's no external IP in `describe`.

### F. GKE with keyless pod identity
> "Run a workload on Kubernetes that reads from a bucket. No keys."

Build: Autopilot cluster with private nodes (Workload Identity is always on in Autopilot) →
bucket → grant the **Kubernetes service account principal**
(`principal://iam.googleapis.com/projects/NUM/locations/global/workloadIdentityPools/PROJECT.svc.id.goog/subject/ns/NS/sa/KSA`)
`roles/storage.objectViewer` **on the bucket**.
**Trap:** Agents create a GSA and a key, or use the older GSA-annotation flow without explaining it.
Verify: `kubectl run` a pod with `google/cloud-sdk` and `gcloud storage ls gs://bucket` from inside it.
Talking point: "This is SPIFFE-style workload identity. The pod's identity is attested by the platform, not by a secret it holds."

### G. Curveball: "it's broken, fix it"
> The interviewer hands you a directory with Terraform that fails to apply, or applies something insecure.

Approach: read before prompting. `terraform init && terraform plan`, run `plan-check.sh`, then
ask the agent to explain the config *before* asking it to change anything.
