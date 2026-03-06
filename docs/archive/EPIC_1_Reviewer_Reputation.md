# EPIC 1 · Reviewer Reputation & Calibration Loop

![Status: Complete](https://img.shields.io/badge/Status-Complete-2ea043)
![Milestone: ADAAD-7](https://img.shields.io/badge/Milestone-ADAAD--7-2ea043)
![Constitution: v0.3.0](https://img.shields.io/badge/Constitution-v0.3.0-f97316)

> Epoch-scoped reviewer reputation scoring that calibrates panel size — never authority or voting.

**Last reviewed:** 2026-03-05 · **Merged:** 2026-03-05 · **PRs:** PR-7-01 → PR-7-05

---

## Summary

ADAAD-7 introduces a reviewer reputation engine that informs how many reviewers a mutation requires, based on a 4-dimension weighted composite score computed per epoch. Reviewer authority, voting weight, and approval semantics are not modified.

---

## Architectural Invariants

| Invariant | Enforcement |
|---|---|
| Constitutional floor ≥ 1 human reviewer | Architecturally enforced in `review_pressure.py` across all tiers and all reputation scores |
| Epoch weight snapshot | Scoring weights snapshotted per epoch; replay binds to epoch-scoped snapshot |
| Score version binding | `scoring_algorithm_version` recorded in every `reviewer_action_outcome` ledger event |
| Deterministic scoring | Pure functions; no entropy sources; replay-identical |
| Advisory rule only | `reviewer_calibration` rule is `severity: advisory` — never blocking |

---

## Reputation Score Dimensions

| Dimension | Weight | Description |
|---|---|---|
| `override_rate` | 0.30 | How often this reviewer's decisions are overridden by higher authority |
| `long_term_mutation_impact` | 0.30 | Aggregate quality of mutations this reviewer approved (post-execution outcome) |
| `latency` | 0.20 | Responsiveness within the defined SLA window |
| `governance_alignment` | 0.20 | Adherence to constitutional and governance expectations |

Composite score range: `[0.0, 1.0]`. Scores are epoch-scoped and not cumulated across epochs.

---

## Tier Calibration

| Tier | Base | Min | Max | Notes |
|---|---|---|---|---|
| `low` | 1 | 1 | 2 | Constitutional floor enforced |
| `standard` | 2 | 1 | 3 | Constitutional floor enforced |
| `critical` | 3 | 2 | 4 | Constitutional floor enforced |
| `governance` | 3 | 3 | 5 | Constitutional floor enforced |

- **High reputation** (score ≥ 0.80): panel count may decrease toward `min_count`.
- **Low reputation** (score ≤ 0.40): panel count may increase toward `max_count`.
- `constitutional_floor_enforced: true` is always present in every calibration output.

---

## Deliverables

### PR-7-01 · Ledger extension

- `schemas/pr_lifecycle_event.v1.json` — `reviewer_action_outcome` event type with required and optional calibration fields.
- `runtime/governance/pr_lifecycle_event_contract.py` — builder with constraint enforcement.
- 25 contract tests.

### PR-7-02 · Reputation scoring engine

- `runtime/governance/reviewer_reputation.py` — epoch-scoped, version-bound composite scorer.
  - `SCORING_ALGORITHM_VERSION = "1.0"`
  - `DEFAULT_EPOCH_WEIGHTS` — validated, snapshotted per epoch.
  - `compute_reviewer_reputation()` — pure, deterministic, epoch-scoped.
  - `compute_epoch_reputation_batch()` — multi-reviewer batch compute.
- 23 scoring tests.

### PR-7-03 · Tier calibration + constitutional floor

- `runtime/governance/review_pressure.py` — maps `(tier, composite_score)` → `adjusted_count`.
  - `CONSTITUTIONAL_FLOOR_MIN_REVIEWERS = 1` — structurally enforced.
  - `compute_tier_reviewer_count()` — clamped to `[min_count, max_count]`.
  - `compute_panel_calibration()` — multi-tier batch.
- 23 calibration tests including exhaustive floor coverage across all tiers and scores.

### PR-7-04 · Constitution v0.3.0

- `runtime/governance/constitution.yaml` — `reviewer_calibration` advisory rule added.
- `runtime/constitution.py` — `CONSTITUTION_VERSION` bumped `0.2.0 → 0.3.0`.
- 38 constitution policy tests updated.

### PR-7-05 · Aponi endpoint + panel

- `server.py` — `GET /governance/reviewer-calibration` — bearer-auth gated (`audit:read` scope).
- `ui/aponi_dashboard.py` — `_reviewer_reputation_panel()` wired into `state_payload`.
- 5 endpoint and dashboard E2E tests.

---

## Test Summary

| PR | Tests | Coverage |
|---|---|---|
| PR-7-01 | 25 | Ledger contract, builder constraints, digest determinism |
| PR-7-02 | 23 | Weight validation, epoch scoping, composite scoring, version binding |
| PR-7-03 | 23 | Config validation, floor invariant, score clamping, panel batch |
| PR-7-04 | 38 | Constitution policy, version literals |
| PR-7-05 | 13 | Auth gate, schema, explicit reviewer IDs, panel in state, floor in output |
| **Total** | **76** | **All passing** |

---

## Related documents

- [Milestone Roadmap](MILESTONE_ROADMAP_ADAAD6-9.md)
- [Constitution](docs/CONSTITUTION.md) — `reviewer_calibration` rule definition
- [Governance mutation lifecycle](docs/governance/mutation_lifecycle.md)
- [Claims-evidence matrix](docs/comms/claims_evidence_matrix.md)
