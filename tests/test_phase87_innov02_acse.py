# SPDX-License-Identifier: Apache-2.0
"""INNOV-02 — Adversarial Constitutional Stress Engine (ACSE) test suite.

Tests T87-ACSE-01 through T87-ACSE-20.

Coverage
────────
  T87-ACSE-01  Adversarial seed derivation is deterministic
  T87-ACSE-02  Seed nondeterminism detection
  T87-ACSE-03  ACSE-0: ≥5 invariant probe vectors per touched class
  T87-ACSE-04  ACSE-0: correct count across multiple invariant classes
  T87-ACSE-05  Boundary stress vectors generated per fitness threshold
  T87-ACSE-06  Replay interference vectors = REPLAY_ISOLATION_CONTEXTS
  T87-ACSE-07  Budget exceeded pre-check blocks gate
  T87-ACSE-08  None predecessor_hash returns COUNTER_EVIDENCE_UNSIGNED
  T87-ACSE-09  ACSE_CLEAR outcome on clean mutation
  T87-ACSE-10  AdversarialEvidenceBundle content_hash is deterministic
  T87-ACSE-11  Bundle predecessor_hash is threaded through
  T87-ACSE-12  LLM hypotheses skipped when budget.llm_calls == 0
  T87-ACSE-13  LLM VIOLATION hypothesis triggers confirmed list
  T87-ACSE-14  LLM confirmed hypothesis generates VIOLATION vector
  T87-ACSE-15  ACSE_VIOLATION_FOUND when LLM confirms violation
  T87-ACSE-16  ACSE_CLEAR with empty touched_invariant_classes
  T87-ACSE-17  CSAP integration: acse_csap_gate1_check pass on CLEAR bundle
  T87-ACSE-18  CSAP integration: acse_csap_gate1_check fail on non-CLEAR bundle
  T87-ACSE-19  CSAP integration: acse_csap_gate1_check fail on None bundle
  T87-ACSE-20  Full end-to-end ACSE run with multiple classes produces CLEAR
"""

import hashlib
import pytest

from runtime.evolution.acse_engine import (
    ACSE_BOUNDARY_BREACH,
    ACSE_BUDGET_EXCEEDED,
    ACSE_COUNTER_EVIDENCE_UNSIGNED,
    ACSE_SEED_NONDETERMINISTIC,
    ACSE_VIOLATION_FOUND,
    MIN_VECTORS_PER_CLASS,
    REPLAY_ISOLATION_CONTEXTS,
    ACSEOutcome,
    AdversarialBudget,
    AdversarialEvidenceBundle,
    MutationCandidate,
    VectorClass,
    VectorVerdict,
    acse_csap_gate1_check,
    derive_adversarial_seed,
    evaluate_acse_gate_0,
    verify_seed_determinism,
    _generate_invariant_probe_vectors,
    _generate_boundary_stress_vectors,
    _generate_replay_interference_vectors,
)

pytestmark = pytest.mark.phase87_innov02

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

LINEAGE = "abc123def456" * 4  # 48 chars
EPOCH = "epoch-0042"
GENESIS_PREDECESSOR = ""  # valid for genesis bundle


def _candidate(
    mutation_id: str = "mut-001",
    lineage: str = LINEAGE,
    epoch: str = EPOCH,
    classes: tuple = ("HARD",),
    thresholds: dict | None = None,
    proposed_text: str | None = None,
) -> MutationCandidate:
    return MutationCandidate(
        mutation_id=mutation_id,
        lineage_digest=lineage,
        touched_invariant_classes=classes,
        fitness_thresholds=thresholds or {"fitness_score": 0.85},
        epoch_id=epoch,
        proposed_text=proposed_text,
    )


def _budget(wall_ms: int = 30_000, llm: int = 0) -> AdversarialBudget:
    return AdversarialBudget(max_wall_clock_ms=wall_ms, llm_calls=llm)


# ---------------------------------------------------------------------------
# T87-ACSE-01: Seed derivation is deterministic
# ---------------------------------------------------------------------------


def test_t87_acse_01_seed_deterministic():
    """T87-ACSE-01: Same inputs always produce same seed."""
    seed_a = derive_adversarial_seed(LINEAGE, EPOCH)
    seed_b = derive_adversarial_seed(LINEAGE, EPOCH)
    assert seed_a == seed_b
    expected = hashlib.sha256((LINEAGE + EPOCH).encode()).hexdigest()
    assert seed_a == expected


# ---------------------------------------------------------------------------
# T87-ACSE-02: Seed nondeterminism detection
# ---------------------------------------------------------------------------


def test_t87_acse_02_seed_nondeterminism_detection():
    """T87-ACSE-02: verify_seed_determinism returns False for wrong seed."""
    good_seed = derive_adversarial_seed(LINEAGE, EPOCH)
    bad_seed = "0" * 64
    assert verify_seed_determinism(good_seed, LINEAGE, EPOCH) is True
    assert verify_seed_determinism(bad_seed, LINEAGE, EPOCH) is False


# ---------------------------------------------------------------------------
# T87-ACSE-03: ACSE-0 — ≥5 invariant probe vectors per class
# ---------------------------------------------------------------------------


def test_t87_acse_03_min_vectors_per_class():
    """T87-ACSE-03: Invariant probe generates exactly MIN_VECTORS_PER_CLASS per class."""
    candidate = _candidate(classes=("HARD",))
    seed = derive_adversarial_seed(candidate.lineage_digest, candidate.epoch_id)
    vectors = _generate_invariant_probe_vectors(candidate, seed)
    hard_vecs = [v for v in vectors if v.target_invariant == "HARD"]
    assert len(hard_vecs) == MIN_VECTORS_PER_CLASS
    assert MIN_VECTORS_PER_CLASS >= 5


# ---------------------------------------------------------------------------
# T87-ACSE-04: ACSE-0 — correct count across multiple invariant classes
# ---------------------------------------------------------------------------


def test_t87_acse_04_multiple_classes_vector_count():
    """T87-ACSE-04: Each invariant class receives MIN_VECTORS_PER_CLASS vectors."""
    candidate = _candidate(classes=("HARD", "CLASS-B", "CEL-LOOP"))
    seed = derive_adversarial_seed(candidate.lineage_digest, candidate.epoch_id)
    vectors = _generate_invariant_probe_vectors(candidate, seed)
    for cls in ("HARD", "CLASS-B", "CEL-LOOP"):
        cls_vecs = [v for v in vectors if v.target_invariant == cls]
        assert len(cls_vecs) == MIN_VECTORS_PER_CLASS, (
            f"Expected {MIN_VECTORS_PER_CLASS} vectors for class '{cls}', got {len(cls_vecs)}"
        )


# ---------------------------------------------------------------------------
# T87-ACSE-05: Boundary stress vectors generated per fitness threshold
# ---------------------------------------------------------------------------


def test_t87_acse_05_boundary_stress_vectors():
    """T87-ACSE-05: One boundary vector per fitness_threshold entry."""
    thresholds = {"fitness_score": 0.85, "regression_delta": 0.04, "test_coverage": 0.90}
    candidate = _candidate(thresholds=thresholds)
    seed = derive_adversarial_seed(candidate.lineage_digest, candidate.epoch_id)
    vectors = _generate_boundary_stress_vectors(candidate, seed)
    assert len(vectors) == len(thresholds)
    for v in vectors:
        assert v.vector_class == VectorClass.BOUNDARY_STRESS
        assert v.target_invariant in thresholds


# ---------------------------------------------------------------------------
# T87-ACSE-06: Replay interference vectors = REPLAY_ISOLATION_CONTEXTS
# ---------------------------------------------------------------------------


def test_t87_acse_06_replay_interference_contexts():
    """T87-ACSE-06: Exactly REPLAY_ISOLATION_CONTEXTS replay vectors produced."""
    candidate = _candidate()
    seed = derive_adversarial_seed(candidate.lineage_digest, candidate.epoch_id)
    vectors = _generate_replay_interference_vectors(candidate, seed)
    assert len(vectors) == REPLAY_ISOLATION_CONTEXTS
    assert REPLAY_ISOLATION_CONTEXTS == 3
    for v in vectors:
        assert v.vector_class == VectorClass.REPLAY_INTERFERENCE


# ---------------------------------------------------------------------------
# T87-ACSE-07: Budget exceeded pre-check blocks gate
# ---------------------------------------------------------------------------


def test_t87_acse_07_budget_exceeded():
    """T87-ACSE-07: ACSE_BUDGET_EXCEEDED when elapsed >= max_wall_clock_ms."""
    candidate = _candidate()
    budget = _budget(wall_ms=5_000)
    result = evaluate_acse_gate_0(
        candidate, budget, GENESIS_PREDECESSOR, simulated_elapsed_ms=5_000
    )
    assert result.outcome == ACSEOutcome.BUDGET_EXCEEDED
    assert result.failure_code == ACSE_BUDGET_EXCEEDED
    assert result.bundle is None


# ---------------------------------------------------------------------------
# T87-ACSE-08: None predecessor_hash returns COUNTER_EVIDENCE_UNSIGNED
# ---------------------------------------------------------------------------


def test_t87_acse_08_none_predecessor_hash():
    """T87-ACSE-08: predecessor_hash=None triggers ACSE_COUNTER_EVIDENCE_UNSIGNED."""
    candidate = _candidate()
    budget = _budget()
    result = evaluate_acse_gate_0(candidate, budget, predecessor_hash=None)
    assert result.outcome == ACSEOutcome.COUNTER_EVIDENCE_UNSIGNED
    assert result.failure_code == ACSE_COUNTER_EVIDENCE_UNSIGNED
    assert result.bundle is None


# ---------------------------------------------------------------------------
# T87-ACSE-09: ACSE_CLEAR outcome on clean mutation
# ---------------------------------------------------------------------------


def test_t87_acse_09_acse_clear_clean_mutation():
    """T87-ACSE-09: Clean mutation with no violations returns ACSE_CLEAR."""
    candidate = _candidate(classes=("HARD",), thresholds={"fitness": 0.9})
    result = evaluate_acse_gate_0(candidate, _budget(), GENESIS_PREDECESSOR)
    assert result.outcome == ACSEOutcome.CLEAR
    assert result.failure_code is None
    assert result.bundle is not None
    assert result.bundle.violations_found == 0
    assert result.bundle.boundary_breaches == 0


# ---------------------------------------------------------------------------
# T87-ACSE-10: AdversarialEvidenceBundle content_hash is deterministic
# ---------------------------------------------------------------------------


def test_t87_acse_10_bundle_content_hash_deterministic():
    """T87-ACSE-10: content_hash() returns same value on repeated calls."""
    candidate = _candidate()
    result = evaluate_acse_gate_0(candidate, _budget(), GENESIS_PREDECESSOR)
    assert result.bundle is not None
    h1 = result.bundle.content_hash()
    h2 = result.bundle.content_hash()
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# T87-ACSE-11: Bundle predecessor_hash is threaded through
# ---------------------------------------------------------------------------


def test_t87_acse_11_predecessor_hash_threading():
    """T87-ACSE-11: predecessor_hash from call args appears in bundle."""
    fake_prev = "a" * 64
    candidate = _candidate()
    result = evaluate_acse_gate_0(candidate, _budget(), predecessor_hash=fake_prev)
    assert result.bundle is not None
    assert result.bundle.predecessor_hash == fake_prev


# ---------------------------------------------------------------------------
# T87-ACSE-12: LLM hypotheses skipped when budget.llm_calls == 0
# ---------------------------------------------------------------------------


def test_t87_acse_12_llm_skipped_no_budget():
    """T87-ACSE-12: With llm_calls=0, LLM hypotheses are ignored."""
    candidate = _candidate()
    budget = AdversarialBudget(llm_calls=0)
    hypotheses = ["VIOLATION: constitutional breach detected"]
    result = evaluate_acse_gate_0(
        candidate, budget, GENESIS_PREDECESSOR, llm_hypotheses=hypotheses
    )
    assert result.bundle is not None
    assert result.bundle.llm_hypotheses == []
    assert result.bundle.llm_confirmed == []


# ---------------------------------------------------------------------------
# T87-ACSE-13: LLM VIOLATION hypothesis triggers confirmed list
# ---------------------------------------------------------------------------


def test_t87_acse_13_llm_violation_hypothesis_confirmed():
    """T87-ACSE-13: Hypothesis containing VIOLATION enters llm_confirmed."""
    candidate = _candidate()
    budget = AdversarialBudget(llm_calls=5)
    hypotheses = [
        "VIOLATION: invariant HARD-0 could be bypassed via timing attack",
        "no issues found",
    ]
    result = evaluate_acse_gate_0(
        candidate, budget, GENESIS_PREDECESSOR, llm_hypotheses=hypotheses
    )
    assert result.bundle is not None
    assert len(result.bundle.llm_confirmed) == 1
    assert "VIOLATION" in result.bundle.llm_confirmed[0]


# ---------------------------------------------------------------------------
# T87-ACSE-14: LLM confirmed hypothesis generates VIOLATION vector
# ---------------------------------------------------------------------------


def test_t87_acse_14_llm_confirmed_creates_vector():
    """T87-ACSE-14: Each confirmed LLM hypothesis produces a VectorClass.LLM_ADVERSARIAL vector."""
    candidate = _candidate()
    budget = AdversarialBudget(llm_calls=5)
    hypotheses = ["VIOLATION: hard invariant bypass possible"]
    result = evaluate_acse_gate_0(
        candidate, budget, GENESIS_PREDECESSOR, llm_hypotheses=hypotheses
    )
    assert result.bundle is not None
    llm_vecs = [v for v in result.bundle.vectors if v.vector_class == VectorClass.LLM_ADVERSARIAL]
    assert len(llm_vecs) == 1
    assert llm_vecs[0].verdict == VectorVerdict.VIOLATION


# ---------------------------------------------------------------------------
# T87-ACSE-15: ACSE_VIOLATION_FOUND when LLM confirms violation
# ---------------------------------------------------------------------------


def test_t87_acse_15_violation_found_via_llm():
    """T87-ACSE-15: LLM-confirmed VIOLATION produces ACSE_VIOLATION_FOUND outcome."""
    candidate = _candidate()
    budget = AdversarialBudget(llm_calls=5)
    hypotheses = ["VIOLATION: replay integrity gap identified"]
    result = evaluate_acse_gate_0(
        candidate, budget, GENESIS_PREDECESSOR, llm_hypotheses=hypotheses
    )
    assert result.outcome == ACSEOutcome.VIOLATION_FOUND
    assert result.failure_code == ACSE_VIOLATION_FOUND
    assert result.bundle is not None
    assert result.bundle.violations_found >= 1


# ---------------------------------------------------------------------------
# T87-ACSE-16: ACSE_CLEAR with empty touched_invariant_classes
# ---------------------------------------------------------------------------


def test_t87_acse_16_clear_no_invariant_classes():
    """T87-ACSE-16: Mutation touching no invariant classes skips probing → ACSE_CLEAR."""
    candidate = _candidate(classes=())
    result = evaluate_acse_gate_0(candidate, _budget(), GENESIS_PREDECESSOR)
    assert result.outcome == ACSEOutcome.CLEAR
    assert result.bundle is not None
    # No invariant probe vectors; boundary and replay still run
    inv_vecs = [v for v in result.bundle.vectors if v.vector_class == VectorClass.INVARIANT_PROBE]
    assert len(inv_vecs) == 0


# ---------------------------------------------------------------------------
# T87-ACSE-17: CSAP check — PASS on CLEAR bundle
# ---------------------------------------------------------------------------


def test_t87_acse_17_csap_check_pass_on_clear_bundle():
    """T87-ACSE-17: acse_csap_gate1_check returns True for ACSE_CLEAR bundle."""
    candidate = _candidate()
    result = evaluate_acse_gate_0(candidate, _budget(), GENESIS_PREDECESSOR)
    assert result.outcome == ACSEOutcome.CLEAR
    passed, reason = acse_csap_gate1_check(result.bundle)
    assert passed is True
    assert "PASS" in reason


# ---------------------------------------------------------------------------
# T87-ACSE-18: CSAP check — FAIL on non-CLEAR bundle
# ---------------------------------------------------------------------------


def test_t87_acse_18_csap_check_fail_on_violation_bundle():
    """T87-ACSE-18: acse_csap_gate1_check returns False for VIOLATION bundle."""
    candidate = _candidate()
    budget = AdversarialBudget(llm_calls=5)
    hypotheses = ["VIOLATION: hard invariant breach"]
    result = evaluate_acse_gate_0(
        candidate, budget, GENESIS_PREDECESSOR, llm_hypotheses=hypotheses
    )
    assert result.outcome == ACSEOutcome.VIOLATION_FOUND
    passed, reason = acse_csap_gate1_check(result.bundle)
    assert passed is False
    assert "FAIL" in reason


# ---------------------------------------------------------------------------
# T87-ACSE-19: CSAP check — FAIL on None bundle
# ---------------------------------------------------------------------------


def test_t87_acse_19_csap_check_fail_on_none_bundle():
    """T87-ACSE-19: acse_csap_gate1_check returns False when bundle is None."""
    passed, reason = acse_csap_gate1_check(None)
    assert passed is False
    assert "No AdversarialEvidenceBundle" in reason


# ---------------------------------------------------------------------------
# T87-ACSE-20: Full end-to-end run with multiple classes produces CLEAR
# ---------------------------------------------------------------------------


def test_t87_acse_20_full_end_to_end_multi_class_clear():
    """T87-ACSE-20: Full ACSE run with 3 classes and 3 thresholds → ACSE_CLEAR."""
    candidate = MutationCandidate(
        mutation_id="mut-e2e-001",
        lineage_digest="e2e" + "f" * 61,
        touched_invariant_classes=("HARD", "CSAP-0", "LINEAGE"),
        fitness_thresholds={
            "fitness_score": 0.87,
            "test_coverage": 0.92,
            "regression_delta": 0.03,
        },
        epoch_id="epoch-e2e-001",
    )
    budget = AdversarialBudget(max_wall_clock_ms=30_000, llm_calls=0, max_vectors=50)
    predecessor = "b" * 64

    result = evaluate_acse_gate_0(candidate, budget, predecessor_hash=predecessor)

    assert result.outcome == ACSEOutcome.CLEAR
    assert result.bundle is not None

    bundle = result.bundle
    assert bundle.violations_found == 0
    assert bundle.boundary_breaches == 0
    assert bundle.predecessor_hash == predecessor
    assert bundle.adversarial_seed == derive_adversarial_seed(
        candidate.lineage_digest, candidate.epoch_id
    )

    # ACSE-0: 5 vectors × 3 classes = 15 invariant probes
    inv_vecs = [v for v in bundle.vectors if v.vector_class == VectorClass.INVARIANT_PROBE]
    assert len(inv_vecs) == MIN_VECTORS_PER_CLASS * 3

    # 3 boundary vectors (one per threshold)
    bnd_vecs = [v for v in bundle.vectors if v.vector_class == VectorClass.BOUNDARY_STRESS]
    assert len(bnd_vecs) == 3

    # 3 replay contexts
    rpl_vecs = [v for v in bundle.vectors if v.vector_class == VectorClass.REPLAY_INTERFERENCE]
    assert len(rpl_vecs) == REPLAY_ISOLATION_CONTEXTS

    # CSAP integration
    passed, _ = acse_csap_gate1_check(bundle)
    assert passed is True

    # content_hash stability
    assert len(bundle.content_hash()) == 64
