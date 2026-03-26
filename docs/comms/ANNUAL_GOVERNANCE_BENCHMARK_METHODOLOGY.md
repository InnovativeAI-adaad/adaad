# Annual Governance Benchmark Methodology (v1.0)

## Purpose

Define a reproducible annual benchmark program that measures governance efficacy and operational resilience across four dimensions:

1. Policy violation catch rate
2. Replay determinism integrity
3. Governance false-positive / false-negative rates
4. Recovery time from fail-closed conditions

The benchmark is designed for two outcomes:

- **Trust evidence:** publish auditable, year-over-year governance quality metrics.
- **Demand generation:** publish anonymized, aggregated findings that position ADAAD as the category reference for governed autonomous systems.

## Scope and cadence

- **Cadence:** Annual publication (Q1 each year) covering the previous calendar year (Jan 1–Dec 31 UTC).
- **Data windows:**
  - **Primary annual window:** full prior year.
  - **Quarterly internal checkpoints:** Q1, Q2, Q3 previews for drift detection (not public unless material).
- **Benchmark populations:**
  - Production governance events (primary)
  - Deterministic replay validation runs
  - Controlled red-team policy challenge suites
  - Recovery drills from synthetic and historical fail-closed scenarios

## Data sources

- Governance decision logs (approve/reject/escalate)
- Replay verification artifacts and digest comparisons
- Policy test corpus (known-valid and known-violating cases)
- Incident and fail-closed lifecycle telemetry
- Runbook execution timestamps for recovery completion

All source datasets must be versioned, immutable once frozen for annual reporting, and signed with a report manifest digest.

## Metric definitions

### 1) Policy violation catch rate

**Goal:** Measure how often governance controls correctly detect true policy violations.

- **Definition:**
  - `catch_rate = true_violations_caught / total_true_violations`
- **Numerator:** Cases labeled as true policy violations that were blocked or escalated by governance.
- **Denominator:** All benchmark cases labeled as true policy violations by adjudication.
- **Target reporting:** overall rate + rate by violation class (security, constitutional, replay, evidence, policy-scope).

### 2) Replay determinism integrity

**Goal:** Measure reproducibility under strict replay constraints.

- **Definition:**
  - `replay_integrity = deterministic_replay_matches / total_replay_verification_runs`
- **Match condition:** canonical digest equality on expected replay artifacts (including order-sensitive hashes where applicable).
- **Failure classification:** non-deterministic output, missing artifact, schema drift, environment/config mismatch.
- **Target reporting:** integrity rate, failure-class distribution, and top divergence signatures.

### 3) Governance false-positive / false-negative rates

**Goal:** Quantify decision quality and calibration.

- **Definitions:**
  - `false_positive_rate = false_positives / total_known_valid_cases`
  - `false_negative_rate = false_negatives / total_known_violation_cases`
- **Label truth source:** dual-review adjudication (policy + security owner) with tie-break protocol.
- **Target reporting:** global FPR/FNR plus per-policy-family breakdown.

### 4) Recovery time from fail-closed conditions

**Goal:** Track operational resilience and runbook effectiveness.

- **Definition:**
  - `recovery_time_minutes = time_of_restored_healthy_state - time_of_fail_closed_trigger`
- **Restored healthy state criteria:**
  - fail-closed condition cleared,
  - governing checks green,
  - replay determinism re-verified for affected surface,
  - evidence row closure complete (if required).
- **Target reporting:** median, p90, p95, max, and segmented by incident class.

## Benchmark design

### A) Ground-truth corpus construction

- Maintain a versioned benchmark corpus with:
  - known-valid scenarios,
  - known-violation scenarios,
  - edge cases (ambiguous/near-threshold),
  - adversarial injections.
- Freeze corpus at annual cutoff and compute corpus digest.
- Ensure class balance and document any imbalance.

### B) Sampling and stratification

- Stratify by:
  - policy domain,
  - environment type,
  - severity tier,
  - runtime subsystem.
- Use weighted aggregation so high-volume classes do not hide high-risk low-volume classes.
- Publish both macro-average and weighted-average metrics.

### C) Statistical treatment

- Report point estimates with 95% confidence intervals (Wilson interval for proportions).
- Minimum sample threshold for any published segment:
  - if `n < threshold`, suppress segment or aggregate upward to preserve quality and anonymity.
- Include prior-year deltas with absolute and relative changes.

### D) Validation controls

- Recompute metrics independently in a second pipeline and compare digests.
- Require deterministic rerun producing identical annual summary artifact.
- Block publication on mismatch until resolved.

## Annual publication package

Publish one benchmark package per year containing:

1. **Executive brief** (category-facing summary)
2. **Methodology appendix** (this framework + any yearly deltas)
3. **Metric tables** (overall + segmented)
4. **Anonymization statement** (privacy protections)
5. **Change log** (method or taxonomy changes from prior year)

Suggested public artifacts:

- `docs/comms/benchmarks/<year>/ANNUAL_GOVERNANCE_BENCHMARK.md`
- `docs/comms/benchmarks/<year>/ANNUAL_GOVERNANCE_BENCHMARK_METHODS.md`
- `docs/comms/benchmarks/<year>/ANNUAL_GOVERNANCE_BENCHMARK_SUMMARY.json`

## Anonymization and aggregation policy

To support category authority without exposing sensitive customer/operator details:

- Remove all direct identifiers (org, repo, operator, environment IDs).
- Apply k-anonymity thresholds for segment publication.
- Bucket rare categories into “Other” when threshold not met.
- Publish only aggregate metrics and high-level trend narratives.
- Redact signatures/paths that could reveal private architecture details.
- Maintain a non-public internal mapping ledger for auditability.

## Demand-generation framing

Public report narrative should emphasize:

- Year-over-year quality improvement trends
- Comparative resilience under fail-closed governance
- Determinism integrity as a trust differentiator
- Practical adoption lessons and benchmark-backed playbooks

This creates a repeatable “category scoreboard” asset for:

- Analyst and media briefings
- Enterprise security/governance buyer enablement
- Partner ecosystem co-marketing

## Governance and ownership

- **Primary owner:** Governance + Reliability.
- **Reviewers:** Security, Policy, Product Marketing, Legal.
- **Approval gate:** publication requires signed annual attestation from Governance and Security leads.

## First publication readiness checklist

- Benchmark corpus frozen and digested
- Annual metric computation reproducible
- Confidence intervals computed and peer-reviewed
- Privacy/anonymization checks signed off
- Public narrative + technical appendix aligned
- Final package approved and published
