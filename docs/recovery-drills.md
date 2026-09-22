# Recovery drills: practice the AI getting it wrong

The interviewers **want** to see a mistake handled well. Rehearse these until the
script below feels boring:

> **"The agent did X. That's wrong because Y. It would have caused Z. I'm fixing
> it by W, and I'm adding a rule so it doesn't happen again."**

Stay calm, don't blame the tool, and don't silently fix it: narrate.

| # | How to trigger it | What goes wrong | How you catch it | Fix + what to say |
|---|---|---|---|---|
| 1 | Prompt: *"make the app publicly accessible"* | Agent adds `google_cloud_run_v2_service_iam_member` with `allUsers` / `roles/run.invoker`, and often sets ingress to `ALL` too | `plan-check.sh` shows `PUBLIC` + `RUNINGR`; you read `member = "allUsers"` in the plan | Revert both. Use LB-only ingress + `invoker_iam_disabled = true` (or IAP). "Public should mean *through the load balancer*, where I can put Cloud Armor. `allUsers` on the service plus ALL ingress means anyone can bypass the LB." |
| 2 | Prompt: *"give the app SA access to the database"* | Agent grants `roles/editor` or `roles/cloudsql.admin` | `BASICROLE` finding, or reading the role name | `roles/cloudsql.client` + `roles/cloudsql.instanceUser`. "Admin lets it delete the instance. The app only needs to connect." |
| 3 | Ask for "a binding for the run.admin role for my user" | Agent uses `google_project_iam_binding` | `AUTHIAM` finding | Switch to `_iam_member`. "`iam_binding` is authoritative for that role, so on apply it would strip everyone else who has it, possibly the sandbox's own SA." |
| 4 | Remove the `depends_on` from Cloud SQL → PSA connection | Apply fails: *network doesn't have at least 1 private services connection* | Read the error, don't paste it blindly | Restore `depends_on`. "Terraform can't infer this dependency from references, so the SQL create raced the peering." |
| 5 | Comment out the `google_project_service` for `sqladmin` | `Error 403: ... SERVICE_DISABLED` | The error names the API | Add the API resource and a `depends_on`. "The API wasn't enabled yet. Enabling APIs is its own layer so this ordering is explicit." |
| 6 | Ask the agent to "rename the database instance" | Plan shows `-/+` on `google_sql_database_instance` | `REPLACE` finding; read the `# forces replacement` line | Refuse. Keep the name, or use `moved {}` if it's only the Terraform address that changes. "Renaming destroys the database. This is exactly why I read every plan." |
| 7 | Ask it to "connect to the DB with a password from Secret Manager" | Agent hardcodes the password in `google_secret_manager_secret_version.secret_data` in `.tf` | You read the literal string | Use IAM DB auth (no password), or `random_password` + ephemeral/write-only where supported. "That password would sit in state and git in plaintext." |
| 8 | Ask it for a provider argument that doesn't exist (e.g. "enable auto-private mode on the subnet") | Agent invents an argument | `terraform validate` fails: *An argument named "…" is not expected here* | "The agent hallucinated. I'll check the registry docs for the real field instead of letting it guess again." |
| 9 | Let the agent run `terraform apply -auto-approve` | Agent applies without you reading | You notice it in the transcript | Stop it (Esc / Ctrl-C). "My AGENTS.md says the agent only plans. A human reads the plan. I'll tighten tool permissions." Then deny the command in `.claude/settings.json` / OpenCode permissions. |
| 10 | Ask for a service account "that my laptop can use" | Agent creates `google_service_account_key` and a `local_file` for the JSON | `SAKEY` finding | Remove it. Use `gcloud auth application-default login` with `--impersonate-service-account`, or the VM identity. "Keys are long-lived bearer credentials. Impersonation gives short-lived tokens and an audit trail." |

## After each drill

- Add the lesson to `AGENTS.md` if it wasn't already there. Showing the guardrails
  file **improve during the session** is a strong signal.
- Re-run `plan-check.sh` to show the finding is gone.
- Verify with `gcloud` / `curl` (not just "the plan looks right now").

## Tool-level guardrails (optional hardening)

Claude Code (`.claude/settings.json` in the working dir):

```json
{
  "permissions": {
    "deny": ["Bash(terraform apply:*)", "Bash(terraform destroy:*)", "Bash(gcloud * delete:*)"],
    "allow": ["Bash(terraform fmt:*)", "Bash(terraform validate:*)", "Bash(terraform plan:*)"]
  }
}
```

OpenCode (`opencode.json`): set `"permission": { "bash": { "terraform apply*": "deny", "*": "ask" } }`.
Check the OpenCode docs for the exact current schema on the day.
