# SPDX-License-Identifier: Apache-2.0
"""Tests for ThreatScanLedger + ThreatScanReader — ADAAD Phase 30.

Test IDs: T30-01 through T30-09
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.threat_scan_ledger import (
    THREAT_SCAN_LEDGER_VERSION,
    ThreatScanChainError,
    ThreatScanLedger,
    ThreatScanReader,
)
from runtime.governance.threat_monitor import ThreatMonitor, default_detectors


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _scan(
    *,
    epoch_id: str = "e-1",
    recommendation: str = "continue",
    risk_score: float = 0.10,
    risk_level: str = "low",
    triggered: bool = False,
) -> dict:
    """Build a minimal ThreatMonitor-shaped scan result dict."""
    findings = [{
        "detector": "test_detector",
        "triggered": triggered,
        "severity": risk_score if triggered else 0.0,
        "recommendation": recommendation,
        "reason": "test",
    }]
    return {
        "epoch_id": epoch_id,
        "mutation_count": 5,
        "recommendation": recommendation,
        "risk": {"score": risk_score, "risk_level": risk_level, "attributions": []},
        "findings": findings,
        "scan_digest": f"sha256:{'a' * 64}",
    }


def _real_scan(events=None):
    """Run actual ThreatMonitor.scan() with default detectors."""
    monitor = ThreatMonitor(detectors=default_detectors())
    return monitor.scan(epoch_id="ep-real", mutation_count=3, events=events or [])


@pytest.fixture
def tmp_ledger(tmp_path):
    p = tmp_path / "threat_scan.jsonl"
    return ThreatScanLedger(path=p), ThreatScanReader(p)


# ---------------------------------------------------------------------------
# T30-01 — Inactive ledger (path=None)
# ---------------------------------------------------------------------------

class TestInactiveLedger:
    def test_T30_01_01_emit_noop(self):
        ledger = ThreatScanLedger()
        ledger.emit(_scan())  # must not raise

    def test_T30_01_02_sequence_stays_zero(self):
        ledger = ThreatScanLedger()
        ledger.emit(_scan())
        assert ledger.sequence == 0

    def test_T30_01_03_path_is_none(self):
        assert ThreatScanLedger().path is None

    def test_T30_01_04_verify_returns_false(self):
        assert ThreatScanLedger().verify_chain() is False

    def test_T30_01_05_no_file_created(self, tmp_path):
        ledger = ThreatScanLedger()
        ledger.emit(_scan())
        assert not any(tmp_path.iterdir())


# ---------------------------------------------------------------------------
# T30-02 — Active ledger: emit and sequence
# ---------------------------------------------------------------------------

class TestActiveLedger:
    def test_T30_02_01_emit_creates_file(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan())
        assert ledger.path.exists()

    def test_T30_02_02_sequence_increments(self, tmp_ledger):
        ledger, reader = tmp_ledger
        for i in range(4):
            ledger.emit(_scan(epoch_id=f"e-{i}"))
        assert ledger.sequence == 4

    def test_T30_02_03_record_fields_present(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(epoch_id="ep-x", recommendation="escalate",
                          risk_score=0.55, risk_level="high", triggered=True))
        rec = reader.history()[0]
        assert rec["epoch_id"] == "ep-x"
        assert rec["recommendation"] == "escalate"
        assert rec["risk_score"] == pytest.approx(0.55)
        assert rec["risk_level"] == "high"
        assert rec["triggered_count"] == 1
        assert rec["sequence"] == 0
        assert rec["ledger_version"] == THREAT_SCAN_LEDGER_VERSION

    def test_T30_02_04_record_hash_present(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan())
        rec = reader.history()[0]
        assert rec["record_hash"].startswith("sha256:")
        assert len(rec["record_hash"]) == 71  # "sha256:" + 64 hex chars

    def test_T30_02_05_timestamp_in_record(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan())
        assert "timestamp_iso" in reader.history()[0]

    def test_T30_02_06_prev_hash_genesis_for_first(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan())
        rec = reader.history()[0]
        assert rec["prev_hash"] == "sha256:" + "0" * 64

    def test_T30_02_07_prev_hash_chain_links(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(epoch_id="e-0"))
        ledger.emit(_scan(epoch_id="e-1"))
        recs = reader.history()
        assert recs[1]["prev_hash"] == recs[0]["record_hash"]


# ---------------------------------------------------------------------------
# T30-03 — Chain verification
# ---------------------------------------------------------------------------

class TestChainVerification:
    def test_T30_03_01_chain_valid_after_multiple_emits(self, tmp_ledger):
        ledger, reader = tmp_ledger
        for i in range(5):
            ledger.emit(_scan(epoch_id=f"e-{i}"))
        assert reader.verify_chain() is True

    def test_T30_03_02_chain_error_on_tampered_hash(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan())
        # Tamper with the record
        content = ledger.path.read_text()
        rec = json.loads(content.strip())
        rec["record_hash"] = "sha256:" + "b" * 64
        ledger.path.write_text(json.dumps(rec) + "\n")
        with pytest.raises(ThreatScanChainError):
            reader.verify_chain()

    def test_T30_03_03_chain_resume_on_reopen(self, tmp_path):
        p = tmp_path / "scan.jsonl"
        ledger1 = ThreatScanLedger(path=p)
        for i in range(3):
            ledger1.emit(_scan(epoch_id=f"e-{i}"))
        # Reopen
        ledger2 = ThreatScanLedger(path=p, chain_verify_on_open=True)
        assert ledger2.sequence == 3
        ledger2.emit(_scan(epoch_id="e-3"))
        reader = ThreatScanReader(p)
        assert reader.verify_chain() is True
        assert len(reader.history()) == 4

    def test_T30_03_04_ledger_version_is_30(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan())
        assert reader.history()[0]["ledger_version"] == "30.0"
        assert THREAT_SCAN_LEDGER_VERSION == "30.0"


# ---------------------------------------------------------------------------
# T30-04 — Real ThreatMonitor scan output accepted
# ---------------------------------------------------------------------------

class TestRealScanIntegration:
    def test_T30_04_01_real_scan_continue_recorded(self, tmp_ledger):
        ledger, reader = tmp_ledger
        scan = _real_scan()
        ledger.emit(scan)
        rec = reader.history()[0]
        assert rec["recommendation"] == "continue"
        assert rec["triggered_count"] == 0

    def test_T30_04_02_real_scan_halt_recorded(self, tmp_ledger):
        ledger, reader = tmp_ledger
        # 3 failure events → failure_spike_detector triggers halt
        events = [{"status": "failed"}, {"status": "failed"}, {"status": "failed"}]
        scan = _real_scan(events=events)
        ledger.emit(scan)
        rec = reader.history()[0]
        assert rec["recommendation"] == "halt"
        assert rec["triggered_count"] >= 1

    def test_T30_04_03_chain_valid_after_real_scan(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_real_scan())
        ledger.emit(_real_scan(events=[{"status": "failed"} for _ in range(3)]))
        assert reader.verify_chain() is True


# ---------------------------------------------------------------------------
# T30-05 — history() filtering
# ---------------------------------------------------------------------------

class TestHistoryFiltering:
    def test_T30_05_01_limit(self, tmp_ledger):
        ledger, reader = tmp_ledger
        for i in range(6):
            ledger.emit(_scan(epoch_id=f"e-{i}"))
        assert len(reader.history(limit=3)) == 3

    def test_T30_05_02_recommendation_filter(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(recommendation="continue"))
        ledger.emit(_scan(recommendation="escalate"))
        ledger.emit(_scan(recommendation="halt"))
        recs = reader.history(recommendation_filter="escalate")
        assert len(recs) == 1
        assert recs[0]["recommendation"] == "escalate"

    def test_T30_05_03_triggered_only(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(triggered=False))
        ledger.emit(_scan(triggered=True, recommendation="escalate"))
        recs = reader.history(triggered_only=True)
        assert len(recs) == 1
        assert recs[0]["triggered_count"] >= 1

    def test_T30_05_04_empty_filter_returns_empty(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(recommendation="continue"))
        assert reader.history(recommendation_filter="halt") == []


# ---------------------------------------------------------------------------
# T30-06 — recommendation_breakdown()
# ---------------------------------------------------------------------------

class TestRecommendationBreakdown:
    def test_T30_06_01_empty_returns_empty(self, tmp_ledger):
        _, reader = tmp_ledger
        assert reader.recommendation_breakdown() == {}

    def test_T30_06_02_counts_correct(self, tmp_ledger):
        ledger, reader = tmp_ledger
        for _ in range(3):
            ledger.emit(_scan(recommendation="continue"))
        ledger.emit(_scan(recommendation="escalate"))
        bd = reader.recommendation_breakdown()
        assert bd["continue"] == 3
        assert bd["escalate"] == 1


# ---------------------------------------------------------------------------
# T30-07 — triggered_rate() / escalation_rate() / avg_risk_score()
# ---------------------------------------------------------------------------

class TestAnalytics:
    def test_T30_07_01_triggered_rate_empty(self, tmp_ledger):
        _, reader = tmp_ledger
        assert reader.triggered_rate() == 0.0

    def test_T30_07_02_triggered_rate_half(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(triggered=False))
        ledger.emit(_scan(triggered=True, recommendation="escalate"))
        assert reader.triggered_rate() == pytest.approx(0.5)

    def test_T30_07_03_escalation_rate_empty(self, tmp_ledger):
        _, reader = tmp_ledger
        assert reader.escalation_rate() == 0.0

    def test_T30_07_04_escalation_rate_all_continue(self, tmp_ledger):
        ledger, reader = tmp_ledger
        for _ in range(4):
            ledger.emit(_scan(recommendation="continue"))
        assert reader.escalation_rate() == 0.0

    def test_T30_07_05_escalation_rate_mixed(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(recommendation="continue"))
        ledger.emit(_scan(recommendation="halt"))
        assert reader.escalation_rate() == pytest.approx(0.5)

    def test_T30_07_06_avg_risk_score_empty(self, tmp_ledger):
        _, reader = tmp_ledger
        assert reader.avg_risk_score() == 0.0

    def test_T30_07_07_avg_risk_score_correct(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(risk_score=0.2))
        ledger.emit(_scan(risk_score=0.4))
        assert reader.avg_risk_score() == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# T30-08 — risk_level_breakdown()
# ---------------------------------------------------------------------------

class TestRiskLevelBreakdown:
    def test_T30_08_01_empty(self, tmp_ledger):
        _, reader = tmp_ledger
        assert reader.risk_level_breakdown() == {}

    def test_T30_08_02_counts(self, tmp_ledger):
        ledger, reader = tmp_ledger
        ledger.emit(_scan(risk_level="low"))
        ledger.emit(_scan(risk_level="low"))
        ledger.emit(_scan(risk_level="high"))
        bd = reader.risk_level_breakdown()
        assert bd["low"] == 2
        assert bd["high"] == 1


# ---------------------------------------------------------------------------
# T30-09 — Determinism: same scan → same record_hash (across two ledgers)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_T30_09_01_identical_scans_identical_record_hash(self, tmp_path):
        scan = _scan(epoch_id="ep-det", recommendation="escalate",
                     risk_score=0.55, risk_level="high", triggered=True)
        p1 = tmp_path / "a.jsonl"
        p2 = tmp_path / "b.jsonl"
        ThreatScanLedger(path=p1).emit(scan)
        ThreatScanLedger(path=p2).emit(scan)
        r1 = ThreatScanReader(p1).history()[0]["record_hash"]
        r2 = ThreatScanReader(p2).history()[0]["record_hash"]
        assert r1 == r2

    def test_T30_09_02_different_epochs_different_hashes(self, tmp_path):
        p1 = tmp_path / "a.jsonl"
        p2 = tmp_path / "b.jsonl"
        ThreatScanLedger(path=p1).emit(_scan(epoch_id="ep-1"))
        ThreatScanLedger(path=p2).emit(_scan(epoch_id="ep-2"))
        r1 = ThreatScanReader(p1).history()[0]["record_hash"]
        r2 = ThreatScanReader(p2).history()[0]["record_hash"]
        assert r1 != r2
