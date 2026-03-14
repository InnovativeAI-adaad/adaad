# Governance KPI Thresholds (Periodic Metrics Pipeline)

This document defines the governance KPI targets consumed by the periodic metrics pipeline.
The pipeline ingests structured `gate_outcome` and `blocked_emission` events and produces a weekly markdown report.

## Event schema (v1.0)

### `gate_outcome`

Required envelope fields:

- `schema_version` (`"1.0"`)
- `event_type` (`"gate_outcome"`)
- `event_timestamp` (UTC ISO-8601)
- `pr_id` (sequence identifier, e.g. `PR-PHASE65-01`)
- `payload` object

Required payload fields:

- `tier` (`0`, `1`, `2`, `3`, `M`)
- `gate_name` (gate command/label)
- `status` (`pass` / `fail`)

Optional payload fields used by KPIs:

- `blocked_reason`
- `replay_divergence` (`true`/`false`)
- `evidence_lag_hours` (float)

### `blocked_emission`

Required payload fields:

- `tier` (`0`, `1`, `2`, `3`, `M`)
- `blocked_reason`

Optional payload fields:

- `blocked_at` (UTC ISO-8601)
- `unblocked_at` (UTC ISO-8601)

## KPI definitions and targets

| KPI | Computation | Target | Alert threshold |
| --- | --- | --- | --- |
| Gate failure rates by tier | `failures / total_gate_outcomes` per tier | Tier 0/1/2/3/M each `< 10%` weekly | Tier 1 warning at `>= 15%`, spike warning at `>= +10pp` vs prior week |
| Mean time to unblock | Mean hours between `blocked_at` and `unblocked_at` | `< 24h` | Warning at `>= 48h` |
| Most common blocked reasons | Frequency ranking over `blocked_reason` | Informational trend metric | Alert if top reason repeats for 3+ consecutive weekly reports |
| Replay divergence frequency | `replay_divergence=true` count / gate outcomes | `0` preferred (fail-closed) | Warning at `>= 1` divergence/week |
| Evidence completeness lag | Mean `evidence_lag_hours` | `< 12h` | Warning at `>= 24h` |

## Weekly report + CLI usage

Generate a weekly report from the append-only ledger table:

```bash
PYTHONPATH=. python scripts/generate_governance_metrics_report.py \
  --ledger-path security/ledger/governance_metrics_events.jsonl \
  --lookback-days 7 \
  --output reports/governance/weekly_metrics.md
```

Fail CI on threshold regression alerts:

```bash
PYTHONPATH=. python scripts/generate_governance_metrics_report.py --fail-on-alerts
```

## Operational notes

- The metrics ledger is append-only JSONL: `security/ledger/governance_metrics_events.jsonl`.
- Event producers should emit at every gate completion and every blocked/unblocked lifecycle transition.
- Reports are intended to run in scheduled CI (weekly cron) and as an operator CLI.
