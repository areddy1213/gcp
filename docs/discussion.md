# Discussion answers (aim for about 2 minutes each)

Structure every answer the same way: **claim → two or three concrete specifics → the trade-off.**

## "What would you change for production?"

> "Four buckets: identity, data, network, and process.
> **Identity:** the sandbox SA had editor. In prod, a CI-only deploy identity with
> predefined roles per layer, reached by Workload Identity Federation from the CI
> system, so there are no keys anywhere. Humans get read-only plus break-glass.
> **Data:** CMEK on Cloud SQL and the state bucket, deletion protection on,
> point-in-time recovery, and a tested restore.
> **Network:** Cloud Armor on the backend service, HTTPS only, VPC Service Controls
> around the data services to stop exfiltration even with valid credentials, and org
> policies like `sql.restrictPublicIp`, `iam.disableServiceAccountKeyCreation`, and
> `iam.allowedPolicyMemberDomains` so the guardrails don't depend on reviewers.
> **Process:** plans run on PRs, applies from CI after approval, state bucket
> readable only by the deploy identity (state contains secrets), drift detection, and
> policy-as-code (OPA/Conftest, or Sentinel) running the same checks my plan-check script does."

## "Where did the AI go wrong, and how did you know?"

Use a **real** example from your session (you'll almost always have one). Shape:

> "It added `allUsers` as invoker when I said 'public'. I caught it reading the plan:
> the member line was `allUsers`. That matters because together with ALL ingress, anyone
> could bypass the load balancer and its WAF. I changed it to LB-only ingress and added
> a rule to AGENTS.md. The general lesson: the agent optimizes for 'it works', so
> I own 'it's safe', and the plan is where I enforce that."

Other honest observations worth making:
- Agents confidently invent provider arguments; `terraform validate` plus the registry docs are the check.
- They over-scope IAM to get past a 403 instead of finding the minimal role.
- They don't know implicit ordering (PSA → SQL, API enablement), so `depends_on` gaps show up at apply.
- They'll happily `-auto-approve`, which is why the agent only plans.

## "Why Terraform over Pulumi?"

> "For shared infra, Terraform's declarative HCL is a feature: it's constrained, reviewable
> by people who aren't developers, and the plan is a stable artifact that policy tools
> understand. The ecosystem (modules, providers, and scanners like Checkov/tfsec/Conftest)
> is the largest, and most infra engineers can read it. Pulumi wins when infra
> is tightly coupled to application code, needs real abstractions and loops that HCL fights,
> or when the team is all TypeScript/Python and wants unit tests in the same language.
> OpenTofu is worth mentioning as the open-governance fork if licensing matters.
> I'd pick whichever the org already uses, since consistency beats marginal gains."

## "How would multiple teams share this?"

> "Split by blast radius and ownership. A platform team owns the foundation: org
> policies, shared VPC host project, networking, and a versioned module registry
> (`cloud-run-service`, `private-sql`) with the secure defaults baked in. App teams get
> service projects attached to the shared VPC, consume the modules, and have their own
> state per team *and* environment, so one team's bad apply can't touch another's state.
> Guardrails are enforced centrally with org policies and policy-as-code in CI rather than
> in code review. Access is via groups, not individuals. The paved road should be the
> easiest path, so teams don't go around it."

## Replit angle: multi-tenant isolation of untrusted code

Have a view. Something like:

> "Replit's core problem is running code nobody reviewed, often written by an agent, for
> millions of tenants on shared hardware. I'd think about it in layers:
> **Compute isolation:** containers alone share a kernel, so you want a stronger boundary:
> gVisor (user-space kernel, syscall interception) or Firecracker microVMs (hardware
> virtualization, fast boot). The trade-off is density and startup time against blast radius.
> **Egress control:** default-deny egress per tenant with allow-lists, blocking the metadata
> server (169.254.169.254) and internal ranges, since that's the classic SSRF path to cloud credentials.
> **Identity:** each workload gets its own short-lived, attested identity (SPIFFE-style)
> instead of shared secrets, and user secrets are injected at runtime, scoped per repl,
> never written into images or logs.
> **Enterprise layer:** single-tenant options, audit logs, SSO/SCIM, and data-residency
> controls, because a bank's security review decides the deal."

Tie it back: *"Today's sandbox is a small version of the same problem: an agent with cloud
credentials, producing infra nobody hand-wrote, and I was the policy layer."*
