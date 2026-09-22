# The reference build: one small prompt per layer

Target stack: **VPC → Private Services Access → Cloud SQL (private IP, IAM auth) →
service account → Cloud Run (Direct VPC egress, LB-only ingress) → external HTTP(S)
load balancer with a serverless NEG**, with remote state in GCS.

Each step below follows the same loop. Say it out loud every time, even when rehearsing alone.

```
PLAN     "Next layer is X. It needs A, B, C. I'm expecting N resources to be created and nothing destroyed."
PROMPT   one layer, with explicit constraints (copy from below)
CHECK    terraform plan -out=tfplan  →  read it  →  ../scripts/plan-check.sh tfplan
APPLY    terraform apply tfplan      (you run this, not the agent)
VERIFY   gcloud / curl from the right-hand pane, outside Terraform
```

> In OpenCode, press **Tab** to switch to *plan* mode for the PLAN step, so the
> interviewer sees it, then Tab back to *build*. In Claude Code, use **Shift+Tab**
> to cycle into plan mode.

---

## 0. Say the architecture (before any prompt)

> "Users hit a global external Application Load Balancer. It routes through a serverless
> NEG to Cloud Run. Cloud Run's ingress only accepts traffic from the load balancer, so the
> `run.app` URL is dead. Cloud Run reaches Cloud SQL over private IP using Direct VPC
> egress, and it authenticates with IAM database auth as its own service account, so
> there are no passwords and no keys. Cloud SQL has no public IP. It gets a private one
> through Private Services Access. State is in a versioned GCS bucket. I'll build it one
> layer at a time and read every plan."

Then draw it (tmux pane, or a paper sketch you describe):

```
client ─▶ [fwd rule :80/443] ─▶ [target proxy] ─▶ [URL map] ─▶ [backend service]
                                                                     │
                                                              [serverless NEG]
                                                                     │
                                            Cloud Run (ingress = LB only, SA = app-sa)
                                                                     │ Direct VPC egress
                                         VPC ── PSA peering ──▶ Cloud SQL (private IP, IAM auth)
```

---

## 1. State bucket (by hand or with the agent)

**Prompt**
> Create a `bootstrap/` Terraform layer that makes a GCS bucket for remote state:
> versioning on, uniform bucket-level access, public access prevention enforced,
> named `${project_id}-tfstate`. Local state for this layer only. Don't touch anything else.

**Check:** 1–2 resources (`google_project_service`, `google_storage_bucket`).
**Verify:** `gcloud storage buckets describe gs://$PROJECT-tfstate --format="yaml(versioning,iamConfiguration)"`

Compare with `reference/00-bootstrap/main.tf`.

## 2. APIs + network

**Prompt**
> In `infra/`, using a GCS backend with prefix `app`, add only the network layer:
> enable compute and servicenetworking APIs, a custom-mode VPC, one subnet in
> `var.region` with Private Google Access, Cloud Router + Cloud NAT, and a Private
> Services Access range plus a `google_service_networking_connection`. No firewall
> rules except IAP SSH from 35.235.240.0/20. Show me the plan; don't apply.

**Check:** about 8 resources, no `0.0.0.0/0`, `auto_create_subnetworks = false`.
**Verify:**
```bash
gcloud compute networks subnets describe app-us-central1 --region us-central1 --format="value(privateIpGoogleAccess)"
gcloud services vpc-peerings list --network app-vpc
```

Compare with `reference/01-network/main.tf`.

## 3. Cloud SQL

**Prompt**
> Add Cloud SQL for PostgreSQL 16, `db-custom-1-3840`, in `var.region`. Private IP only
> on our VPC (`ipv4_enabled = false`), `depends_on` the PSA connection, IAM database
> authentication on (`cloudsql.iam_authentication` flag), backups on, and a variable for
> `deletion_protection`. One database called `app`. No users with passwords.

**Check:**
- `ipv4_enabled = false` and `private_network` set.
- No `google_sql_user` with a `password`.
- `plan-check.sh` shows no `SQLPUB` finding.
- Cloud SQL takes 8–15 minutes. Use the time to narrate what comes next.

**Verify:**
```bash
gcloud sql instances describe app-db --format="yaml(ipAddresses,settings.ipConfiguration)"
# Expect only type: PRIVATE, and ipv4Enabled: false
```

## 4. Identity

**Prompt**
> Add a service account `app-run` for Cloud Run. Grant only: `roles/cloudsql.client`
> and `roles/cloudsql.instanceUser` at the project (these can't be scoped lower),
> and `roles/logging.logWriter`. Add a `google_sql_user` of type
> `CLOUD_IAM_SERVICE_ACCOUNT` for it. Use `_iam_member` only. No keys.

**Check:**
- Exactly three `google_project_iam_member` grants.
- The SQL user name is the SA email **without** `.gserviceaccount.com`. Agents often get this wrong.
- No `google_service_account_key`.

**Verify:** `../scripts/iam-audit.sh`

## 5. Cloud Run

**Prompt**
> Add a `google_cloud_run_v2_service` named `app`, running
> `us-docker.pkg.dev/cloudrun/container/hello`, as `app-run`. Set ingress to
> `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER`, Direct VPC egress on our subnet with
> `PRIVATE_RANGES_ONLY`, and `invoker_iam_disabled = true` (it's public only via the LB).
> Pass the instance connection name and DB name as env vars. `deletion_protection = false` for the sandbox.

**Check:**
- `ingress` isn't `INGRESS_TRAFFIC_ALL`.
- No `allUsers` `run.invoker` binding. If the agent adds one, that's your recovery moment (see drill 1).
- `vpc_access.network_interfaces` points at our subnet.

**Verify:**
```bash
URL=$(gcloud run services describe app --region us-central1 --format='value(status.url)')
curl -s -o /dev/null -w "%{http_code}\n" "$URL"   # expect 404: the run.app URL is blocked by ingress
```

## 6. Load balancer

**Prompt**
> Add a global external Application Load Balancer (`EXTERNAL_MANAGED`) in front of
> Cloud Run: serverless NEG → backend service → URL map → target HTTP proxy → global
> forwarding rule on port 80 with a reserved global IP. Output the IP. (HTTPS with a
> managed cert is optional; it needs a domain.)

**Check:** 5–6 resources. Be ready to say what each one does:
- **Forwarding rule:** the IP and port clients connect to.
- **Target proxy:** terminates HTTP/TLS.
- **URL map:** routes by host and path.
- **Backend service:** policy for the backends (logging, Cloud Armor, IAP, CDN).
- **Serverless NEG:** points at the Cloud Run service.

**Verify (the closing demo):**
```bash
LB=$(terraform output -raw lb_ip)
curl -s -o /dev/null -w "LB: %{http_code}\n" "http://$LB/"   # 200. The LB can take 3–5 min to start serving.
curl -s -o /dev/null -w "run.app: %{http_code}\n" "$URL"     # 404, blocked
../scripts/iam-audit.sh                                       # no basic roles or public principals added
```

> "Traffic works through the only front door, the direct URL is dead, and the audit shows
> nothing broad was granted. What I'd add for prod: Cloud Armor on the backend service,
> HTTPS with a managed cert and an HTTP→HTTPS redirect, CMEK on SQL, and applies from CI."

## 7. Tear down

```bash
terraform destroy          # you may need deletion_protection=false on SQL first
gcloud sql instances list  # confirm it's gone (billing)
```

---

## Prompt patterns that keep the agent small

- "**Only** add X. Don't modify existing files except `main.tf`."
- "Show me the diff and the list of resources you expect in the plan **before** running anything."
- "Explain every IAM grant you added and why it can't be narrower."
- "You used `<arg>`. Does that exist in provider 6.x? If you're not sure, say so."
- "`terraform validate` failed with `<error>`. Fix only that error."
