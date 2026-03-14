# ADAAD Simulation Trigger Scenarios

Use `ADAAD simulate` to execute orchestration and gate evaluation in non-mutating mode.

## Trigger

```bash
python scripts/run_adaad_trigger.py "ADAAD simulate" --scenario <scenario>
```

All simulation output includes `simulation=true` markers and skips git stage/merge operations.

## Scenario Catalog

### 1) Dependency blocked

```bash
python scripts/run_adaad_trigger.py "ADAAD simulate" --scenario dependency_blocked
```

Expected status: `blocked` with `Blocked reason: dependency_unmerged`.

### 2) Evidence missing

```bash
python scripts/run_adaad_trigger.py "ADAAD simulate" --scenario evidence_missing
```

Expected status: `blocked` with Tier 3 failure and evidence-missing reason.

### 3) Tier 1 failure

```bash
python scripts/run_adaad_trigger.py "ADAAD simulate" --scenario tier1_failure
```

Expected status: `blocked` with Tier 1 failure.

### 4) Merge-ready simulation

```bash
python scripts/run_adaad_trigger.py "ADAAD simulate" --scenario merge_ready
```

Expected status: `ready` with all simulated gates passing. Even in this state, simulation mode does not stage or merge code.
