# SPDX-License-Identifier: Apache-2.0
"""Tests: PressureAuditLedger + PressureAuditReader — Phase 25 / PR-25-01"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.health_pressure_adaptor import HealthPressureAdaptor
from runtime.governance.pressure_audit_ledger import (
    PRESSURE_LEDGER_GENESIS_PREV_HASH,
    PRESSURE_LEDGER_VERSION,
    PressureAuditChainError,
    PressureAuditLedger,
    PressureAuditReader,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _adaptor() -> HealthPressureAdaptor:
    return HealthPressureAdaptor()


def _adj(h: float = 0.70):
    return _adaptor().compute(h)


def _ledger(tmp_path: Path, name: str = "test.jsonl", **kw) -> PressureAuditLedger:
    return PressureAuditLedger(tmp_path / name, **kw)


def _emit_n(ledger: PressureAuditLedger, n: int, health_scores: list | None = None):
    if health_scores is None:
        health_scores = [0.70] * n
    for h in health_scores:
        ledger.emit(_adj(h))


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_new_path_creates_file_on_first_emit(self, tmp_path):
        ledger = _ledger(tmp_path)
        assert not (tmp_path / "test.jsonl").exists()
        ledger.emit(_adj())
        assert (tmp_path / "test.jsonl").exists()

    def test_existing_valid_chain_opens_without_error(self, tmp_path):
        l1 = _ledger(tmp_path)
        _emit_n(l1, 3)
        l2 = PressureAuditLedger(tmp_path / "test.jsonl", chain_verify_on_open=True)
        assert l2.sequence == 3

    def test_chain_verify_on_open_false_skips_check(self, tmp_path):
        p = tmp_path / "bad.jsonl"
        p.write_text('{"corrupted": true}\n', encoding="utf-8")
        # Should not raise with chain_verify_on_open=False
        ledger = PressureAuditLedger(p, chain_verify_on_open=False)
        assert ledger is not None

    def test_corrupted_existing_chain_raises(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 2)
        # Corrupt the file
        content = (tmp_path / "test.jsonl").read_text()
        lines = content.strip().splitlines()
        record = json.loads(lines[0])
        record["pressure_tier"] = "TAMPERED"
        lines[0] = json.dumps(record, sort_keys=True, separators=(",", ":"))
        (tmp_path / "test.jsonl").write_text("\n".join(lines) + "\n")
        with pytest.raises(PressureAuditChainError):
            PressureAuditLedger(tmp_path / "test.jsonl", chain_verify_on_open=True)


# ---------------------------------------------------------------------------
# Emit tests
# ---------------------------------------------------------------------------


class TestEmit:
    def test_emit_writes_parseable_jsonl_record(self, tmp_path):
        ledger = _ledger(tmp_path)
        ledger.emit(_adj(0.70))
        lines = (tmp_path / "test.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["pressure_tier"] == "elevated"

    def test_emit_increments_sequence(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 5)
        assert ledger.sequence == 5
        lines = (tmp_path / "test.jsonl").read_text().strip().splitlines()
        seqs = [json.loads(l)["sequence"] for l in lines]
        assert seqs == list(range(5))

    def test_first_record_prev_hash_is_genesis(self, tmp_path):
        ledger = _ledger(tmp_path)
        ledger.emit(_adj())
        record = json.loads((tmp_path / "test.jsonl").read_text().strip())
        assert record["prev_hash"] == PRESSURE_LEDGER_GENESIS_PREV_HASH

    def test_subsequent_records_link_hashes(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 3)
        lines = (tmp_path / "test.jsonl").read_text().strip().splitlines()
        records = [json.loads(l) for l in lines]
        assert records[1]["prev_hash"] == records[0]["record_hash"]
        assert records[2]["prev_hash"] == records[1]["record_hash"]

    def test_ledger_version_in_every_record(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 3)
        for line in (tmp_path / "test.jsonl").read_text().strip().splitlines():
            assert json.loads(line)["ledger_version"] == PRESSURE_LEDGER_VERSION

    def test_adaptor_version_preserved(self, tmp_path):
        ledger = _ledger(tmp_path)
        ledger.emit(_adj())
        record = json.loads((tmp_path / "test.jsonl").read_text().strip())
        assert record["adaptor_version"] == "24.0"

    def test_adjustment_digest_preserved(self, tmp_path):
        adj = _adj(0.50)
        ledger = _ledger(tmp_path)
        ledger.emit(adj)
        record = json.loads((tmp_path / "test.jsonl").read_text().strip())
        assert record["adjustment_digest"] == adj.adjustment_digest

    def test_health_band_preserved(self, tmp_path):
        ledger = _ledger(tmp_path)
        ledger.emit(_adj(0.50))  # red
        record = json.loads((tmp_path / "test.jsonl").read_text().strip())
        assert record["health_band"] == "red"

    def test_pressure_tier_preserved(self, tmp_path):
        ledger = _ledger(tmp_path)
        ledger.emit(_adj(0.50))  # critical
        record = json.loads((tmp_path / "test.jsonl").read_text().strip())
        assert record["pressure_tier"] == "critical"


# ---------------------------------------------------------------------------
# Chain verification tests
# ---------------------------------------------------------------------------


class TestVerifyChain:
    def test_intact_chain_returns_true(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 5)
        assert ledger.verify_chain() is True

    def test_empty_ledger_verify_returns_true(self, tmp_path):
        ledger = _ledger(tmp_path)
        assert ledger.verify_chain() is True

    def test_tampered_pressure_tier_raises(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 3)
        path = tmp_path / "test.jsonl"
        lines = path.read_text().strip().splitlines()
        record = json.loads(lines[1])
        record["pressure_tier"] = "TAMPERED"
        lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n")
        with pytest.raises(PressureAuditChainError) as exc_info:
            ledger.verify_chain()
        assert exc_info.value.sequence is not None
        assert exc_info.value.detail

    def test_sequence_gap_raises(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 3)
        path = tmp_path / "test.jsonl"
        lines = path.read_text().strip().splitlines()
        record = json.loads(lines[1])
        record["sequence"] = 99  # gap
        lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n")
        with pytest.raises(PressureAuditChainError):
            ledger.verify_chain()

    def test_genesis_sentinel_matches_pattern(self):
        assert PRESSURE_LEDGER_GENESIS_PREV_HASH == "sha256:" + "0" * 64


# ---------------------------------------------------------------------------
# PressureAuditReader tests
# ---------------------------------------------------------------------------


class TestPressureAuditReader:
    def test_nonexistent_path_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PressureAuditReader(tmp_path / "no_such.jsonl")

    def test_history_newest_first(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 5)
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        records = reader.history()
        seqs = [r["sequence"] for r in records]
        assert seqs == sorted(seqs, reverse=True)

    def test_history_filter_by_tier(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 5, [0.90, 0.70, 0.50, 0.90, 0.70])
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        elevated = reader.history(pressure_tier="elevated")
        assert all(r["pressure_tier"] == "elevated" for r in elevated)

    def test_history_limit(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 10)
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        assert len(reader.history(limit=3)) == 3

    def test_history_offset(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 10)
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        all_recs = reader.history()
        offset_recs = reader.history(offset=3)
        assert all_recs[3:] == offset_recs

    def test_history_limit_too_large_raises(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 1)
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        with pytest.raises(ValueError):
            reader.history(limit=501)

    def test_tier_frequency_counts(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 5, [0.90, 0.70, 0.50, 0.90, 0.70])
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        freq = reader.tier_frequency()
        assert freq.get("none", 0) == 2
        assert freq.get("elevated", 0) == 2
        assert freq.get("critical", 0) == 1

    def test_tier_frequency_empty_returns_empty(self, tmp_path):
        ledger = _ledger(tmp_path)
        ledger.emit(_adj())  # one record to create file
        path = tmp_path / "test.jsonl"
        path.write_text("")  # clear
        reader = PressureAuditReader(path)
        assert reader.tier_frequency() == {}

    def test_tier_frequency_series_window(self, tmp_path):
        ledger = _ledger(tmp_path)
        # 10 records: 5 elevated, 5 none
        _emit_n(ledger, 10, [0.70]*5 + [0.90]*5)
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        series = reader.tier_frequency_series(window=5)
        # First window: all elevated; second window: all none
        assert "elevated" in series
        assert abs(series["elevated"][0] - 1.0) < 1e-9
        assert abs(series["elevated"][1] - 0.0) < 1e-9

    def test_tier_frequency_series_absent_tiers_zero(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 10, [0.70]*5 + [0.90]*5)
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        series = reader.tier_frequency_series(window=5)
        # "critical" never appears — should not be in series (or if it is, all zeros)
        if "critical" in series:
            assert all(v == 0.0 for v in series["critical"])

    def test_reader_verify_chain_intact(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 5)
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        assert reader.verify_chain() is True

    def test_round_trip_10_records(self, tmp_path):
        ledger = _ledger(tmp_path)
        _emit_n(ledger, 10)
        reader = PressureAuditReader(tmp_path / "test.jsonl")
        assert len(reader.history(limit=500)) == 10

    def test_replay_determinism(self, tmp_path):
        """Two ledgers built from same adjustments produce identical chain hashes."""
        scores = [0.90, 0.70, 0.70, 0.50, 0.90]
        p1 = tmp_path / "l1.jsonl"
        p2 = tmp_path / "l2.jsonl"
        for p in (p1, p2):
            l = PressureAuditLedger(p)
            for s in scores:
                l.emit(_adaptor().compute(s))
        # Last record_hash should be identical
        last1 = json.loads(p1.read_text().strip().splitlines()[-1])["record_hash"]
        last2 = json.loads(p2.read_text().strip().splitlines()[-1])["record_hash"]
        assert last1 == last2

    def test_pressure_audit_chain_error_has_sequence_and_detail(self, tmp_path):
        err = PressureAuditChainError("test", sequence=3, detail="mismatch")
        assert err.sequence == 3
        assert err.detail == "mismatch"
