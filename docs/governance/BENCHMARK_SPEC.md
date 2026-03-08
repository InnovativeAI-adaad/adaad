# Governance Benchmark Specification v1

<!-- SPDX-License-Identifier: Apache-2.0 -->

## Purpose

This specification defines deterministic benchmark categories and scoring for release-candidate promotion.

## Benchmark Categories

Every run MUST emit a normalized score in `[0.0, 1.0]` for:

1. **governance_correctness**
   - Measures policy verdict correctness against a fixed governance corpus.
2. **determinism_fidelity**
   - Measures run-to-run output equality using deterministic seeds over fixed fixtures.
3. **adversarial_robustness**
   - Measures defense behavior on malicious or malformed governance payloads.
4. **federation_consistency**
   - Measures cross-node and cross-origin consensus consistency on federated fixtures.
5. **operational_mttr**
   - Measures normalized recovery speed under fixed incident scenarios.

## Determinism and Corpus Requirements

- Benchmark runners MUST use only fixed corpora checked into the repository.
- Every stochastic component MUST use an explicit deterministic seed.
- Output ordering MUST be stable (`sort_keys=True` for JSON and deterministic list sorting).

Canonical corpus path:

- `scripts/benchmark_corpus.json`

Canonical runner:

- `scripts/run_release_benchmarks.py`

## Machine-Readable Output Contract

Runner output MUST include:

- release candidate identifier
- benchmark spec version
- deterministic seed set
- per-category raw counts and normalized scores
- aggregate score summary and benchmark digest
- UTC timestamp and git commit SHA (if available)

Output artifact path (default):

- `docs/releases/benchmarks/<release_candidate>/benchmark_results.json`

Human-readable scorecard path (default):

- `docs/releases/benchmarks/<release_candidate>/scorecard.md`

## Promotion Gate: Non-Regression Rule

Promotion is blocked when any category score regresses versus baseline.

Required validator:

- `scripts/validate_benchmark_deltas.py`

Pass condition:

- All current category scores are `>=` baseline category scores.

Waiver mode (exception path):

- Regression is allowed only with an explicit signed waiver JSON.
- Waiver MUST include category list, rationale, signer identity, signer timestamp, and deterministic signature digest.

Signed waiver schema:

```json
{
  "waiver_id": "bench-waiver-<id>",
  "baseline": "<version>",
  "candidate": "<version>",
  "regressed_categories": ["operational_mttr"],
  "rationale": "<explicit risk acceptance>",
  "signed_by": "<human governor>",
  "signed_at_utc": "<ISO8601>",
  "signature": "sha256(<signed_by>|<signed_at_utc>|<rationale>|<sorted_category_csv>)"
}
```

A missing/invalid signature or category mismatch fails closed.
