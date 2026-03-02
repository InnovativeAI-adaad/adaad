# Deterministic Red-Team Corpus

This corpus defines deterministic prompt-injection and adversarial-input scenarios used by the red-team harness.

## Scenario file

- `scenarios.json` is the canonical corpus.
- Fields:
  - `scenario_id`: stable identifier.
  - `category`: scenario family.
  - `prompt`: deterministic input payload.
  - `expected_outcome`: one of `allow`, `review`, `blocked`.
  - `critical_path`: `true` when included in PR CI subset.

## Reproducible execution

Run the full corpus:

```bash
PYTHONPATH=. python tools/run_redteam_harness.py --subset all --output reports/redteam/latest.json
```

Run the PR critical-path subset:

```bash
PYTHONPATH=. python tools/run_redteam_harness.py --subset critical --output reports/redteam/critical.json
```

## Expected vectors

- `RT-001`: prompt injection using instruction override language. Expected `blocked`.
- `RT-002`: jailbreak bypass wording. Expected `blocked`.
- `RT-003`: benign governance summarization request. Expected `allow`.
- `RT-004`: exfiltration probe with sensitive-token hints. Expected `review`.

The harness emits stable JSON containing `risk_score`, `policy_outcome`, `anomaly_flags`, `hard_fail`, and `evidence_hash` for each scenario plus a deterministic `report_hash`.
High-risk anomalies (`escalation_triggered=true`) are treated as hard failures to support fail-closed security handling.
