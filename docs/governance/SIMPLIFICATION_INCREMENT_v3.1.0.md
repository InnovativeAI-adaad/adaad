# Phase 6.1 Simplification Increment (v3.1.0)

## Purpose

Define fail-closed, measurable simplification targets that reduce complexity and
improve safety/efficiency while preserving constitutional governance guarantees.

## Canonical contract

- Contract file: `governance/simplification_targets.json`
- Validator: `scripts/validate_simplification_targets.py`
- CI integration: `.github/workflows/ci.yml` (`simplification-contract-gate`)

## Simplification KPIs

1. **Critical file complexity budgets**
   - Budgets must exist for each critical file and include:
     - `max_lines`
     - `max_fan_in`
   - Violation is fail-closed.

2. **Legacy-path reduction target**
   - Baseline legacy branch count is fixed in contract.
   - Target reduction is minimum 70%.
   - CI enforces no-regression threshold until target completion.

3. **Unified metrics-schema adoption**
   - Coverage target is 100% for enumerated metric producers.
   - Each producer must import and instantiate
     `EvolutionMetricsEmitter`.

4. **Runtime cost + mutation experiment caps**
   - Constitution resource limits are bounded by contract max caps.
   - Beast-mode mutation experiment defaults are bounded by contract max caps.

## Governance tiering and auditability

Any PR touching one or more of the following MUST be classified as governance
impact and reviewed under critical-tier gate expectations:

- `governance/simplification_targets.json`
- `scripts/validate_simplification_targets.py`
- `.github/workflows/ci.yml` simplification gate logic
- This spec and associated evidence matrix rows

CI must fail closed when simplification targets are exceeded or when contract
and implementation drift is detected.
