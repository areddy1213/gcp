# Agent guardrails for GCP infrastructure work

Rules for any coding agent in this repo (OpenCode reads this file, and Claude Code
reads it through `CLAUDE.md`). Copy it into the interview sandbox before your first prompt.

## How we work

1. **Plan before you write.** Before editing files, list the resources you will
   add or change and the reason for each. Wait for approval.
2. **One layer per change.** Stay inside the layer you were asked to build
   (APIs, network, data, identity, app, load balancer). Never "build it all" in one go.
3. **Never run `terraform apply` or `terraform destroy` yourself.** You may run
   `terraform fmt`, `terraform validate`, and `terraform plan -out=tfplan`. A human
   reads the plan and runs the apply.
4. **Keep diffs small and explain them.** After each change, summarize which
   resources were added or changed and flag anything destructive (`-/+` or `-`).

## Security rules (non-negotiable)

- **No basic roles.** Never grant `roles/owner`, `roles/editor`, or `roles/viewer`.
  Use predefined roles, scoped to the resource (bucket, secret, service) rather
  than the project wherever possible.
- **No public principals.** Never grant anything to `allUsers` or
  `allAuthenticatedUsers`. If something must be reachable, it goes behind the load balancer.
- **No service account keys.** Never create `google_service_account_key`, never
  write JSON keys to disk, never set `GOOGLE_APPLICATION_CREDENTIALS` to a key file.
  Use the VM's attached identity, Workload Identity, or impersonation.
- **Additive IAM only.** Use `google_*_iam_member`. Do not use `google_*_iam_policy`
  or `google_*_iam_binding` (they are authoritative and can silently remove
  existing access) unless I explicitly ask.
- **Public apps go through the load balancer, not `allUsers`.** To make a Cloud Run
  app public, restrict its ingress to the load balancer and turn off the invoker
  check with `invoker_iam_disabled = true`, or put IAP on the backend. Tell me which
  one you chose and why. Never quietly add `allUsers` as `roles/run.invoker`.
- **Private by default.**
  - Cloud SQL: private IP only (`ipv4_enabled = false`), via Private Services Access.
  - Cloud Run: `ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"`, egress through Direct VPC egress.
  - GKE: private nodes, and a private control-plane endpoint where the task allows it.
  - VMs: no external IP; reach them with IAP.
- **No `0.0.0.0/0` ingress firewall rules**, except Google's load balancer and
  health-check ranges (`130.211.0.0/22`, `35.191.0.0/16`) and IAP (`35.235.240.0/20`).
- **Secrets live in Secret Manager**, never in `.tf` files, `terraform.tfvars`, or
  environment variables baked into images.
- **Protect stateful resources.** Set `deletion_protection` on databases (the
  sandbox may turn it off at teardown) and call out any plan that replaces them.

## Terraform conventions

- Remote state in GCS (versioning on, uniform bucket-level access). Never commit state.
- Pin the provider: `hashicorp/google ~> 6.0`.
- Every resource needs `project` and `region` from variables. No hard-coded project IDs.
- Enable APIs with `google_project_service` (`disable_on_destroy = false`), and
  add `depends_on` from resources that need them.
- Label everything: `env`, `owner`, `managed-by = "terraform"`.
- Put names in variables or locals so a second environment is just a new tfvars file.

## When you are unsure

Ask instead of guessing. Don't invent resource arguments; if you aren't sure an
argument exists in provider 6.x, say so, and I will check the docs.
