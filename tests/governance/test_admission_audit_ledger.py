# SPDX-License-Identifier: Apache-2.0
"""Tests for AdmissionAuditLedger + AdmissionAuditReader — ADAAD Phase 27.

Test IDs: T27-01..36
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from runtime.governance.admission_audit_ledger import (
    ADMISSION_LEDGER_GENESIS_PREV_HASH,
    ADMISSION_LEDGER_VERSION,
    AdmissionAuditChainError,
    AdmissionAuditLedger,
    AdmissionAuditReader,
)
from runtime.governance.mutation_admission import MutationAdmissionController


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decision(health: float = 0.90, risk: float = 0.20):
    return MutationAdmissionController().evaluate(
        health_score=health, mutation_risk_score=risk
    )


# ---------------------------------------------------------------------------
# T27-01..06 — Inactive ledger (no path)
# ---------------------------------------------------------------------------


def test_inactive_emit_is_noop():                              # T27-01
    ledger = AdmissionAuditLedger()
    ledger.emit(_decision())   # must not raise
    assert ledger.sequence == 0


def test_inactive_path_is_none():                             # T27-02
    ledger = AdmissionAuditLedger()
    assert ledger.path is None


def test_inactive_verify_returns_false():                     # T27-03
    ledger = AdmissionAuditLedger()
    assert ledger.verify_chain() is False


def test_inactive_sequence_zero():                            # T27-04
    assert AdmissionAuditLedger().sequence == 0


def test_inactive_multiple_emits_silent():                    # T27-05
    ledger = AdmissionAuditLedger()
    for _ in range(5):
        ledger.emit(_decision())
    assert ledger.sequence == 0


def test_inactive_no_file_created(tmp_path):                  # T27-06
    # Inactive — path=None — no file must be created
    AdmissionAuditLedger()
    assert not (tmp_path / "ghost.jsonl").exists()


# ---------------------------------------------------------------------------
# T27-07..15 — Active ledger: emit and sequence
# ---------------------------------------------------------------------------


def test_active_emit_creates_file(tmp_path):                   # T27-07
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    assert p.exists()


def test_active_sequence_increments(tmp_path):                 # T27-08
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    assert ledger.sequence == 1
    ledger.emit(_decision())
    assert ledger.sequence == 2


def test_active_record_fields(tmp_path):                       # T27-09
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    d = _decision(health=0.75, risk=0.40)
    ledger.emit(d)
    rec = json.loads(p.read_text().strip())
    assert rec["sequence"] == 0
    assert rec["prev_hash"] == ADMISSION_LEDGER_GENESIS_PREV_HASH
    assert rec["health_score"] == pytest.approx(0.75, abs=1e-6)
    assert rec["mutation_risk_score"] == pytest.approx(0.40, abs=1e-6)
    assert rec["admitted"] is True   # amber band, risk=0.40 < threshold=0.60 → admitted
    assert "record_hash" in rec
    assert "timestamp_iso" in rec
    assert rec["ledger_version"] == ADMISSION_LEDGER_VERSION


def test_active_prev_hash_chain(tmp_path):                     # T27-10
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    ledger.emit(_decision())
    lines = [json.loads(l) for l in p.read_text().strip().splitlines()]
    assert lines[1]["prev_hash"] == lines[0]["record_hash"]


def test_active_record_hash_is_sha256(tmp_path):               # T27-11
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    rec = json.loads(p.read_text().strip())
    assert rec["record_hash"].startswith("sha256:")
    assert len(rec["record_hash"]) == 7 + 64


def test_active_emit_admitted_true(tmp_path):                   # T27-12
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    d = _decision(health=1.0, risk=0.10)
    ledger.emit(d)
    rec = json.loads(p.read_text().strip())
    assert rec["admitted"] is True


def test_active_emit_epoch_paused(tmp_path):                    # T27-13
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    d = _decision(health=0.10, risk=0.01)
    ledger.emit(d)
    rec = json.loads(p.read_text().strip())
    assert rec["epoch_paused"] is True


def test_active_emit_halt_band(tmp_path):                       # T27-14
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    d = _decision(health=0.20, risk=0.05)
    ledger.emit(d)
    rec = json.loads(p.read_text().strip())
    assert rec["admission_band"] == "halt"


def test_active_path_property(tmp_path):                        # T27-15
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    assert ledger.path == p


# ---------------------------------------------------------------------------
# T27-16..22 — Chain verification
# ---------------------------------------------------------------------------


def test_verify_chain_intact(tmp_path):                         # T27-16
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    for _ in range(5):
        ledger.emit(_decision())
    assert ledger.verify_chain() is True


def test_verify_chain_via_reader(tmp_path):                     # T27-17
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    reader = AdmissionAuditReader(p)
    assert reader.verify_chain() is True


def test_verify_chain_on_open_intact(tmp_path):                 # T27-18
    """Second ledger instance opens same file and verifies chain."""
    p = tmp_path / "adm.jsonl"
    l1 = AdmissionAuditLedger(p)
    l1.emit(_decision())
    l2 = AdmissionAuditLedger(p, chain_verify_on_open=True)
    assert l2.sequence == 1


def test_tampered_record_hash_raises(tmp_path):                 # T27-19
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    # Tamper: overwrite record_hash
    content = json.loads(p.read_text().strip())
    content["record_hash"] = "sha256:" + "a" * 64
    p.write_text(json.dumps(content) + "\n")
    with pytest.raises(AdmissionAuditChainError):
        _verify = AdmissionAuditLedger(p, chain_verify_on_open=True)


def test_tampered_admitted_field_raises(tmp_path):              # T27-20
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    content = json.loads(p.read_text().strip())
    content["admitted"] = not content["admitted"]
    p.write_text(json.dumps(content) + "\n")
    with pytest.raises(AdmissionAuditChainError):
        AdmissionAuditLedger(p, chain_verify_on_open=True)


def test_tampered_prev_hash_raises(tmp_path):                   # T27-21
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    ledger.emit(_decision())
    lines = p.read_text().strip().splitlines()
    rec = json.loads(lines[1])
    rec["prev_hash"] = "sha256:" + "b" * 64
    p.write_text(lines[0] + "\n" + json.dumps(rec) + "\n")
    with pytest.raises(AdmissionAuditChainError):
        AdmissionAuditLedger(p, chain_verify_on_open=True)


def test_chain_verify_on_open_false_skips(tmp_path):            # T27-22
    """chain_verify_on_open=False must not raise on tampered file."""
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    content = json.loads(p.read_text().strip())
    content["record_hash"] = "sha256:" + "c" * 64
    p.write_text(json.dumps(content) + "\n")
    # Should not raise
    AdmissionAuditLedger(p, chain_verify_on_open=False)


# ---------------------------------------------------------------------------
# T27-23..30 — AdmissionAuditReader analytics
# ---------------------------------------------------------------------------


def test_reader_history_all(tmp_path):                          # T27-23
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    for _ in range(4):
        ledger.emit(_decision())
    reader = AdmissionAuditReader(p)
    assert len(reader.history()) == 4


def test_reader_history_limit(tmp_path):                        # T27-24
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    for _ in range(6):
        ledger.emit(_decision())
    reader = AdmissionAuditReader(p)
    assert len(reader.history(limit=3)) == 3


def test_reader_history_band_filter(tmp_path):                  # T27-25
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision(health=1.0, risk=0.10))   # green
    ledger.emit(_decision(health=0.70, risk=0.80))  # amber deferred
    ledger.emit(_decision(health=0.20, risk=0.05))  # halt
    reader = AdmissionAuditReader(p)
    greens = reader.history(band_filter="green")
    assert len(greens) == 1
    assert all(r["admission_band"] == "green" for r in greens)


def test_reader_history_admitted_only(tmp_path):                # T27-26
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision(health=1.0, risk=0.10))   # admitted
    ledger.emit(_decision(health=0.70, risk=0.80))  # deferred
    reader = AdmissionAuditReader(p)
    admitted = reader.history(admitted_only=True)
    assert all(r["admitted"] is True for r in admitted)


def test_reader_band_frequency(tmp_path):                       # T27-27
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision(health=1.0, risk=0.10))   # green
    ledger.emit(_decision(health=1.0, risk=0.10))   # green
    ledger.emit(_decision(health=0.20, risk=0.05))  # halt
    reader = AdmissionAuditReader(p)
    freq = reader.band_frequency()
    assert freq["green"] == 2
    assert freq["halt"] == 1


def test_reader_admission_rate_all_admitted(tmp_path):          # T27-28
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    for _ in range(4):
        ledger.emit(_decision(health=1.0, risk=0.10))
    reader = AdmissionAuditReader(p)
    assert reader.admission_rate() == pytest.approx(1.0)


def test_reader_admission_rate_half(tmp_path):                  # T27-29
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision(health=1.0, risk=0.10))   # admitted
    ledger.emit(_decision(health=0.20, risk=0.05))  # halt → not admitted
    reader = AdmissionAuditReader(p)
    assert reader.admission_rate() == pytest.approx(0.5)


def test_reader_empty_file_defaults(tmp_path):                  # T27-30
    p = tmp_path / "ghost.jsonl"
    reader = AdmissionAuditReader(p)
    assert reader.history() == []
    assert reader.band_frequency() == {}
    assert reader.admission_rate() == pytest.approx(1.0)
    assert reader.verify_chain() is False


# ---------------------------------------------------------------------------
# T27-31..36 — Determinism and persistence
# ---------------------------------------------------------------------------


def test_deterministic_record_hash(tmp_path):                   # T27-31
    """Same decision emitted twice to two ledgers → identical record_hash."""
    p1 = tmp_path / "l1.jsonl"
    p2 = tmp_path / "l2.jsonl"
    d = _decision(health=0.85, risk=0.30)
    AdmissionAuditLedger(p1).emit(d)
    AdmissionAuditLedger(p2).emit(d)
    r1 = json.loads(p1.read_text().strip())
    r2 = json.loads(p2.read_text().strip())
    assert r1["record_hash"] == r2["record_hash"]


def test_timestamp_excluded_from_hash(tmp_path):                # T27-32
    """Mutating timestamp_iso must not change record_hash."""
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    original = json.loads(p.read_text().strip())
    original_hash = original["record_hash"]
    original["timestamp_iso"] = "1970-01-01T00:00:00+00:00"
    # Recompute hash independently
    from runtime.governance.admission_audit_ledger import _canonical_bytes, _sha256_prefixed
    probe = {k: v for k, v in original.items() if k not in ("record_hash", "timestamp_iso")}
    recomputed = _sha256_prefixed(_canonical_bytes(probe))
    assert recomputed == original_hash


def test_resume_sequence_on_reopen(tmp_path):                   # T27-33
    p = tmp_path / "adm.jsonl"
    l1 = AdmissionAuditLedger(p)
    l1.emit(_decision())
    l1.emit(_decision())
    l2 = AdmissionAuditLedger(p)
    l2.emit(_decision())
    assert l2.sequence == 3
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 3


def test_parent_dir_created(tmp_path):                          # T27-34
    p = tmp_path / "nested" / "deep" / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    assert p.exists()


def test_controller_version_stored(tmp_path):                   # T27-35
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    rec = json.loads(p.read_text().strip())
    assert rec["controller_version"] == "25.0"


def test_ledger_version_stored(tmp_path):                       # T27-36
    p = tmp_path / "adm.jsonl"
    ledger = AdmissionAuditLedger(p)
    ledger.emit(_decision())
    rec = json.loads(p.read_text().strip())
    assert rec["ledger_version"] == ADMISSION_LEDGER_VERSION == "27.0"
