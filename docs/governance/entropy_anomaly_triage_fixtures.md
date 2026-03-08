# Entropy Anomaly Triage Replay Fixtures

This document defines deterministic anomaly triage threshold semantics for entropy policy evaluation and ties them to replay fixtures used in CI.

## Threshold semantics

`runtime/evolution/entropy_policy.py` exposes deterministic threshold tiers via `EntropyAnomalyThresholds`:

- **`monitor_bits`**: minimum observed entropy bits that classify a mutation as an anomaly requiring monitoring.
- **`investigate_bits`**: observed entropy threshold requiring explicit operator investigation.
- **`block_bits`**: critical anomaly threshold; expected to fail closed via entropy ceiling enforcement in governed runtime flows.

The default threshold profile is:

- `monitor_bits = 1`
- `investigate_bits = 8`
- `block_bits = 16`

## Deterministic reason taxonomy

Triaging emits deterministic reason labels:

- `anomaly_not_detected`
- `anomaly_observed_bits_monitor_threshold_reached`
- `anomaly_observed_bits_investigate_threshold_reached`
- `anomaly_observed_bits_block_threshold_reached`

Entropy policy outcomes additionally preserve policy verdict reasons:

- `ok`
- `entropy_policy_disabled`
- `entropy_budget_exceeded`
- `epoch_entropy_budget_exceeded`
- `mutation_and_epoch_entropy_budget_exceeded`

## Replay fixtures

Fixtures are encoded in:

- `tests/determinism/test_entropy_anomaly_triage_replay.py`

Scenarios covered:

1. `none`: no observed anomaly bits, deterministic no-anomaly triage.
2. `monitor`: observed bits at monitor threshold, policy pass with monitor triage.
3. `investigate`: observed bits at investigate threshold, policy pass with investigate triage.
4. `block_fail_closed`: observed bits beyond block threshold, deterministic fail-closed verdict (`entropy_ceiling_exceeded`) and stable violation reason.

## Fail-closed expectation

For block-tier anomalies, replay runs must produce identical:

- policy pass/fail outcome,
- policy `reason`,
- `triage_level` / `triage_reason`, and
- replay digest for fixture summaries.

Any divergence across replays is a governance failure and should block promotion.
