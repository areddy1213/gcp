#!/usr/bin/env bash
# Scan a saved Terraform plan for the mistakes AI agents commonly make.
# This does not replace reading the plan. It's a second pair of eyes you can
# run in the right-hand tmux pane while you narrate.
#
# Usage:
#   terraform plan -out=tfplan
#   ../scripts/plan-check.sh tfplan          # or pass a plan already converted to JSON
set -euo pipefail

PLAN="${1:-tfplan}"
if [[ "$PLAN" == *.json ]]; then JSON=$(cat "$PLAN"); else JSON=$(terraform show -json "$PLAN"); fi

FINDINGS=$(jq -r '
  def rc: .resource_changes[]? | select(.change.actions != ["no-op"] and .change.actions != ["read"]);
  def a: .change.after // {};
  [
    # Summary of destructive actions
    (rc | select(.change.actions | index("delete")) |
      if (.change.actions | index("create")) then "REPLACE  \(.address)  (-/+ destroys and recreates it; data loss if it is stateful)"
      else "DELETE   \(.address)" end),

    # Basic roles anywhere in IAM
    (rc | select(.type | test("_iam_(member|binding|policy)$")) | select((a.role // "") | test("^roles/(owner|editor|viewer)$")) |
      "BASICROLE \(.address) grants \(a.role)"),

    # Public principals
    (rc | select(.type | test("_iam_(member|binding)$")) |
      select(([a.member] + (a.members // [])) | map(select(. != null)) | any(test("^(allUsers|allAuthenticatedUsers)$"))) |
      "PUBLIC   \(.address) grants \(a.role) to allUsers/allAuthenticatedUsers"),
    (rc | select(.type | test("_iam_policy$")) | select((a.policy_data // "") | test("allUsers|allAuthenticatedUsers")) |
      "PUBLIC   \(.address) policy_data contains allUsers/allAuthenticatedUsers"),

    # Authoritative IAM
    (rc | select(.type | test("_iam_(binding|policy)$")) |
      "AUTHIAM  \(.address) is authoritative (\(.type)); it can remove access it does not list. Prefer _iam_member"),

    # Long-lived keys
    (rc | select(.type == "google_service_account_key") | "SAKEY    \(.address) creates a service account key"),

    # Open firewall
    (rc | select(.type == "google_compute_firewall") | select((a.direction // "INGRESS") == "INGRESS") |
      select((a.source_ranges // []) | index("0.0.0.0/0")) |
      "FIREWALL \(.address) allows ingress from 0.0.0.0/0"),

    # Cloud SQL public IP
    (rc | select(.type == "google_sql_database_instance") |
      select(a.settings[0].ip_configuration[0].ipv4_enabled? == true) |
      "SQLPUB   \(.address) has a public IPv4 address (ipv4_enabled = true)"),
    (rc | select(.type == "google_sql_database_instance") | select(a.deletion_protection? == false) |
      "SQLPROT  \(.address) has deletion_protection = false"),

    # Cloud Run open ingress
    (rc | select(.type == "google_cloud_run_v2_service") | select((a.ingress // "INGRESS_TRAFFIC_ALL") == "INGRESS_TRAFFIC_ALL") |
      "RUNINGR  \(.address) ingress is INGRESS_TRAFFIC_ALL (the run.app URL is reachable directly)"),

    # Buckets without public access prevention
    (rc | select(.type == "google_storage_bucket") | select(a.public_access_prevention? != "enforced") |
      "BUCKET   \(.address) public_access_prevention is not \"enforced\""),

    # GKE without private nodes
    (rc | select(.type == "google_container_cluster") |
      select((a.private_cluster_config // [])[0].enable_private_nodes? != true) |
      "GKEPUB   \(.address) does not enable private nodes")
  ] | .[]
' <<<"$JSON")

if [[ -n "$FINDINGS" ]]; then
  echo "$FINDINGS"
  echo
  echo "Findings above: read each one out loud and decide: intended, or fix it?"
  exit 2
fi
echo "plan-check: no findings (you still need to read the plan)"
