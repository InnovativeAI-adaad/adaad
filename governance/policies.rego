package adaad.governance

# Baseline policy for privileged runtime operations.
# Overlay bundles may replace/extend this policy file through
# ADAAD_GOVERNANCE_POLICY_PATHS (os.pathsep-separated paths).

default allow = false

default deny_reason = "deny_by_default"

privileged_operations := {
  "mutation.apply",
  "mutation.promote",
  "mutation.manifest.write",
}

allowed_tiers := {"governance", "production"}

allow {
  input.operation in privileged_operations
  input.actor_tier in allowed_tiers
  not input.fail_closed
}

allow {
  input.operation in privileged_operations
  input.emergency_override == true
  input.override_token_verified == true
}

deny_reason = "operation_not_privileged" {
  not input.operation in privileged_operations
}

deny_reason = "insufficient_tier" {
  input.operation in privileged_operations
  not input.actor_tier in allowed_tiers
  not input.emergency_override == true
}

deny_reason = "fail_closed" {
  input.fail_closed
}
