# Performance Baselines by SKU

This document defines target performance bands for the deterministic benchmark scenario suite in `scripts/bench_performance_scenarios.py`.

## Scenario coverage

The benchmark suite records versioned artifacts for four scenarios:

1. Replay verification latency
2. Governance gate throughput
3. API p95 latency under concurrent load
4. Ledger growth and retrieval performance

Artifacts are written under:

- `docs/releases/performance/sku-performance-scenarios/<baseline_version>/`

Each run emits per-SKU JSON + Markdown artifacts that include:

- raw samples/rollups for each scenario,
- pass/fail evaluation against the SKU target band,
- generation timestamp and benchmark version.

## Target bands by SKU

Target bands are aligned to offer expectations in `docs/product/SKUS.md`.

| SKU | Replay verification latency (p95, ms) | Governance gate throughput (min eval/s) | API concurrent load latency (p95, ms) | Ledger retrieval (last 100 rows p95, ms) |
|---|---:|---:|---:|---:|
| Community | <= 2.5 | >= 180,000 | <= 40.0 | <= 3.0 |
| Team | <= 1.8 | >= 220,000 | <= 28.0 | <= 2.5 |
| Enterprise | <= 1.5 | >= 250,000 | <= 22.0 | <= 2.0 |

## Execution

Run all SKUs:

```bash
PYTHONPATH=. python scripts/bench_performance_scenarios.py --sku all --version v1
```

Run one SKU:

```bash
PYTHONPATH=. python scripts/bench_performance_scenarios.py --sku enterprise --version v1
```

## Versioning policy

- Bump `--version` when scenario logic or pass/fail thresholds change.
- Keep prior version directories immutable for auditability.
- Publish any threshold changes in release notes and update this document in the same PR.
