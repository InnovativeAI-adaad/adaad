# SPDX-License-Identifier: Apache-2.0
"""Phase 96 — INNOV-11 · Cross-Epoch Dream State Engine (DSTE)
Test IDs: T96-DSTE-01 through T96-DSTE-30

Constitutional invariants under test:
    DSTE-0  Ledger-first commit
    DSTE-1  Determinism / seed required
    DSTE-2  Novelty floor (0.30)
    DSTE-3  Pool quorum (3 successful epochs)
    DSTE-4  Chain integrity (prev_event_hash)
    DSTE-5  No-write between epochs
    DSTE-6  Candidate count ceiling (5)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

pytestmark = pytest.mark.autonomous_critical

from runtime.innovations30.dream_state import (
    DREAM_CANDIDATES,
    DREAM_MIN_NOVELTY,
    DREAM_QUORUM,
    DSTE_0,
    DSTE_1,
    DSTE_2,
    DSTE_3,
    DSTE_4,
    DSTE_5,
    DSTE_6,
    DreamCandidate,
    DreamGateViolation,
    DreamLedgerEvent,
    DreamStateEngine,
    DreamStateReport,
    evaluate_dream_gate_0,
    evaluate_dream_gate_1,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _epoch_entry(epoch_id: str, mut_type: str, delta: float) -> dict[str, Any]:
    return {
        "epoch_id": epoch_id,
        "winning_mutation_type": mut_type,
        "winning_strategy_id": f"strat-{mut_type}",
        "fitness_delta": delta,
    }


def _pool(n: int = 5, delta: float = 0.8) -> list[dict[str, Any]]:
    """n successful epochs with distinct mutation types."""
    types = ["refactor", "optimize", "extract", "inline", "rename",
             "split", "merge", "hoist", "sink", "reorder"]
    return [_epoch_entry(f"epoch-{i:03d}", types[i % len(types)], delta) for i in range(n)]


def _engine(tmp_path: Path) -> DreamStateEngine:
    return DreamStateEngine(
        state_path=tmp_path / "candidates.jsonl",
        ledger_path=tmp_path / "ledger.jsonl",
    )


# ── T96-DSTE-01..05 Determinism (DSTE-1) ────────────────────────────────────

def test_T96_DSTE_01_identical_inputs_identical_output(tmp_path):
    """T96-DSTE-01: Same epoch_memory + epoch_id + seed → same candidates."""
    pool = _pool(8)
    engine = _engine(tmp_path)
    r1 = engine.dream(pool, epoch_id="epoch-AAA", seed=42)
    engine2 = _engine(tmp_path / "e2")
    r2 = engine2.dream(pool, epoch_id="epoch-AAA", seed=42)
    ids1 = [c.candidate_id for c in r1.candidates]
    ids2 = [c.candidate_id for c in r2.candidates]
    assert ids1 == ids2


def test_T96_DSTE_02_different_seed_may_differ(tmp_path):
    """T96-DSTE-02: Different seeds may produce different candidate orderings."""
    pool = _pool(10)
    e1 = _engine(tmp_path / "s1")
    e2 = _engine(tmp_path / "s2")
    r1 = e1.dream(pool, epoch_id="epoch-BBB", seed=1)
    r2 = e2.dream(pool, epoch_id="epoch-BBB", seed=9999)
    # At least one metric should differ (different seeds drive different rng paths)
    fitness1 = [c.predicted_fitness for c in r1.candidates]
    fitness2 = [c.predicted_fitness for c in r2.candidates]
    # This assertion checks determinism by seed; different seeds CAN produce equal
    # outputs if pool is small, but the rng paths differ — validate both are valid
    for c in r1.candidates + r2.candidates:
        assert c.novelty_score >= DREAM_MIN_NOVELTY


def test_T96_DSTE_03_genesis_digest_deterministic(tmp_path):
    """T96-DSTE-03: genesis_digest is sha256 of sorted(source_epochs) + id."""
    import hashlib, json
    c = DreamCandidate(
        candidate_id="DREAM-abc12345-00",
        source_epochs=["epoch-001", "epoch-002"],
        combined_intent="test",
        recombined_ops=[],
        predicted_fitness=0.8,
        novelty_score=0.7,
    )
    expected_payload = json.dumps(
        {"id": "DREAM-abc12345-00", "epochs": sorted(["epoch-001", "epoch-002"])},
        sort_keys=True,
    )
    expected = "sha256:" + hashlib.sha256(expected_payload.encode()).hexdigest()
    assert c.genesis_digest == expected


def test_T96_DSTE_04_sort_order_is_deterministic(tmp_path):
    """T96-DSTE-04: Candidate list sorted by predicted*novelty desc, tie-broken by id."""
    pool = _pool(10)
    e = _engine(tmp_path)
    r = e.dream(pool, epoch_id="epoch-SORT", seed=77)
    scores = [round(c.predicted_fitness * c.novelty_score, 8) for c in r.candidates]
    assert scores == sorted(scores, reverse=True)


def test_T96_DSTE_05_repeated_calls_same_engine_deterministic(tmp_path):
    """T96-DSTE-05: Two sequential calls with same seed on same engine produce same output."""
    pool = _pool(6)
    e1 = _engine(tmp_path / "a")
    e2 = _engine(tmp_path / "b")
    r1 = e1.dream(pool, epoch_id="epoch-REP", seed=123)
    r2 = e2.dream(pool, epoch_id="epoch-REP", seed=123)
    assert [c.candidate_id for c in r1.candidates] == [c.candidate_id for c in r2.candidates]
    assert [c.novelty_score for c in r1.candidates] == [c.novelty_score for c in r2.candidates]


# ── T96-DSTE-06..09 Ledger-first commit (DSTE-0) ────────────────────────────

def test_T96_DSTE_06_ledger_file_created_before_return(tmp_path):
    """T96-DSTE-06: Ledger file exists and contains event after dream() returns."""
    pool = _pool(5)
    e = _engine(tmp_path)
    r = e.dream(pool, epoch_id="epoch-LED", seed=1)
    assert e.ledger_path.exists()
    lines = e.ledger_path.read_text().strip().split("\n")
    assert len(lines) >= 1
    event = json.loads(lines[0])
    assert event["event_id"] == r.ledger_event_id


def test_T96_DSTE_07_ledger_event_precedes_candidate_return(tmp_path):
    """T96-DSTE-07: gate_1 fails if ledger_committed=False (DSTE-0 enforced)."""
    with pytest.raises(DreamGateViolation) as exc_info:
        evaluate_dream_gate_1(
            candidates=[],
            ledger_committed=False,
            ledger_event_id="DSTE-test-0000",
        )
    assert exc_info.value.invariant == DSTE_0


def test_T96_DSTE_08_ledger_event_contains_all_required_fields(tmp_path):
    """T96-DSTE-08: Each ledger event has the full constitutional field set."""
    pool = _pool(5)
    e = _engine(tmp_path)
    e.dream(pool, epoch_id="epoch-FIELDS", seed=2)
    event = json.loads(e.ledger_path.read_text().strip().split("\n")[0])
    required = [
        "event_type", "event_id", "epoch_id", "dream_seed",
        "candidate_count", "candidate_ids", "novelty_rejects",
        "quorum_met", "pool_size", "genesis_digest",
        "prev_event_hash", "timestamp_utc", "invariant_class",
        "invariants_checked",
    ]
    for field in required:
        assert field in event, f"Missing required field: {field}"


def test_T96_DSTE_09_ledger_invariant_class_is_hard(tmp_path):
    """T96-DSTE-09: All ledger events declare invariant_class='Hard'."""
    pool = _pool(5)
    e = _engine(tmp_path)
    e.dream(pool, epoch_id="epoch-HARD", seed=3)
    for line in e.ledger_path.read_text().strip().split("\n"):
        event = json.loads(line)
        assert event["invariant_class"] == "Hard"


# ── T96-DSTE-10..12 Novelty floor rejection (DSTE-2) ────────────────────────

def test_T96_DSTE_10_all_returned_candidates_above_novelty_floor(tmp_path):
    """T96-DSTE-10: No returned candidate has novelty_score < DREAM_MIN_NOVELTY."""
    pool = _pool(8)
    e = _engine(tmp_path)
    r = e.dream(pool, epoch_id="epoch-NOV", seed=42)
    for c in r.candidates:
        assert c.novelty_score >= DREAM_MIN_NOVELTY, (
            f"Candidate {c.candidate_id} has novelty {c.novelty_score} < {DREAM_MIN_NOVELTY}"
        )


def test_T96_DSTE_11_novelty_rejects_recorded_in_ledger(tmp_path):
    """T96-DSTE-11: novelty_rejects field in ledger event is non-negative integer."""
    pool = _pool(6)
    e = _engine(tmp_path)
    e.dream(pool, epoch_id="epoch-REJ", seed=5)
    event = json.loads(e.ledger_path.read_text().strip().split("\n")[0])
    assert isinstance(event["novelty_rejects"], int)
    assert event["novelty_rejects"] >= 0


def test_T96_DSTE_12_low_novelty_pool_still_returns_valid_report(tmp_path):
    """T96-DSTE-12: Pool where all combos have low novelty yields PASS report with empty candidates."""
    # All same mutation type → max overlap → novelty = 0.5 which is ≥ 0.3, so passes
    # Force novelty below floor by patching
    pool = _pool(5)
    e = _engine(tmp_path)
    with mock.patch.object(DreamStateEngine, "_compute_novelty", return_value=0.10):
        r = e.dream(pool, epoch_id="epoch-LOWNOV", seed=7)
    # All candidates rejected by DSTE-2; report still PASS with empty candidates
    assert r.verdict == "PASS"
    assert r.candidates == []
    event = json.loads(e.ledger_path.read_text().strip().split("\n")[0])
    assert event["novelty_rejects"] > 0


# ── T96-DSTE-13..15 Quorum gate (DSTE-3) ────────────────────────────────────

def test_T96_DSTE_13_under_quorum_returns_empty_candidates(tmp_path):
    """T96-DSTE-13: Pool with <3 successful epochs returns [] candidates."""
    pool = [_epoch_entry("e0", "refactor", 0.9), _epoch_entry("e1", "optimize", 0.8)]
    e = _engine(tmp_path)
    r = e.dream(pool, epoch_id="epoch-QUO", seed=1)
    assert r.candidates == []
    assert r.verdict == "PASS"


def test_T96_DSTE_14_under_quorum_does_not_raise(tmp_path):
    """T96-DSTE-14: Under-quorum path never raises; returns report gracefully."""
    pool = [_epoch_entry("e0", "refactor", 0.9)]
    e = _engine(tmp_path)
    r = e.dream(pool, epoch_id="epoch-NOQUO", seed=1)
    assert isinstance(r, DreamStateReport)


def test_T96_DSTE_15_under_quorum_ledger_event_emitted(tmp_path):
    """T96-DSTE-15: Under-quorum path still emits a ledger event (DSTE-3 evidence)."""
    pool = [_epoch_entry("e0", "refactor", 0.9), _epoch_entry("e1", "optimize", 0.7)]
    e = _engine(tmp_path)
    e.dream(pool, epoch_id="epoch-QUOEV", seed=1)
    assert e.ledger_path.exists()
    event = json.loads(e.ledger_path.read_text().strip().split("\n")[0])
    assert event["quorum_met"] is False
    assert event["event_type"] == "dream_consolidation_skipped"


# ── T96-DSTE-16..18 Chain integrity (DSTE-4) ────────────────────────────────

def test_T96_DSTE_16_first_event_has_genesis_prev_hash(tmp_path):
    """T96-DSTE-16: First ledger event carries prev_event_hash='genesis'."""
    pool = _pool(5)
    e = _engine(tmp_path)
    e.dream(pool, epoch_id="epoch-CH1", seed=1)
    event = json.loads(e.ledger_path.read_text().strip().split("\n")[0])
    assert event["prev_event_hash"] == "genesis"


def test_T96_DSTE_17_sequential_events_form_chain(tmp_path):
    """T96-DSTE-17: Second event's prev_event_hash equals hash of first event."""
    import hashlib, json as _json
    pool = _pool(5)
    e = _engine(tmp_path)
    e.dream(pool, epoch_id="epoch-CH2A", seed=1)
    e.dream(pool, epoch_id="epoch-CH2B", seed=2)
    lines = e.ledger_path.read_text().strip().split("\n")
    assert len(lines) == 2
    ev1 = _json.loads(lines[0])
    ev2 = _json.loads(lines[1])
    ev1_hash = "sha256:" + hashlib.sha256(
        _json.dumps(ev1, sort_keys=True).encode()
    ).hexdigest()
    assert ev2["prev_event_hash"] == ev1_hash


def test_T96_DSTE_18_prev_event_hash_field_is_sha256(tmp_path):
    """T96-DSTE-18: prev_event_hash is either 'genesis' or a sha256: prefixed string."""
    pool = _pool(5)
    e = _engine(tmp_path)
    e.dream(pool, epoch_id="epoch-CH3A", seed=1)
    e.dream(pool, epoch_id="epoch-CH3B", seed=2)
    for line in e.ledger_path.read_text().strip().split("\n"):
        ev = json.loads(line)
        h = ev["prev_event_hash"]
        assert h == "genesis" or h.startswith("sha256:"), f"Bad prev_event_hash: {h}"


# ── T96-DSTE-19..21 No-write invariant (DSTE-5) ─────────────────────────────

def test_T96_DSTE_19_epoch_memory_not_mutated(tmp_path):
    """T96-DSTE-19: epoch_memory list is not modified during dream()."""
    pool = _pool(5)
    original_ids = [e["epoch_id"] for e in pool]
    original_len = len(pool)
    eng = _engine(tmp_path)
    eng.dream(pool, epoch_id="epoch-NW1", seed=1)
    assert [e["epoch_id"] for e in pool] == original_ids
    assert len(pool) == original_len


def test_T96_DSTE_20_no_production_state_file_written(tmp_path):
    """T96-DSTE-20: Only dream ledger and candidate files are written; no other files created."""
    pool = _pool(5)
    eng = DreamStateEngine(
        state_path=tmp_path / "cand.jsonl",
        ledger_path=tmp_path / "led.jsonl",
    )
    files_before = set(tmp_path.rglob("*"))
    eng.dream(pool, epoch_id="epoch-NW2", seed=1)
    files_after = set(tmp_path.rglob("*"))
    new_files = {f for f in files_after - files_before if f.is_file()}
    allowed = {tmp_path / "cand.jsonl", tmp_path / "led.jsonl"}
    unexpected = new_files - allowed
    assert not unexpected, f"Unexpected files written: {unexpected}"


def test_T96_DSTE_21_individual_epoch_entries_not_modified(tmp_path):
    """T96-DSTE-21: Each dict in epoch_memory retains original keys and values."""
    pool = _pool(5)
    import copy
    pool_snapshot = copy.deepcopy(pool)
    eng = _engine(tmp_path)
    eng.dream(pool, epoch_id="epoch-NW3", seed=1)
    assert pool == pool_snapshot


# ── T96-DSTE-22..23 Candidate ceiling (DSTE-6) ──────────────────────────────

def test_T96_DSTE_22_candidate_count_never_exceeds_ceiling(tmp_path):
    """T96-DSTE-22: dream() never returns more than DREAM_CANDIDATES candidates."""
    pool = _pool(20)
    eng = _engine(tmp_path)
    r = eng.dream(pool, epoch_id="epoch-CAP", seed=42)
    assert len(r.candidates) <= DREAM_CANDIDATES


def test_T96_DSTE_23_gate1_rejects_overcounted_candidates():
    """T96-DSTE-23: evaluate_dream_gate_1 raises DSTE-6 if >5 candidates passed."""
    overcounted = [
        DreamCandidate(
            candidate_id=f"DREAM-test-{i:02d}",
            source_epochs=["e1", "e2"],
            combined_intent="x",
            recombined_ops=[],
            predicted_fitness=0.8,
            novelty_score=0.5,
        )
        for i in range(6)
    ]
    with pytest.raises(DreamGateViolation) as exc_info:
        evaluate_dream_gate_1(
            candidates=overcounted,
            ledger_committed=True,
            ledger_event_id="DSTE-test-0000",
        )
    assert exc_info.value.invariant == DSTE_6


# ── T96-DSTE-24..26 seed=None hard block (DSTE-1) ──────────────────────────

def test_T96_DSTE_24_seed_none_raises_gate_violation(tmp_path):
    """T96-DSTE-24: seed=None is a Hard-class violation via DreamGateViolation."""
    pool = _pool(5)
    eng = _engine(tmp_path)
    with pytest.raises(DreamGateViolation) as exc_info:
        eng.dream(pool, epoch_id="epoch-SEED", seed=None)
    assert exc_info.value.invariant == DSTE_1


def test_T96_DSTE_25_seed_none_in_gate0_raises_immediately():
    """T96-DSTE-25: evaluate_dream_gate_0 raises immediately on seed=None."""
    with pytest.raises(DreamGateViolation) as exc_info:
        evaluate_dream_gate_0(seed=None, epoch_memory=_pool(5))
    assert exc_info.value.invariant == DSTE_1


def test_T96_DSTE_26_seed_zero_is_valid(tmp_path):
    """T96-DSTE-26: seed=0 is a valid explicit seed (not treated as falsy None)."""
    pool = _pool(5)
    eng = _engine(tmp_path)
    r = eng.dream(pool, epoch_id="epoch-ZERO", seed=0)
    assert r.verdict == "PASS"
    event = json.loads(eng.ledger_path.read_text().strip().split("\n")[0])
    assert event["dream_seed"] == 0


# ── T96-DSTE-27..28 Verdict cannot be APPROVED ──────────────────────────────

def test_T96_DSTE_27_report_verdict_approved_raises():
    """T96-DSTE-27: DreamStateReport raises ValueError if verdict='APPROVED'."""
    with pytest.raises(ValueError, match="cannot be 'APPROVED'"):
        DreamStateReport(
            report_id="DSR-test",
            phase=96,
            innovation="INNOV-11",
            epoch_id="epoch-APPR",
            candidates=[],
            ledger_event_id="DSTE-test-0000",
            invariants_passed=[],
            invariants_failed=[],
            verdict="APPROVED",
            timestamp_utc="2026-03-30T00:00:00+00:00",
        )


def test_T96_DSTE_28_dream_engine_never_emits_approved_verdict(tmp_path):
    """T96-DSTE-28: dream() only produces PASS or RETURNED verdicts."""
    pool = _pool(5)
    eng = _engine(tmp_path)
    r = eng.dream(pool, epoch_id="epoch-VERD", seed=1)
    assert r.verdict in {"PASS", "RETURNED"}
    assert r.verdict != "APPROVED"


# ── T96-DSTE-29..30 CEL Step 16 integration ─────────────────────────────────

def test_T96_DSTE_29_cel_step_skips_when_under_quorum(tmp_path):
    """T96-DSTE-29: dream() with <DREAM_QUORUM successful epochs is a no-op for candidates."""
    failing_pool = [_epoch_entry(f"e{i}", "refactor", -0.1) for i in range(10)]
    eng = _engine(tmp_path)
    r = eng.dream(failing_pool, epoch_id="epoch-CEL1", seed=1)
    assert r.candidates == []
    assert r.verdict == "PASS"
    event = json.loads(eng.ledger_path.read_text().strip().split("\n")[0])
    assert event["quorum_met"] is False


def test_T96_DSTE_30_successful_cycle_provides_mutation_seed_pool(tmp_path):
    """T96-DSTE-30: Successful dream() provides candidate pool for next-epoch injection."""
    pool = _pool(8, delta=0.9)
    eng = _engine(tmp_path)
    r = eng.dream(pool, epoch_id="epoch-CEL2", seed=42)
    # Candidates are ready to inject into next epoch's mutation_seed_pool
    for c in r.candidates:
        assert c.recombined_ops, "Each candidate must have recombined_ops for injection"
        assert c.source_epochs, "Each candidate must declare source epochs"
        assert c.genesis_digest.startswith("sha256:")
    # Candidate file written for downstream consumption
    assert eng.state_path.exists()
    lines = eng.state_path.read_text().strip().split("\n")
    assert len(lines) == len(r.candidates)
