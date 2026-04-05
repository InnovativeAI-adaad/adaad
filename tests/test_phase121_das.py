# SPDX-License-Identifier: Apache-2.0
"""Phase 121 — INNOV-36 Deterministic Audit Sandbox (DAS) tests.

T121-DAS-01..30  (30/30)
pytest mark: phase121
"""
from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from pathlib import Path

from runtime.innovations30.deterministic_audit_sandbox import (
    DASChainError,
    DASDeterminismError,
    DASGateError,
    DASReplayError,
    DASVerifyError,
    DASViolation,
    DAS_INVARIANTS,
    DeterministicAuditSandbox,
    EpochRecord,
    RuntimeDeterminismProvider,
    _CHAIN_KEY,
    _CHAIN_PREFIX_LEN,
    _GENESIS_PREV,
    _compute_chain_link,
    das_guard,
)

pytestmark = pytest.mark.phase121

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_ledger(tmp_path: Path) -> Path:
    return tmp_path / "das_test.jsonl"


@pytest.fixture()
def timer() -> RuntimeDeterminismProvider:
    return RuntimeDeterminismProvider(base_ts="2026-04-04T00:00:00Z", step_seconds=1)


@pytest.fixture()
def sandbox(tmp_ledger: Path, timer: RuntimeDeterminismProvider) -> DeterministicAuditSandbox:
    return DeterministicAuditSandbox(ledger_path=tmp_ledger, timer=timer)


@pytest.fixture()
def populated_ledger(tmp_ledger: Path, timer: RuntimeDeterminismProvider) -> Path:
    """Write 8 records to a ledger and return its path."""
    sb = DeterministicAuditSandbox(ledger_path=tmp_ledger, timer=timer)
    sb.run_epoch(epoch_id="EPOCH-001", seed="test-seed-v1", n_mutations=8)
    sb.flush()
    return tmp_ledger


# ── T121-DAS-01: invariant registry completeness ──────────────────────────────
def test_T121_DAS_01_invariant_registry():
    expected = {"DAS-0", "DAS-DETERM-0", "DAS-CHAIN-0", "DAS-REPLAY-0",
                "DAS-GATE-0", "DAS-VERIFY-0", "DAS-DOCKER-0"}
    assert set(DAS_INVARIANTS.keys()) == expected


# ── T121-DAS-02: all invariants are Hard-class ────────────────────────────────
def test_T121_DAS_02_all_hard_class():
    for key, meta in DAS_INVARIANTS.items():
        assert meta["class"] == "Hard", f"{key} is not Hard-class"


# ── T121-DAS-03: timer produces deterministic timestamps ─────────────────────
def test_T121_DAS_03_timer_determinism():
    t1 = RuntimeDeterminismProvider(base_ts="2026-01-01T00:00:00Z", step_seconds=1)
    t2 = RuntimeDeterminismProvider(base_ts="2026-01-01T00:00:00Z", step_seconds=1)
    for _ in range(5):
        assert t1.now_utc() == t2.now_utc()


# ── T121-DAS-04: timer advances correctly ────────────────────────────────────
def test_T121_DAS_04_timer_advances():
    t = RuntimeDeterminismProvider(base_ts="2026-01-01T00:00:00Z", step_seconds=10)
    ts0 = t.now_utc()
    ts1 = t.now_utc()
    assert ts0 == "2026-01-01T00:00:00Z"
    assert ts1 == "2026-01-01T00:00:10Z"


# ── T121-DAS-05: timer reset restores determinism ────────────────────────────
def test_T121_DAS_05_timer_reset():
    t = RuntimeDeterminismProvider()
    first = [t.now_utc() for _ in range(3)]
    t.reset()
    second = [t.now_utc() for _ in range(3)]
    assert first == second


# ── T121-DAS-06: chain link is deterministic ─────────────────────────────────
def test_T121_DAS_06_chain_link_deterministic():
    h1 = _compute_chain_link("E001:M0001", _GENESIS_PREV)
    h2 = _compute_chain_link("E001:M0001", _GENESIS_PREV)
    assert h1 == h2


# ── T121-DAS-07: chain link is 24 chars ──────────────────────────────────────
def test_T121_DAS_07_chain_link_length():
    h = _compute_chain_link("E001:M0001", _GENESIS_PREV)
    assert len(h) == _CHAIN_PREFIX_LEN == 24


# ── T121-DAS-08: chain link changes on different inputs ──────────────────────
def test_T121_DAS_08_chain_link_sensitivity():
    h1 = _compute_chain_link("E001:M0001", _GENESIS_PREV)
    h2 = _compute_chain_link("E001:M0002", _GENESIS_PREV)
    h3 = _compute_chain_link("E001:M0001", "a" * 64)
    assert h1 != h2
    assert h1 != h3


# ── T121-DAS-09: EpochRecord computes record_hash on init ────────────────────
def test_T121_DAS_09_epoch_record_hash_on_init():
    rec = EpochRecord(
        epoch_id="EPOCH-001", seed="s1", mutation_id="mut0001",
        status="approved", timestamp="2026-04-04T00:00:00Z",
        prev_digest=_GENESIS_PREV,
    )
    assert len(rec.record_hash) == _CHAIN_PREFIX_LEN
    expected = _compute_chain_link("EPOCH-001:mut0001", _GENESIS_PREV)
    assert rec.record_hash == expected


# ── T121-DAS-10: EpochRecord serialization round-trip ────────────────────────
def test_T121_DAS_10_epoch_record_roundtrip():
    rec = EpochRecord(
        epoch_id="EPOCH-001", seed="s1", mutation_id="mut0001",
        status="approved", timestamp="2026-04-04T00:00:00Z",
        prev_digest=_GENESIS_PREV,
        metadata={"detail": "x"},
    )
    d = rec.to_dict()
    rec2 = EpochRecord.from_dict(d)
    assert rec2.epoch_id == rec.epoch_id
    assert rec2.record_hash == rec.record_hash
    assert rec2.metadata == {"detail": "x"}


# ── T121-DAS-11: run_epoch returns correct count ─────────────────────────────
def test_T121_DAS_11_run_epoch_count(sandbox):
    records = sandbox.run_epoch(epoch_id="EPOCH-001", seed="abc", n_mutations=8)
    assert len(records) == 8


# ── T121-DAS-12: run_epoch is deterministic (DAS-0) ──────────────────────────
def test_T121_DAS_12_run_epoch_deterministic(tmp_path):
    t1 = RuntimeDeterminismProvider()
    t2 = RuntimeDeterminismProvider()
    sb1 = DeterministicAuditSandbox(ledger_path=tmp_path / "l1.jsonl", timer=t1)
    sb2 = DeterministicAuditSandbox(ledger_path=tmp_path / "l2.jsonl", timer=t2)
    r1 = sb1.run_epoch(epoch_id="EPOCH-001", seed="xyz", n_mutations=8)
    r2 = sb2.run_epoch(epoch_id="EPOCH-001", seed="xyz", n_mutations=8)
    for a, b in zip(r1, r2):
        assert a.record_hash == b.record_hash


# ── T121-DAS-13: chain links correctly across records ────────────────────────
def test_T121_DAS_13_chain_links_correct(sandbox):
    records = sandbox.run_epoch(epoch_id="EPOCH-001", seed="abc", n_mutations=4)
    prev = _GENESIS_PREV
    for rec in records:
        expected = _compute_chain_link(f"{rec.epoch_id}:{rec.mutation_id}", prev)
        assert rec.record_hash == expected
        prev = rec.record_hash


# ── T121-DAS-14: empty epoch_id raises DASViolation ─────────────────────────
def test_T121_DAS_14_empty_epoch_id_raises(sandbox):
    with pytest.raises(DASViolation):
        sandbox.run_epoch(epoch_id="", seed="abc")


# ── T121-DAS-15: empty seed raises DASViolation ──────────────────────────────
def test_T121_DAS_15_empty_seed_raises(sandbox):
    with pytest.raises(DASViolation):
        sandbox.run_epoch(epoch_id="EPOCH-001", seed="")


# ── T121-DAS-16: n_mutations < 1 raises DASViolation ─────────────────────────
def test_T121_DAS_16_zero_mutations_raises(sandbox):
    with pytest.raises(DASViolation):
        sandbox.run_epoch(epoch_id="EPOCH-001", seed="abc", n_mutations=0)


# ── T121-DAS-17: flush writes correct number of lines ────────────────────────
def test_T121_DAS_17_flush_line_count(sandbox, tmp_ledger):
    sandbox.run_epoch(epoch_id="EPOCH-001", seed="abc", n_mutations=8)
    sandbox.flush()
    lines = [l for l in tmp_ledger.read_text().splitlines() if l.strip()]
    assert len(lines) == 8


# ── T121-DAS-18: flush writes valid JSON on every line ───────────────────────
def test_T121_DAS_18_flush_valid_json(sandbox, tmp_ledger):
    sandbox.run_epoch(epoch_id="EPOCH-001", seed="abc", n_mutations=4)
    sandbox.flush()
    for line in tmp_ledger.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            assert "record_hash" in d


# ── T121-DAS-19: flush writes prev_digest chain ──────────────────────────────
def test_T121_DAS_19_flush_prev_digest_chain(sandbox, tmp_ledger):
    sandbox.run_epoch(epoch_id="EPOCH-001", seed="abc", n_mutations=4)
    sandbox.flush()
    records = [json.loads(l) for l in tmp_ledger.read_text().splitlines() if l.strip()]
    assert records[0]["prev_digest"] == _GENESIS_PREV
    for i in range(1, len(records)):
        assert records[i]["prev_digest"] == records[i - 1]["record_hash"]


# ── T121-DAS-20: verify_ledger passes on clean ledger (DAS-VERIFY-0) ─────────
def test_T121_DAS_20_verify_ledger_clean(populated_ledger):
    result = DeterministicAuditSandbox.verify_ledger(populated_ledger)
    assert result["ok"] is True
    assert result["records_checked"] == 8
    assert result["error"] is None


# ── T121-DAS-21: verify_ledger raises on tampered hash (DAS-VERIFY-0) ────────
def test_T121_DAS_21_verify_ledger_tampered(populated_ledger):
    lines = populated_ledger.read_text().splitlines()
    d = json.loads(lines[3])
    d["record_hash"] = "000000000000000000000000"  # 24 zeros — wrong
    lines[3] = json.dumps(d)
    populated_ledger.write_text("\n".join(lines) + "\n")
    with pytest.raises(DASVerifyError):
        DeterministicAuditSandbox.verify_ledger(populated_ledger)


# ── T121-DAS-22: verify_ledger raises on tampered prev_digest ────────────────
def test_T121_DAS_22_verify_ledger_tampered_prev(populated_ledger):
    lines = populated_ledger.read_text().splitlines()
    d = json.loads(lines[2])
    d["prev_digest"] = "x" * 64
    lines[2] = json.dumps(d)
    populated_ledger.write_text("\n".join(lines) + "\n")
    with pytest.raises(DASVerifyError):
        DeterministicAuditSandbox.verify_ledger(populated_ledger)


# ── T121-DAS-23: replay_epoch reproduces correct hashes (DAS-REPLAY-0) ───────
def test_T121_DAS_23_replay_epoch_correct(populated_ledger, tmp_path, timer):
    timer.reset()
    sb = DeterministicAuditSandbox(ledger_path=tmp_path / "replay.jsonl", timer=timer)
    replayed = sb.replay_epoch(populated_ledger)
    assert len(replayed) == 8
    # All replayed record_hashes must match stored
    stored = [json.loads(l) for l in populated_ledger.read_text().splitlines() if l.strip()]
    for r, s in zip(replayed, stored):
        assert r.record_hash == s["record_hash"]


# ── T121-DAS-24: replay_epoch raises on tampered record (DAS-REPLAY-0) ───────
def test_T121_DAS_24_replay_epoch_tampered(populated_ledger, tmp_path, timer):
    lines = populated_ledger.read_text().splitlines()
    d = json.loads(lines[1])
    d["record_hash"] = "deadbeefdeadbeefdeadbeef"
    lines[1] = json.dumps(d)
    populated_ledger.write_text("\n".join(lines) + "\n")
    timer.reset()
    sb = DeterministicAuditSandbox(ledger_path=tmp_path / "r.jsonl", timer=timer)
    with pytest.raises(DASReplayError):
        sb.replay_epoch(populated_ledger)


# ── T121-DAS-25: mutation_id is deterministic ────────────────────────────────
def test_T121_DAS_25_mutation_id_deterministic():
    m1 = DeterministicAuditSandbox._derive_mutation_id("seed-x", 0)
    m2 = DeterministicAuditSandbox._derive_mutation_id("seed-x", 0)
    assert m1 == m2
    assert len(m1) == 16


# ── T121-DAS-26: mutation_id differs across seeds/indices ────────────────────
def test_T121_DAS_26_mutation_id_unique():
    ids = {DeterministicAuditSandbox._derive_mutation_id("seed", i) for i in range(8)}
    assert len(ids) == 8


# ── T121-DAS-27: classify only returns valid statuses ────────────────────────
def test_T121_DAS_27_classify_valid_statuses():
    valid = DeterministicAuditSandbox.VALID_STATUSES
    for i in range(50):
        s = DeterministicAuditSandbox._classify("seed-test", i)
        assert s in valid


# ── T121-DAS-28: das_guard wraps non-DAS exceptions ─────────────────────────
def test_T121_DAS_28_das_guard_wraps():
    @das_guard
    def _boom():
        raise ValueError("unexpected")

    with pytest.raises(DASViolation, match="unexpected"):
        _boom()


# ── T121-DAS-29: das_guard re-raises DASViolation unchanged ──────────────────
def test_T121_DAS_29_das_guard_reraises_das():
    @das_guard
    def _das_err():
        raise DASVerifyError("DAS-VERIFY-0: test")

    with pytest.raises(DASVerifyError):
        _das_err()


# ── T121-DAS-30: full pipeline — run, flush, verify, replay all pass ─────────
def test_T121_DAS_30_full_pipeline(tmp_path):
    ledger = tmp_path / "full_pipeline.jsonl"
    timer = RuntimeDeterminismProvider()
    sb = DeterministicAuditSandbox(ledger_path=ledger, timer=timer)
    records = sb.run_epoch(epoch_id="EPOCH-FULL", seed="pipeline-seed-v1", n_mutations=8)
    assert len(records) == 8
    sb.flush()
    # verify
    result = DeterministicAuditSandbox.verify_ledger(ledger)
    assert result["ok"] is True
    assert result["records_checked"] == 8
    # replay
    timer2 = RuntimeDeterminismProvider()
    sb2 = DeterministicAuditSandbox(ledger_path=tmp_path / "r.jsonl", timer=timer2)
    replayed = sb2.replay_epoch(ledger)
    assert len(replayed) == 8
    stored = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    for r, s in zip(replayed, stored):
        assert r.record_hash == s["record_hash"]
