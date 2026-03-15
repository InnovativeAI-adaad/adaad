# SPDX-License-Identifier: Apache-2.0
"""Phase 76 — Seed CEL Outcome Recorder: test suite.

T76-OUT-01..08  record_cel_outcome() core behaviour
T76-LNK-01..04  SEED-OUTCOME-LINK-0 field validation
T76-DET-01..03  SEED-OUTCOME-DETERM-0 digest determinism
T76-IDM-01..03  SEED-OUTCOME-IDEM-0 idempotency
T76-AUD-01..03  SEED-OUTCOME-AUDIT-0 ledger write behaviour
T76-API-01..04  POST /innovations/seeds/{seed_id}/cel-outcome endpoint
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from runtime.seed_cel_outcome import (
    OUTCOME_STATUSES,
    SeedOutcomeLinkError,
    SeedOutcomeStatusError,
    clear_outcome_registry,
    get_cel_outcome,
    record_cel_outcome,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeLedger:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []
        self.fail = False

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.fail:
            raise RuntimeError("ledger write failure injected")
        entry = {"event_type": event_type, **payload}
        self.events.append(entry)
        return entry


class _FakeBus:
    def __init__(self) -> None:
        self.frames: List[Dict[str, Any]] = []
        self.fail = False

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if self.fail:
            raise RuntimeError("bus emit failure injected")
        self.frames.append({"type": event_type, **data})


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure a fresh idempotency registry before every test."""
    clear_outcome_registry()
    yield
    clear_outcome_registry()


@pytest.fixture()
def ledger() -> _FakeLedger:
    return _FakeLedger()


@pytest.fixture()
def bus() -> _FakeBus:
    return _FakeBus()


# ---------------------------------------------------------------------------
# T76-OUT — core record_cel_outcome() behaviour
# ---------------------------------------------------------------------------


class TestRecordCelOutcomeCore:
    """T76-OUT-01..08"""

    def test_returns_outcome_dict(self, ledger, bus):
        """T76-OUT-01: returns a well-formed outcome dict."""
        out = record_cel_outcome(
            "seed-a", "cycle-1", "ep-100", "success",
            fitness_delta=0.05, mutation_count=2,
            ledger=ledger, bus=bus,
        )
        assert out["seed_id"] == "seed-a"
        assert out["cycle_id"] == "cycle-1"
        assert out["epoch_id"] == "ep-100"
        assert out["outcome_status"] == "success"
        assert out["fitness_delta"] == pytest.approx(0.05)
        assert out["mutation_count"] == 2

    def test_outcome_digest_present(self, ledger, bus):
        """T76-OUT-02: outcome_digest is a non-empty hex string."""
        out = record_cel_outcome(
            "seed-b", "cycle-2", "ep-101", "partial",
            ledger=ledger, bus=bus,
        )
        assert isinstance(out["outcome_digest"], str)
        assert len(out["outcome_digest"]) == 64

    def test_recorded_at_present(self, ledger, bus):
        """T76-OUT-03: recorded_at is an ISO-8601 timestamp."""
        out = record_cel_outcome(
            "seed-c", "cycle-3", "ep-102", "failed",
            ledger=ledger, bus=bus,
        )
        assert "T" in out["recorded_at"]

    def test_notes_carried(self, ledger, bus):
        """T76-OUT-04: optional notes field is persisted."""
        out = record_cel_outcome(
            "seed-d", "cycle-4", "ep-103", "skipped",
            notes="dry run — no mutations attempted",
            ledger=ledger, bus=bus,
        )
        assert out["notes"] == "dry run — no mutations attempted"

    def test_all_valid_statuses_accepted(self, ledger, bus):
        """T76-OUT-05: all four outcome statuses are accepted."""
        for i, status in enumerate(sorted(OUTCOME_STATUSES)):
            clear_outcome_registry()
            out = record_cel_outcome(
                f"seed-{i}", f"cycle-{i}", f"ep-{i}", status,
                ledger=ledger, bus=bus,
            )
            assert out["outcome_status"] == status

    def test_get_cel_outcome_returns_recorded(self, ledger, bus):
        """T76-OUT-06: get_cel_outcome() returns the stored record."""
        record_cel_outcome(
            "seed-e", "cycle-5", "ep-104", "success",
            ledger=ledger, bus=bus,
        )
        fetched = get_cel_outcome("seed-e", "cycle-5")
        assert fetched is not None
        assert fetched["outcome_status"] == "success"

    def test_get_cel_outcome_missing_returns_none(self):
        """T76-OUT-07: get_cel_outcome() returns None for unknown key."""
        result = get_cel_outcome("unknown-seed", "unknown-cycle")
        assert result is None

    def test_default_fitness_and_mutations_are_zero(self, ledger, bus):
        """T76-OUT-08: defaults for fitness_delta and mutation_count are 0."""
        out = record_cel_outcome(
            "seed-f", "cycle-6", "ep-105", "success",
            ledger=ledger, bus=bus,
        )
        assert out["fitness_delta"] == pytest.approx(0.0)
        assert out["mutation_count"] == 0


# ---------------------------------------------------------------------------
# T76-LNK — SEED-OUTCOME-LINK-0 field validation
# ---------------------------------------------------------------------------


class TestLinkFieldValidation:
    """T76-LNK-01..04"""

    def test_empty_seed_id_raises(self, ledger, bus):
        """T76-LNK-01: empty seed_id raises SeedOutcomeLinkError."""
        with pytest.raises(SeedOutcomeLinkError, match="seed_id"):
            record_cel_outcome("", "cycle-x", "ep-x", "success", ledger=ledger, bus=bus)

    def test_empty_cycle_id_raises(self, ledger, bus):
        """T76-LNK-02: empty cycle_id raises SeedOutcomeLinkError."""
        with pytest.raises(SeedOutcomeLinkError, match="cycle_id"):
            record_cel_outcome("seed-x", "", "ep-x", "success", ledger=ledger, bus=bus)

    def test_empty_epoch_id_raises(self, ledger, bus):
        """T76-LNK-03: empty epoch_id raises SeedOutcomeLinkError."""
        with pytest.raises(SeedOutcomeLinkError, match="epoch_id"):
            record_cel_outcome("seed-x", "cycle-x", "", "success", ledger=ledger, bus=bus)

    def test_invalid_status_raises(self, ledger, bus):
        """T76-LNK-04: unknown outcome_status raises SeedOutcomeStatusError."""
        with pytest.raises(SeedOutcomeStatusError, match="bogus"):
            record_cel_outcome("seed-x", "cycle-x", "ep-x", "bogus", ledger=ledger, bus=bus)


# ---------------------------------------------------------------------------
# T76-DET — SEED-OUTCOME-DETERM-0 digest determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """T76-DET-01..03"""

    def test_digest_is_deterministic(self, ledger, bus):
        """T76-DET-01: same inputs produce the same outcome_digest."""
        out1 = record_cel_outcome(
            "seed-g", "cycle-7", "ep-106", "success", ledger=ledger, bus=bus,
        )
        clear_outcome_registry()
        out2 = record_cel_outcome(
            "seed-g", "cycle-7", "ep-106", "success", ledger=_FakeLedger(), bus=_FakeBus(),
        )
        assert out1["outcome_digest"] == out2["outcome_digest"]

    def test_different_status_produces_different_digest(self, ledger, bus):
        """T76-DET-02: different outcome_status → different digest."""
        out_success = record_cel_outcome(
            "seed-h", "cycle-8", "ep-107", "success", ledger=ledger, bus=bus,
        )
        clear_outcome_registry()
        out_failed = record_cel_outcome(
            "seed-h", "cycle-8", "ep-107", "failed", ledger=_FakeLedger(), bus=_FakeBus(),
        )
        assert out_success["outcome_digest"] != out_failed["outcome_digest"]

    def test_digest_matches_manual_sha256(self):
        """T76-DET-03: outcome_digest equals manually computed SHA-256."""
        from runtime.seed_cel_outcome import _outcome_digest  # noqa: PLC0415
        expected = _outcome_digest("seed-i", "cycle-9", "ep-108", "partial")
        payload = json.dumps(
            {"seed_id": "seed-i", "cycle_id": "cycle-9", "epoch_id": "ep-108", "outcome_status": "partial"},
            sort_keys=True,
        ).encode()
        assert expected == hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# T76-IDM — SEED-OUTCOME-IDEM-0 idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """T76-IDM-01..03"""

    def test_duplicate_call_returns_first_record(self, ledger, bus):
        """T76-IDM-01: second call for same (seed_id, cycle_id) returns first record."""
        out1 = record_cel_outcome(
            "seed-j", "cycle-10", "ep-109", "success", fitness_delta=0.1,
            ledger=ledger, bus=bus,
        )
        out2 = record_cel_outcome(
            "seed-j", "cycle-10", "ep-200", "failed", fitness_delta=0.9,
            ledger=ledger, bus=bus,
        )
        assert out1 is out2

    def test_duplicate_does_not_write_second_ledger_entry(self, ledger, bus):
        """T76-IDM-02: only one ledger event written on duplicate calls."""
        record_cel_outcome("seed-k", "cycle-11", "ep-110", "success", ledger=ledger, bus=bus)
        record_cel_outcome("seed-k", "cycle-11", "ep-111", "partial", ledger=ledger, bus=bus)
        outcome_events = [e for e in ledger.events if e["event_type"] == "SeedCELOutcomeEvent"]
        assert len(outcome_events) == 1

    def test_different_cycle_id_is_new_record(self, ledger, bus):
        """T76-IDM-03: different cycle_id for same seed creates a distinct record."""
        out1 = record_cel_outcome("seed-l", "cycle-12a", "ep-112", "success", ledger=ledger, bus=bus)
        out2 = record_cel_outcome("seed-l", "cycle-12b", "ep-112", "failed",  ledger=_FakeLedger(), bus=_FakeBus())
        assert out1["outcome_digest"] != out2["outcome_digest"]
        assert out1["outcome_status"] == "success"
        assert out2["outcome_status"] == "failed"


# ---------------------------------------------------------------------------
# T76-AUD — SEED-OUTCOME-AUDIT-0 ledger behaviour
# ---------------------------------------------------------------------------


class TestAuditLedger:
    """T76-AUD-01..03"""

    def test_ledger_event_written_with_correct_fields(self, ledger, bus):
        """T76-AUD-01: SeedCELOutcomeEvent has required fields in ledger."""
        record_cel_outcome(
            "seed-m", "cycle-13", "ep-113", "success",
            fitness_delta=0.03, mutation_count=5,
            ledger=ledger, bus=bus,
        )
        events = [e for e in ledger.events if e["event_type"] == "SeedCELOutcomeEvent"]
        assert len(events) == 1
        ev = events[0]
        assert ev["seed_id"] == "seed-m"
        assert ev["cycle_id"] == "cycle-13"
        assert ev["epoch_id"] == "ep-113"
        assert ev["outcome_status"] == "success"
        assert ev["fitness_delta"] == pytest.approx(0.03)
        assert ev["mutation_count"] == 5
        assert ev["ritual"] == "seed_cel_outcome"

    def test_ledger_failure_raises_and_no_registry_entry(self, bus):
        """T76-AUD-02: ledger write failure raises RuntimeError; registry not updated."""
        bad_ledger = _FakeLedger()
        bad_ledger.fail = True
        with pytest.raises(RuntimeError, match="SEED-OUTCOME-AUDIT-0"):
            record_cel_outcome(
                "seed-n", "cycle-14", "ep-114", "success",
                ledger=bad_ledger, bus=bus,
            )
        assert get_cel_outcome("seed-n", "cycle-14") is None

    def test_bus_failure_does_not_raise(self, ledger):
        """T76-AUD-03: bus emit failure is non-fatal (IBUS-FAILSAFE-0)."""
        bad_bus = _FakeBus()
        bad_bus.fail = True
        # Must NOT raise
        out = record_cel_outcome(
            "seed-o", "cycle-15", "ep-115", "partial",
            ledger=ledger, bus=bad_bus,
        )
        assert out["outcome_status"] == "partial"


# ---------------------------------------------------------------------------
# T76-API — POST /innovations/seeds/{seed_id}/cel-outcome endpoint
# ---------------------------------------------------------------------------


class TestCelOutcomeEndpoint:
    """T76-API-01..04"""

    def _make_client(self):
        from fastapi import FastAPI                  # noqa: PLC0415
        from fastapi.testclient import TestClient    # noqa: PLC0415
        from runtime.innovations_router import router  # noqa: PLC0415
        _app = FastAPI()
        _app.include_router(router)
        return TestClient(_app)

    def test_happy_path_returns_outcome(self, ledger, bus):
        """T76-API-01: valid payload returns 200 with outcome dict."""
        client = self._make_client()
        with (
            patch("runtime.innovations_router._require_audit_write"),
            patch("runtime.seed_cel_outcome.record_cel_outcome", return_value={
                "seed_id":        "seed-api-1",
                "cycle_id":       "cycle-api-1",
                "epoch_id":       "ep-api-1",
                "outcome_status": "success",
                "fitness_delta":  0.07,
                "mutation_count": 3,
                "notes":          "",
                "recorded_at":    "2026-03-15T00:00:00+00:00",
                "outcome_digest": "a" * 64,
            }),
        ):
            resp = client.post(
                "/innovations/seeds/seed-api-1/cel-outcome",
                json={
                    "cycle_id":       "cycle-api-1",
                    "epoch_id":       "ep-api-1",
                    "outcome_status": "success",
                    "fitness_delta":  0.07,
                    "mutation_count": 3,
                },
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["seed_id"] == "seed-api-1"
        assert data["outcome"]["outcome_status"] == "success"
        assert "advisory_notice" in data

    def test_missing_required_fields_returns_422(self):
        """T76-API-02: empty cycle_id raises SeedOutcomeLinkError → 422."""
        client = self._make_client()
        with patch("runtime.innovations_router._require_audit_write"):
            resp = client.post(
                "/innovations/seeds/seed-api-2/cel-outcome",
                json={"cycle_id": "", "epoch_id": "ep-x", "outcome_status": "success"},
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == 422

    def test_invalid_status_returns_422(self):
        """T76-API-03: unrecognised outcome_status returns 422."""
        client = self._make_client()
        with patch("runtime.innovations_router._require_audit_write"):
            resp = client.post(
                "/innovations/seeds/seed-api-3/cel-outcome",
                json={
                    "cycle_id":       "cycle-api-3",
                    "epoch_id":       "ep-api-3",
                    "outcome_status": "unknown_status",
                },
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == 422

    def test_missing_auth_returns_401(self):
        """T76-API-04: missing Authorization header returns 401."""
        client = self._make_client()
        resp = client.post(
            "/innovations/seeds/seed-api-4/cel-outcome",
            json={
                "cycle_id":       "cycle-api-4",
                "epoch_id":       "ep-api-4",
                "outcome_status": "success",
            },
        )
        assert resp.status_code == 401
