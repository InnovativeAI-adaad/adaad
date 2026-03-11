# SPDX-License-Identifier: Apache-2.0
"""Tests for Phase 29 — Enforcement Verdict Audit Binding.

Verifies that AdmissionAuditLedger.emit(decision, verdict=...) correctly
persists EnforcerVerdict fields into the hash-chained JSONL ledger, that
AdmissionAuditReader surfaces enforcement analytics, and that the chain
remains verifiable when mixing verdict-carrying and plain records.

Test IDs: T29-01 through T29-08
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.admission_audit_ledger import (
    ADMISSION_LEDGER_VERSION,
    AdmissionAuditLedger,
    AdmissionAuditReader,
)
from runtime.governance.admission_band_enforcer import AdmissionBandEnforcer
from runtime.governance.mutation_admission import MutationAdmissionController


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_decision(health: float = 0.90, risk: float = 0.10):
    return MutationAdmissionController().evaluate(health, risk)


def _make_verdict(health: float = 0.90, risk: float = 0.10, mode: str = "advisory"):
    enforcer = AdmissionBandEnforcer(health_score=health, escalation_mode=mode)
    return enforcer.evaluate(risk)


@pytest.fixture
def tmp_ledger(tmp_path):
    ledger = AdmissionAuditLedger(path=tmp_path / "audit.jsonl")
    return ledger, AdmissionAuditReader(tmp_path / "audit.jsonl")


# ---------------------------------------------------------------------------
# T29-01 — emit with verdict: enforcement fields present in record
# ---------------------------------------------------------------------------

class TestEmitWithVerdict:
    def test_T29_01_01_enforcement_present_true(self, tmp_ledger):
        ledger, reader = tmp_ledger
        decision = _make_decision()
        verdict = _make_verdict()
        ledger.emit(decision, verdict=verdict)
        records = reader.history()
        assert records[0]["enforcement_present"] is True

    def test_T29_01_02_escalation_mode_persisted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        verdict = _make_verdict(mode="advisory")
        ledger.emit(_make_decision(), verdict=verdict)
        assert reader.history()[0]["escalation_mode"] == "advisory"

    def test_T29_01_03_blocking_mode_persisted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        verdict = _make_verdict(health=0.10, risk=0.99, mode="blocking")
        ledger.emit(_make_decision(0.10, 0.99), verdict=verdict)
        rec = reader.history()[0]
        assert rec["escalation_mode"] == "blocking"
        assert rec["blocked"] is True

    def test_T29_01_04_blocked_false_persisted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        verdict = _make_verdict(health=0.90, risk=0.10, mode="advisory")
        ledger.emit(_make_decision(), verdict=verdict)
        assert reader.history()[0]["blocked"] is False

    def test_T29_01_05_block_reason_persisted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        verdict = _make_verdict(health=0.10, risk=0.99, mode="blocking")
        ledger.emit(_make_decision(0.10, 0.99), verdict=verdict)
        rec = reader.history()[0]
        assert "catastrophic" in rec["block_reason"].lower()

    def test_T29_01_06_verdict_digest_persisted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        verdict = _make_verdict()
        ledger.emit(_make_decision(), verdict=verdict)
        rec = reader.history()[0]
        assert rec["verdict_digest"] == verdict.verdict_digest
        assert len(rec["verdict_digest"]) == 64

    def test_T29_01_07_enforcer_version_persisted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        verdict = _make_verdict()
        ledger.emit(_make_decision(), verdict=verdict)
        assert reader.history()[0]["enforcer_version"] == "28.0"

    def test_T29_01_08_all_decision_fields_still_present(self, tmp_ledger):
        ledger, reader = tmp_ledger
        decision = _make_decision(0.75, 0.30)
        verdict = _make_verdict(0.75, 0.30)
        ledger.emit(decision, verdict=verdict)
        rec = reader.history()[0]
        for field in ("health_score", "mutation_risk_score", "admission_band",
                      "admitted", "decision_digest", "controller_version"):
            assert field in rec, f"missing: {field}"


# ---------------------------------------------------------------------------
# T29-02 — emit WITHOUT verdict: enforcement_present=False, nulls
# ---------------------------------------------------------------------------

class TestEmitWithoutVerdict:
    def test_T29_02_01_enforcement_present_false(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision())
        assert reader.history()[0]["enforcement_present"] is False

    def test_T29_02_02_enforcement_fields_are_none(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision())
        rec = reader.history()[0]
        for field in ("escalation_mode", "blocked", "block_reason",
                      "verdict_digest", "enforcer_version"):
            assert rec[field] is None, f"{field} should be None"


# ---------------------------------------------------------------------------
# T29-03 — Chain integrity with mixed emit types
# ---------------------------------------------------------------------------

class TestChainIntegrity:
    def test_T29_03_01_chain_valid_after_mixed_emits(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision())                            # no verdict
        ledger.emit(_make_decision(), verdict=_make_verdict())  # with verdict
        ledger.emit(_make_decision())                            # no verdict
        assert reader.verify_chain() is True

    def test_T29_03_02_sequence_numbers_monotonic(self, tmp_ledger):
        ledger, reader = tmp_ledger
        for i in range(4):
            ledger.emit(_make_decision(), verdict=_make_verdict() if i % 2 == 0 else None)
        records = reader.history()
        seqs = [r["sequence"] for r in records]
        assert seqs == list(range(4))

    def test_T29_03_03_ledger_version_is_29(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision())
        assert reader.history()[0]["ledger_version"] == ADMISSION_LEDGER_VERSION
        assert ADMISSION_LEDGER_VERSION == "29.0"

    def test_T29_03_04_record_hash_covers_enforcement_fields(self, tmp_ledger):
        """Records with/without verdict must have different record_hashes."""
        ledger_a, reader_a = tmp_ledger
        with tempfile.TemporaryDirectory() as td:
            ledger_b = AdmissionAuditLedger(path=Path(td) / "b.jsonl")
            reader_b = AdmissionAuditReader(Path(td) / "b.jsonl")

        decision = _make_decision()
        verdict = _make_verdict()
        ledger_a.emit(decision, verdict=verdict)
        ledger_b = AdmissionAuditLedger(path=Path(td) / "b.jsonl")
        ledger_b.emit(decision)  # same decision, no verdict

        h_a = reader_a.history()[0]["record_hash"]
        reader_b2 = AdmissionAuditReader(Path(td) / "b.jsonl")
        h_b = reader_b2.history()[0]["record_hash"]
        assert h_a != h_b  # enforcement fields change the hash


# ---------------------------------------------------------------------------
# T29-04 — blocked_count analytics
# ---------------------------------------------------------------------------

class TestBlockedCount:
    def test_T29_04_01_empty_ledger_returns_zero(self, tmp_ledger):
        _, reader = tmp_ledger
        assert reader.blocked_count() == 0

    def test_T29_04_02_no_blocked_records(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision(), verdict=_make_verdict(health=0.90))
        assert reader.blocked_count() == 0

    def test_T29_04_03_counts_blocked_correctly(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision(0.90, 0.10), verdict=_make_verdict(0.90, 0.10, "advisory"))
        ledger.emit(_make_decision(0.10, 0.99), verdict=_make_verdict(0.10, 0.99, "blocking"))
        ledger.emit(_make_decision(0.10, 0.99), verdict=_make_verdict(0.10, 0.99, "blocking"))
        assert reader.blocked_count() == 2

    def test_T29_04_04_no_verdict_records_not_counted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision())  # no verdict — blocked field is None
        assert reader.blocked_count() == 0


# ---------------------------------------------------------------------------
# T29-05 — enforcement_rate analytics
# ---------------------------------------------------------------------------

class TestEnforcementRate:
    def test_T29_05_01_empty_returns_zero(self, tmp_ledger):
        _, reader = tmp_ledger
        assert reader.enforcement_rate() == 0.0

    def test_T29_05_02_all_with_verdict(self, tmp_ledger):
        ledger, reader = tmp_ledger
        for _ in range(3):
            ledger.emit(_make_decision(), verdict=_make_verdict())
        assert reader.enforcement_rate() == pytest.approx(1.0)

    def test_T29_05_03_mixed_rate(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision(), verdict=_make_verdict())  # with
        ledger.emit(_make_decision())                           # without
        assert reader.enforcement_rate() == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# T29-06 — escalation_mode_breakdown analytics
# ---------------------------------------------------------------------------

class TestEscalationBreakdown:
    def test_T29_06_01_empty_returns_empty(self, tmp_ledger):
        _, reader = tmp_ledger
        assert reader.escalation_mode_breakdown() == {}

    def test_T29_06_02_advisory_counted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision(), verdict=_make_verdict(mode="advisory"))
        ledger.emit(_make_decision(), verdict=_make_verdict(mode="advisory"))
        assert reader.escalation_mode_breakdown()["advisory"] == 2

    def test_T29_06_03_blocking_counted(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision(0.10, 0.99), verdict=_make_verdict(0.10, 0.99, "blocking"))
        assert reader.escalation_mode_breakdown()["blocking"] == 1

    def test_T29_06_04_no_verdict_counted_as_none(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision())
        assert reader.escalation_mode_breakdown()["none"] == 1


# ---------------------------------------------------------------------------
# T29-07 — history_with_enforcement filter
# ---------------------------------------------------------------------------

class TestHistoryWithEnforcement:
    def test_T29_07_01_returns_only_enforcement_records(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision())                           # no verdict
        ledger.emit(_make_decision(), verdict=_make_verdict())  # with verdict
        recs = reader.history_with_enforcement()
        assert len(recs) == 1
        assert recs[0]["enforcement_present"] is True

    def test_T29_07_02_blocked_only_filter(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_make_decision(0.90, 0.10), verdict=_make_verdict(0.90, 0.10, "advisory"))
        ledger.emit(_make_decision(0.10, 0.99), verdict=_make_verdict(0.10, 0.99, "blocking"))
        blocked = reader.history_with_enforcement(blocked_only=True)
        assert len(blocked) == 1
        assert blocked[0]["blocked"] is True

    def test_T29_07_03_limit_respected(self, tmp_ledger):
        ledger, reader = tmp_ledger
        for _ in range(5):
            ledger.emit(_make_decision(), verdict=_make_verdict())
        recs = reader.history_with_enforcement(limit=3)
        assert len(recs) == 3


# ---------------------------------------------------------------------------
# T29-08 — Inactive ledger (path=None) — no-op on all paths
# ---------------------------------------------------------------------------

class TestInactiveLedger:
    def test_T29_08_01_emit_with_verdict_noop_when_inactive(self):
        ledger = AdmissionAuditLedger()  # no path
        verdict = _make_verdict()
        ledger.emit(_make_decision(), verdict=verdict)  # must not raise

    def test_T29_08_02_inactive_sequence_stays_zero(self):
        ledger = AdmissionAuditLedger()
        ledger.emit(_make_decision(), verdict=_make_verdict())
        assert ledger.sequence == 0
