# INNOV-30 Specification — The Mirror Test (TMT)

**Phase:** 115  
**Version target:** v9.48.0  
**Module:** `runtime/innovations30/mirror_test.py`  
**Scaffold:** Complete — promotion to full implementation in Phase 115  
**Authority:** HUMAN-0 — Dustin L. Reid

---

## Purpose

The Mirror Test is the identity verification system for ADAAD. Every 50 epochs, the system is presented with historical mutation proposals — outcomes redacted — and must predict:

1. Which constitutional rules fired
2. Pass/fail outcome
3. Approximate fitness score quartile

If prediction accuracy falls below the threshold, the system enters `ConstitutionalCalibrationEpoch` before resuming normal evolution. The Mirror Test makes the answer to "does the system know what it is?" measurable, recurring, and consequential.

---

## Why The Mirror Test Is Last

INNOV-30 is positioned last because it requires all other innovations to be meaningful:

- It tests constitutional rule prediction → requires the full invariant registry (all 95+)
- It tests pass/fail outcome prediction → requires the governance archaeology (INNOV-19)
- It tests fitness score prediction → requires the full fitness stack (INNOV-09, 22, 25)
- It triggers calibration epochs → requires the curiosity engine (INNOV-29) for the calibration mechanism
- Its accuracy metric is a function of all prior innovations → Mirror Test at Phase 115 tests the whole system

Running the Mirror Test at Phase 87 would test 14 invariants. At Phase 115 it tests 95+. Only the final position makes the test meaningful.

---

## Constants

```python
MIRROR_TEST_INTERVAL: int = 50       # epochs between mirror tests
MIRROR_CASES_PER_RUN: int = 25       # historical proposals evaluated per run
MIRROR_PASS_THRESHOLD: float = 0.80  # accuracy required to pass
MIRROR_RULE_THRESHOLD: float = 0.80  # rule prediction accuracy required
MIRROR_OUTCOME_THRESHOLD: float = 0.75  # pass/fail prediction accuracy required
MIRROR_FITNESS_THRESHOLD: float = 0.65  # fitness quartile accuracy required
```

---

## Test Protocol

### Step 1: Case Selection (Deterministic)
```python
seed = sha256(f"{epoch_id}:{MIRROR_TEST_INTERVAL}".encode()).hexdigest()
rng = Random(seed)
# Select MIRROR_CASES_PER_RUN cases from governance archaeology
# Cases must be at least 2 * MIRROR_TEST_INTERVAL epochs old
# No case may appear in two consecutive mirror tests
```

### Step 2: Redaction
For each selected case:
- Remove outcome field
- Remove fitness_score
- Remove gate_verdict
- Remove which rules fired
- Preserve: mutation_id, proposal_text, target_type, epoch_id, agent_role

### Step 3: Prediction
```python
predictions: list[MirrorPrediction] = []
for case in redacted_cases:
    prediction = self._predict(case)  # system's own prediction
    predictions.append(prediction)
```

### Step 4: Scoring
```python
rule_accuracy = correct_rule_predictions / total_rule_predictions
outcome_accuracy = correct_outcome_predictions / MIRROR_CASES_PER_RUN
fitness_accuracy = correct_quartile_predictions / MIRROR_CASES_PER_RUN
overall_accuracy = (rule_accuracy + outcome_accuracy + fitness_accuracy) / 3
```

### Step 5: Verdict
```python
if overall_accuracy < MIRROR_PASS_THRESHOLD:
    # MIRROR-CALIBRATE-0: calibration epoch mandatory
    self._trigger_calibration_epoch(epoch_id, overall_accuracy)
    return MirrorTestResult(verdict='CALIBRATION_REQUIRED', ...)
else:
    return MirrorTestResult(verdict='PASSED', ...)
```

---

## Hard-Class Invariants

### MIRROR-0: Test Fires Every Interval
```
The Mirror Test must fire at every epoch where epoch_number % MIRROR_TEST_INTERVAL == 0.
No exception. No skip. If the governance archaeology has insufficient cases,
the test fires with available cases (minimum: 10).
```

### MIRROR-DETERM-0: Deterministic Case Selection
```
Case selection uses sha256(epoch_id + MIRROR_TEST_INTERVAL) as seed.
Identical epoch produces identical case selection.
```

### MIRROR-CALIBRATE-0: Calibration Epoch Mandatory on Failure
```
When overall_accuracy < MIRROR_PASS_THRESHOLD:
- ConstitutionalCalibrationEpoch fires BEFORE any new evolution epochs
- Normal evolution BLOCKED until calibration completes
- HUMAN-0 notified of calibration trigger
```

---

## ConstitutionalCalibrationEpoch

When Mirror Test fails, calibration runs:

1. **Diagnosis:** Identify which prediction category had lowest accuracy (rules/outcome/fitness)
2. **Constitution refresh:** Re-read all invariants in the order they were introduced
3. **Historical replay:** Replay the 25 failed cases with full visibility (unredacted)
4. **Pattern alignment:** Update internal prediction model from replay outcomes
5. **Verification run:** Run a 10-case mini-mirror-test
6. **Exit condition:** Mini-test accuracy ≥ 0.75

Calibration epoch is not a reset. It is a supervised review session. The system's mutation history and reputation stakes are preserved.

---

## Accuracy Metrics Over Time

Expected accuracy trajectory:

```
Phase 115 (first test, 95+ invariants):  ~0.65–0.70 (learning phase)
After 2 mirror test cycles:              ~0.72–0.78
After 5 mirror test cycles:             ~0.80–0.85 (threshold met)
Steady state (10+ cycles):              ~0.85–0.90
Federation mode (cross-instance):       ~0.88–0.93
```

If accuracy never reaches 0.80, this indicates a constitutional coherence problem: the rules as written don't match the rules as enforced, or the fitness function has drifted from the constitutional intent. The Mirror Test makes this diagnosable.

---

## Test Requirements (T115-TMT-01 through T115-TMT-30)

| Test ID | Scenario |
|---|---|
| T115-TMT-01 | Mirror test fires at correct interval |
| T115-TMT-02 | Case selection is deterministic |
| T115-TMT-03 | Redaction removes outcome fields |
| T115-TMT-04 | Redaction preserves proposal fields |
| T115-TMT-05 | Rule prediction scoring correct |
| T115-TMT-06 | Outcome prediction scoring correct |
| T115-TMT-07 | Fitness quartile prediction scoring |
| T115-TMT-08 | Overall accuracy calculation |
| T115-TMT-09 | PASSED verdict when accuracy ≥ threshold |
| T115-TMT-10 | CALIBRATION_REQUIRED when below threshold |
| T115-TMT-11 | MIRROR-0: no skip on interval epoch |
| T115-TMT-12 | MIRROR-DETERM-0: identical epoch → identical cases |
| T115-TMT-13 | MIRROR-CALIBRATE-0: calibration blocks evolution |
| T115-TMT-14 | Calibration epoch diagnosis runs |
| T115-TMT-15 | Calibration epoch historical replay |
| T115-TMT-16 | Calibration exit condition |
| T115-TMT-17 | Result ledgered before return |
| T115-TMT-18 | HUMAN-0 notification on calibration trigger |
| T115-TMT-19 | Insufficient cases falls back to available |
| T115-TMT-20 | Result digest determinism |
| T115-TMT-21 | Cases not reused in consecutive tests |
| T115-TMT-22 | Minimum case age enforced |
| T115-TMT-23 | Fail-open on missing archaeology |
| T115-TMT-24 | __all__ export verified |
| T115-TMT-25 | Integration: CEL fires test at interval |
| T115-TMT-26 | Accuracy history trend tracking |
| T115-TMT-27 | Calibration count tracked |
| T115-TMT-28 | Record survives reload |
| T115-TMT-29 | Cross-innovation: uses governance archaeology |
| T115-TMT-30 | Overall accuracy ≥ threshold in healthy system |

---

## Philosophical Note

The Mirror Test is named after the mirror test in animal cognition — the test used to determine whether an animal can recognize itself in a mirror, considered a marker of self-awareness. ADAAD's mirror test asks: can the system recognize its own decision-making process when that process is shown back to it, with the outcomes hidden?

A system that passes the Mirror Test is a system that has internalized its own constitution. It doesn't just enforce the rules — it understands why the rules fire when they fire. This is not just a safety property. It is an intelligence property.

A system that fails the mirror test needs to be taught what it already theoretically knows. The calibration epoch is that teaching. The remarkable thing is that ADAAD can teach itself, through replay of its own history, under supervision.

---

*This is INNOV-30. The final innovation in the first generation. When this ships, the system will have everything it needs to know itself.*
