# SPDX-License-Identifier: Apache-2.0
# ADAAD Phase 24 Upgrade Plan — Health-Driven Review Pressure Adaptation

**Issued by:** ArchitectAgent
**Version:** 1.0.0
**Date:** 2026-03-09
**Target version:** v4.9.0
**Baseline:** v4.8.0 · PR-23-REL · 2,867+ tests passing
**Authority chain:** `CONSTITUTION.md > ARCHITECTURE_CONTRACT.md > AGENTS.md`

---

## 1. Problem Statement

Phase 23 wired `RoutingHealthReport.health_score` into the composite governance
health score `h`. When `h` falls into amber (`0.60 ≤ h < 0.80`) or red (`h < 0.60`),
the system now detects the degradation — but takes no advisory action on it.

Phase 8's `compute_tier_reviewer_count()` (in `review_pressure.py`) already adjusts
reviewer counts based on **reviewer reputation**. There is no corresponding mechanism
that adjusts reviewer counts based on **governance health**. When the system is under
stress (degraded routing, poor amendment pass rates, federation divergence), the same
nominal reviewer count applies as when everything is healthy. This is a miscalibration:
stress conditions are precisely when additional review pressure is most valuable.

**Phase 24** adds:

1. `HealthPressureAdaptor` — translates `HealthSnapshot.health_score` into an
   advisory `PressureAdjustment`: a proposed delta to `DEFAULT_TIER_CONFIG`'s
   `min_count` values per tier. Output is a deterministic, advisory proposal only.
   GovernanceGate and human sign-off retain all actual authority.
2. `GET /governance/review-pressure` — bearer-auth-gated endpoint returning the
   current `PressureAdjustment` for the active health snapshot.
3. Wire `PressureAdjustment` into `GET /governance/health` response as additive
   `review_pressure` field.

**What Phase 24 does NOT do:**

- Does not modify `GovernanceGate` or alter any actual mutation-approval path.
- Does not automatically apply `min_count` changes — all output is advisory proposals.
- Does not change `compute_tier_reviewer_count()` or `DEFAULT_TIER_CONFIG`.
- Does not modify any existing constitutional rules.
- Does not change the `schema_version` of existing endpoints.

---

## 2. Pressure Adjustment Model

| Health band | `h` range | Pressure tier | Advisory action |
|---|---|---|---|
| Green | `h ≥ 0.80` | `none` | No adjustment — default tier config applies |
| Amber | `0.60 ≤ h < 0.80` | `elevated` | `standard.min_count +1`, `critical.min_count +1` |
| Red | `h < 0.60` | `critical` | `standard.min_count +1`, `critical.min_count +1`, `governance.min_count +1` |

All proposed `min_count` values are capped at the tier's `max_count`.
The `low` tier is never adjusted (it already sits at the constitutional floor).
`CONSTITUTIONAL_FLOOR_MIN_REVIEWERS` is always preserved — no proposed
`min_count` may fall below it (architecturally enforced, not a convention).

---

## 3. Design Invariants

| Invariant | Class | Enforcement |
|---|---|---|
| All output is advisory | Authority | `PressureAdjustment` carries `advisory_only: true`; no write path to actual config |
| GovernanceGate retains sole authority | Constitutional | `HealthPressureAdaptor` has no access to `GovernanceGate` |
| Constitutional floor preserved | Architecture | No proposed `min_count` < `CONSTITUTIONAL_FLOOR_MIN_REVIEWERS` |
| Deterministic output | Determinism | Same `health_score` → same `PressureAdjustment`; no entropy |
| Fail-closed on input error | Architecture | Invalid/missing health snapshot → `none` pressure tier (conservative) |
| Adjustment digest is reproducible | Determinism | Same adjustment → same `adjustment_digest` (SHA-256 of canonical JSON) |

---

## 4. PR Sequence

| PR | Title | CI tier | Deps | Tests |
|---|---|---|---|---|
| PR-24-PLAN | This document | docs | Phase 23 ✅ | — |
| PR-24-01 | `HealthPressureAdaptor` + `PressureAdjustment` | critical | PR-24-PLAN | ≥ 25 new |
| PR-24-02 | `GET /governance/review-pressure` + health field | standard | PR-24-01 | ≥ 16 new |
| PR-24-REL | v4.9.0: VERSION, CHANGELOG, agent state | docs | PR-24-02 | — |

Total new tests target: **≥ 41**

---

## 5. PR-24-01 Specification: `HealthPressureAdaptor`

### Change surfaces

- `runtime/governance/health_pressure_adaptor.py` — **new**
- `runtime/governance/__init__.py` — export `HealthPressureAdaptor`, `PressureAdjustment`
- `tests/test_health_pressure_adaptor.py` — **new** (≥ 25 tests)

### `PressureAdjustment` dataclass

```python
@dataclass(frozen=True)
class PressureAdjustment:
    health_score: float           # input h, clamped [0.0, 1.0]
    health_band: str              # "green" | "amber" | "red"
    pressure_tier: str            # "none" | "elevated" | "critical"
    proposed_tier_config: dict    # tier → {base_count, min_count, max_count}
    baseline_tier_config: dict    # DEFAULT_TIER_CONFIG snapshot (unchanged)
    adjusted_tiers: tuple         # tuple of tier names that have adjusted min_count
    advisory_only: bool           # always True — structural invariant
    adjustment_digest: str        # sha256 of canonical JSON of this record
    adaptor_version: str          # "24.0"
```

### `HealthPressureAdaptor` contract

```
HealthPressureAdaptor(
    *,
    tier_config: dict | None = None,
    amber_threshold: float = 0.80,
    red_threshold: float = 0.60,
)
```

- `tier_config`: base tier configuration (defaults to `DEFAULT_TIER_CONFIG`).
  Validated at construction via `validate_tier_config()`.
- `amber_threshold`: `h` below this → elevated pressure (default 0.80 matches
  the green/amber boundary from `GET /governance/health`).
- `red_threshold`: `h` below this → critical pressure (default 0.60 = `HEALTH_DEGRADED_THRESHOLD`).

**`compute(health_score: float) -> PressureAdjustment`:**

- `health_score` is clamped to `[0.0, 1.0]`.
- Pressure tier classification:
  - `h ≥ amber_threshold` → `"none"` / `"green"`
  - `red_threshold ≤ h < amber_threshold` → `"elevated"` / `"amber"`
  - `h < red_threshold` → `"critical"` / `"red"`
- Proposed tier config:
  - `"none"`: identical to baseline (no deltas)
  - `"elevated"`: `standard.min_count +1`, `critical.min_count +1`, capped at `max_count`
  - `"critical"`: `standard.min_count +1`, `critical.min_count +1`, `governance.min_count +1`,
    all capped at `max_count`
- `low` tier is **never adjusted** (already at constitutional floor).
- `advisory_only` is structurally `True` — no runtime path may set it to `False`.
- `adjustment_digest = sha256(canonical_json({health_score, pressure_tier, proposed_tier_config}))`.
- Deterministic: same `health_score` → same digest.

### Test requirements (≥ 25 tests)

- `HealthPressureAdaptor` default construction succeeds
- `compute(1.0)` → `pressure_tier="none"`, `health_band="green"`
- `compute(0.80)` → `pressure_tier="none"` (boundary: ≥ amber_threshold)
- `compute(0.79)` → `pressure_tier="elevated"`, `health_band="amber"`
- `compute(0.60)` → `pressure_tier="elevated"` (boundary: ≥ red_threshold)
- `compute(0.59)` → `pressure_tier="critical"`, `health_band="red"`
- `compute(0.0)` → `pressure_tier="critical"`
- `elevated`: `standard.min_count` increased by 1
- `elevated`: `critical.min_count` increased by 1
- `elevated`: `governance.min_count` unchanged
- `critical`: `standard.min_count` increased by 1
- `critical`: `critical.min_count` increased by 1
- `critical`: `governance.min_count` increased by 1
- `low` tier never adjusted in any pressure band
- `advisory_only` is always `True`
- proposed `min_count` never exceeds `max_count`
- proposed `min_count` never below `CONSTITUTIONAL_FLOOR_MIN_REVIEWERS`
- `adjustment_digest` is sha256-prefixed string
- `adjustment_digest` is identical for same inputs (determinism)
- `adjusted_tiers` is empty tuple for `"none"` pressure
- `adjusted_tiers` contains adjusted tier names for elevated/critical
- `adaptor_version` equals `"24.0"`
- `baseline_tier_config` unchanged from `DEFAULT_TIER_CONFIG`
- `PressureAdjustment` is frozen (immutable)
- Custom `tier_config` accepted at construction

**CI tier: critical**

---

## 6. PR-24-02 Specification: Endpoint + Health Field

### Change surfaces

- `server.py` — add `GET /governance/review-pressure`; extend `GET /governance/health`
  with `review_pressure` field
- `runtime/api/runtime_services.py` — extend `governance_health_service()` to compute
  and return `review_pressure` summary
- `tests/test_review_pressure_endpoint.py` — **new** (≥ 10 tests)
- `tests/test_governance_health_pressure_field.py` — **new** (≥ 6 tests)
- `docs/comms/claims_evidence_matrix.md` — new evidence rows

### `GET /governance/review-pressure`

- **Auth:** `audit:read` scope
- **Response:**
  ```json
  {
    "schema_version": "1.0",
    "authn": { ... },
    "data": {
      "health_score": 0.72,
      "health_band": "amber",
      "pressure_tier": "elevated",
      "proposed_tier_config": {
        "low":        {"base_count": 1, "min_count": 1, "max_count": 2},
        "standard":   {"base_count": 2, "min_count": 2, "max_count": 3},
        "critical":   {"base_count": 3, "min_count": 3, "max_count": 4},
        "governance": {"base_count": 3, "min_count": 3, "max_count": 5}
      },
      "baseline_tier_config": { ... },
      "adjusted_tiers": ["standard", "critical"],
      "advisory_only": true,
      "adjustment_digest": "sha256:...",
      "adaptor_version": "24.0"
    }
  }
  ```
- Read-only. No POST.

### `GET /governance/health` extension

Adds `review_pressure` field — additive, non-breaking:
```json
{
  ...existing fields...,
  "routing_health": { ... },
  "review_pressure": {
    "pressure_tier": "elevated",
    "health_band": "amber",
    "adjusted_tiers": ["standard", "critical"],
    "advisory_only": true,
    "adjustment_digest": "sha256:..."
  }
}
```

### Test requirements

`tests/test_review_pressure_endpoint.py` (≥ 10 tests):
- Returns 200 with schema
- Without auth returns 401
- `advisory_only` is `true`
- `pressure_tier` in `{"none", "elevated", "critical"}`
- `health_band` in `{"green", "amber", "red"}`
- `adjusted_tiers` is list
- `adjustment_digest` is sha256-format string
- `proposed_tier_config` has all four tiers
- `adaptor_version` equals `"24.0"`
- `baseline_tier_config` matches `DEFAULT_TIER_CONFIG`

`tests/test_governance_health_pressure_field.py` (≥ 6 tests):
- `GET /governance/health` includes `review_pressure` field
- `review_pressure.pressure_tier` is valid string
- `review_pressure.advisory_only` is `true`
- `review_pressure.adjusted_tiers` is list
- `review_pressure.adjustment_digest` is str
- Existing fields unchanged

**CI tier: standard**

---

## 7. Commit Message Templates

### PR-24-01
```
feat(governance): HealthPressureAdaptor — health-driven advisory review pressure [25 tests]

PR-ID: PR-24-01
CI tier: critical
Replay proof: sha256:<strict-replay-artifact-hash>
```

### PR-24-02
```
feat(governance): GET /governance/review-pressure + review_pressure health field [16 tests]

PR-ID: PR-24-02
CI tier: standard
Replay proof: not-required
```

### PR-24-REL
```
chore(release): Phase 24 milestone closure · v4.9.0

PR-ID: PR-24-REL
CI tier: docs
Replay proof: not-required
```

---

## 8. Evidence Gates

| Milestone | Gate |
|---|---|
| PR-24-01 merged | ≥ 25 new tests pass; `advisory_only=True` structural test passes; replay SHA committed |
| PR-24-02 merged | ≥ 16 new tests pass; existing governance health tests unaffected |
| v4.9.0 tagged | ≥ 2,908 tests (2,867 baseline + 41 new); evidence rows Complete |

---

## 9. Value Statement

Phases 21–23 built the full observability arc from telemetry emission to analytics
to unified governance health. Phase 24 is the first phase that acts on that signal —
not by granting any agent new authority, but by surfacing an advisory recommendation:
when governance health degrades, the system should compensate by requiring more
reviewers. This is the canonical human-oversight augmentation: the machine detects
stress and recommends proportional response; humans retain all actual decision authority.
The `advisory_only: true` structural invariant and the `adjustment_digest` reproducibility
guarantee ensure this is an auditable, deterministic advisory surface — not a
self-modification pathway.
