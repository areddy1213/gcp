# 10-day study plan (check off as you go)

This assumes about 1.5–2 hours on weekdays and longer sessions on weekends. **End every build day with
`terraform destroy`**, and stop the VM (`gcloud compute instances stop sandbox --zone us-central1-a`).

## Day 0: Ask the recruiter (5 minutes, do it today)
- [ ] Which agents are preinstalled (OpenCode? Claude Code? Something else)?
- [ ] Do they provide the model API keys, or do I bring my own?
- [ ] Will I be told the task ahead of time, or is it unseen?
- [ ] How long is the build portion, and how long is the discussion?
- [ ] Can I bring my own `AGENTS.md` / notes file into the sandbox?

## Phase 1: Foundations

### Day 1: Rehearsal environment
- [ ] Create a throwaway GCP project and **set a budget alert** ($20–50) *first*
- [ ] On your laptop: `PROJECT=<id> ./scripts/rehearsal-vm.sh`
- [ ] Connect with plain `ssh` (not browser SSH)
- [ ] On the VM: clone this repo, then `./scripts/vm-bootstrap.sh`
- [ ] Log in to `claude` and `opencode` once each
- [ ] tmux: `tmux new -s interview`, split with `Ctrl-b |`, switch panes with `Ctrl-b ←/→`, scroll with `Ctrl-b [`
- [ ] Run `./scripts/orient.sh` and say every section's result out loud
- [ ] Do the orientation again **from memory** without the script (the commands are in `scripts/orient.sh`)

### Day 2: Terraform by hand (no AI)
- [ ] HashiCorp tutorial: *Get Started – Google Cloud*
- [ ] Learn the plan symbols: `+` create, `~` update in place, `-` destroy, **`-/+` replace** (data loss on a database)
- [ ] Understand state, the GCS backend, variables, outputs, `depends_on`, and when to use modules
- [ ] Type out `reference/00-bootstrap` yourself (don't copy-paste), `init`, `plan`, `apply`
- [ ] Type out `reference/01-network` yourself, `init -backend-config="bucket=<project>-tfstate"`, `plan`, `apply`
- [ ] `terraform destroy` the network, and keep the state bucket

### Day 3: GCP concepts
- [ ] IAM: basic vs predefined roles, project vs resource grants, SA impersonation
- [ ] **`iam_policy` / `iam_binding` are authoritative; `iam_member` is additive.** Explain it in one sentence out loud
- [ ] Networking: firewall rules, Private Google Access, Cloud NAT, **Private Services Access**
- [ ] Load balancer chain: forwarding rule → target proxy → URL map → backend service → serverless NEG
- [ ] Cloud Run: ingress settings, Direct VPC egress, `invoker_iam_disabled`
- [ ] Cloud SQL: private IP only, IAM database auth
- [ ] Write an AWS ↔ GCP cheat sheet if it helps (VPC is global, IAM is on resources, etc.)

## Phase 2: Build with AI

### Day 4: Guardrails and the data layer (Claude Code)
- [ ] Read `AGENTS.md` line by line and make sure you can justify every rule
- [ ] Follow `docs/prompts.md` steps 0–3: state bucket, network, Cloud SQL
- [ ] For every plan: narrate it, then run `scripts/plan-check.sh tfplan`
- [ ] Verify SQL has only a private IP with `gcloud sql instances describe`

### Day 5: The app layer (Claude Code)
- [ ] `docs/prompts.md` steps 4–6: identity, Cloud Run, load balancer
- [ ] Closing demo: `curl` to the LB returns 200 and `curl` to `run.app` returns 404
- [ ] `scripts/iam-audit.sh`: no basic roles or public principals added
- [ ] `terraform destroy`

### Day 6: Rebuild with OpenCode, and practice recovering
- [ ] Same stack in OpenCode; use **plan mode (Tab)** visibly before build mode
- [ ] Do at least 4 drills from `docs/recovery-drills.md` (1, 3, 4, and 6 are the most important)
- [ ] For each drill, say the recovery script out loud: *did X → wrong because Y → would cause Z → fixed by W*
- [ ] Add one new rule to `AGENTS.md` based on what you saw

## Phase 3: Unseen tasks

### Day 7: GKE + Workload Identity
- [ ] `docs/unseen-prompts.md` prompt F (Autopilot, private nodes, KSA → bucket with no keys)
- [ ] Prove it from inside a pod: `gcloud storage ls gs://<bucket>`
- [ ] Practice the SPIFFE comparison in one sentence

### Day 8: Timed variations (45 minutes each)
- [ ] Variation 1: ____ (pick from B, C, D, E)
- [ ] Variation 2: ____
- [ ] (optional) Variation 3: ____
- [ ] Note where you lost time: ______________________

## Phase 4: Mocks and discussion

### Day 9: Full timed mock (60 minutes of building + 15 of discussion, recorded)
- [ ] Someone else picks the prompt (or Claude picks at random)
- [ ] Review the recording:
  - [ ] Did I state the plan before prompting?
  - [ ] Did I read every plan?
  - [ ] Did I verify outside Terraform?
  - [ ] Did I stay calm when something broke?

### Day 10: Discussion and a second mock
- [ ] Say each answer in `docs/discussion.md` aloud, timed at 2 minutes or less
- [ ] Replit multi-tenant isolation view (gVisor vs Firecracker, egress, identity)
- [ ] Do the Replit use case in `docs/replit-usecase.md` (it's the answer to "why Replit")
- [ ] Second mock, ideally with Hayk

## If the interview is under a week away
- [ ] Day 1
- [ ] Days 2+3 combined (tutorial plus IAM and networking only)
- [ ] Days 4+5 combined (the full stack with one agent)
- [ ] Drills 1, 3, and 6 only
- [ ] Day 9 mock
