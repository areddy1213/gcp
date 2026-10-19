# GCP sandbox round: practice kit

A rehearsal kit for an interview round where you **build real GCP infrastructure with an
AI coding agent (OpenCode or Claude Code) on a remote VM**. You're graded on how you drive
the AI, not on writing HCL from memory.

## The loop you're demonstrating

Every layer, every time, out loud:

| Step | What you do | What you say |
|---|---|---|
| **1. Plan** | State the architecture and the next layer *before* prompting | "Next is the data layer: PSA range, peering, SQL with private IP only. I expect 4 creates and 0 destroys." |
| **2. Constrain** | One small prompt per layer, with explicit rules (`AGENTS.md`) | "Only the network layer. Show me the plan; don't apply." |
| **3. Check** | Read the whole `terraform plan`, then run `scripts/plan-check.sh` | "Here it granted `roles/editor`. That's too broad, and here's the minimal role." |
| **4. Verify** | Prove it outside Terraform with `gcloud` / `curl` | "The LB returns 200, `run.app` returns 404, and the IAM audit is clean." |
| **5. Recover** | When the AI is wrong: name it, explain it, fix it, and add a rule | "It added `allUsers`. That bypasses the LB. Reverting, and adding a rule to AGENTS.md." |

## Walkthrough: where to start

**If you have zero GCP/Terraform experience, go in this order. Don't skip step 3.**

1. **Today:** send the recruiter the questions in [Day 0 of the study plan](docs/study-plan.md#day-0-ask-the-recruiter-5-minutes-do-it-today).
2. **Set up the rehearsal VM** (Day 1). From your laptop:
   ```bash
   PROJECT=my-throwaway-project ./scripts/rehearsal-vm.sh    # VM + dedicated SA, no keys
   ssh ...                                                    # the script prints the command
   git clone <this repo> && cd gcp && ./scripts/vm-bootstrap.sh   # on the VM
   tmux new -s interview        # Ctrl-b |  → agent on the left, verification shell on the right
   ./scripts/orient.sh          # the "first 5 minutes" routine
   ```
3. **Write Terraform by hand once** (Day 2). Type out [`reference/00-bootstrap`](reference/00-bootstrap/main.tf)
   and [`reference/01-network`](reference/01-network/main.tf) yourself. Every line is commented.
   This is what lets you judge the agent's output later.
4. **Build the full stack with the agent**, layer by layer, following [`docs/prompts.md`](docs/prompts.md)
   (Days 4–5). Copy `AGENTS.md` and `CLAUDE.md` into your working directory first.
5. **Break it on purpose**: [`docs/recovery-drills.md`](docs/recovery-drills.md) (Day 6).
6. **Unseen tasks, then timed mocks**: [`docs/unseen-prompts.md`](docs/unseen-prompts.md) (Days 7–9).
7. **Discussion prep**: [`docs/discussion.md`](docs/discussion.md) and [`docs/replit-usecase.md`](docs/replit-usecase.md) (Day 10).

Track progress in [`docs/study-plan.md`](docs/study-plan.md). The checkboxes render on GitHub.

## What's in here

```
AGENTS.md                 Guardrails every agent reads (OpenCode reads it directly)
CLAUDE.md                 Imports AGENTS.md for Claude Code
scripts/
  rehearsal-vm.sh         (laptop) Create the practice VM with a dedicated SA, no keys, SSH from your IP only
  vm-bootstrap.sh         (VM) Install terraform, tmux, jq, Node, Claude Code, OpenCode
  orient.sh               (VM) First 5 minutes: identity, permissions, existing resources, tools. Read-only
  plan-check.sh           Scan a saved plan for owner/editor, allUsers, SA keys, authoritative IAM,
                          0.0.0.0/0, public SQL, open Cloud Run ingress, and -/+ replacements
  iam-audit.sh            After apply: basic roles, public principals, public buckets, Run invokers, SA keys
reference/
  00-bootstrap/           Hand-written state bucket (Day 2)
  01-network/             Hand-written VPC, subnet, NAT, IAP firewall, Private Services Access (Day 2)
docs/
  study-plan.md           10-day checklist (plus the under-a-week version)
  prompts.md              The layer-by-layer prompts, what to check, and how to verify each
  recovery-drills.md      10 ways the agent goes wrong, and the fix + script for each
  unseen-prompts.md       7 mock tasks with the traps to watch for
  discussion.md           2-minute answers: prod changes, AI mistakes, TF vs Pulumi, multi-team, Replit
  replit-usecase.md       "Why Replit" + a one-hour cert-checker build with Replit Agent
warm-pool-controller/     Replit take-home: WorkerPool/WorkerClaim Kubernetes controller (Go, Kubebuilder)
  docs/review-prep.md     Code-review session notes: verified state, walkthrough, issues, patches, answers
```

## Using `plan-check.sh`

```bash
terraform plan -out=tfplan
../scripts/plan-check.sh tfplan    # exit 2 + findings, or exit 0
```

It's a second pair of eyes, **not** a substitute for reading the plan. Say that if you use it in the interview.

## Cost hygiene

- Set a budget alert before creating anything.
- `terraform destroy` at the end of every session. Cloud SQL and the LB forwarding rule bill hourly.
- `gcloud compute instances stop sandbox --zone us-central1-a` when you're not practicing.
- Never commit `*.tfstate`, `tfplan`, or `.terraform/` (see `.gitignore`).
