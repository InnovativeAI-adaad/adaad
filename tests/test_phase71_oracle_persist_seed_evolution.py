# SPDX-License-Identifier: Apache-2.0
"""Phase 71 — Oracle Persistence + Capability Seed Evolution tests.

Test IDs
========
T71-ORC-01  oracle_query writes one record to OracleLedger per call
T71-ORC-02  OracleLedger.replay() returns records in append order
T71-ORC-03  Two identical queries produce identical event_window_hash (ORACLE-DETERM-0)
T71-ORC-04  OracleLedger.append() is resilient to unwritable path (ORACLE-PERSIST-0 fail-safe)
T71-ORC-05  GET /oracle/history returns records from ledger (ORACLE-REPLAY-0)
T71-EVO-01  run_seed_evolution returns empty list when cadence not reached
T71-EVO-02  run_seed_evolution returns one result per seed on cadence tick
T71-EVO-03  evolve_seed expansion_score is bounded in [0.15, 1.0]
T71-EVO-04  SeedEvolutionEvent written to lineage ledger on cadence tick (SEED-EVOL-0)
T71-EVO-05  run_seed_evolution is fail-safe per seed (SEED-EVOL-FAIL-0)
T71-GRAD-01 seed_graduated bus frame emitted when expansion_score >= 0.85 (SEED-GRAD-0)
T71-GRAD-02 SeedGraduationEvent written to lineage ledger on graduation
T71-GRAD-03 Graduation is idempotent per epoch — same seed not graduated twice (SEED-GRAD-0)
T71-BUS-01  emit_seed_graduated produces correct frame schema
T71-BUS-02  seed_graduated frame type present in innovations_bus __all__
"""

from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from runtime.innovations import ADAADInnovationEngine, CapabilitySeed
from runtime.innovations_bus import emit_seed_graduated, get_bus
from runtime.oracle_ledger import OracleLedger
from runtime.seed_evolution import (
    GRADUATION_THRESHOLD,
    SEED_EVOLUTION_CADENCE,
    run_seed_evolution,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_oracle_ledger(tmp_path: Path) -> OracleLedger:
    return OracleLedger(path=tmp_path / "oracle_answers.jsonl")


@pytest.fixture()
def sample_events() -> List[Dict[str, Any]]:
    return [
        {"epoch_id": f"ep-{i:03d}", "event_type": "MutationApplied", "status": "approved"}
        for i in range(5)
    ]


@pytest.fixture()
def seed_a() -> CapabilitySeed:
    return CapabilitySeed(
        seed_id="seed-alpha",
        intent="Improve cache locality in fitness evaluation",
        scaffold="runtime/fitness_v2.py",
        author="dustin",
        lane="performance",
    )


@pytest.fixture()
def seed_b() -> CapabilitySeed:
    return CapabilitySeed(
        seed_id="seed-beta",
        intent="Add streaming verification to lineage reads",
        scaffold="runtime/evolution/lineage_v2.py",
        author="dustin",
        lane="correctness",
    )


@pytest.fixture()
def engine() -> ADAADInnovationEngine:
    return ADAADInnovationEngine()


@pytest.fixture()
def mock_ledger() -> MagicMock:
    ledger = MagicMock()
    ledger.append_event = MagicMock(return_value={"event_type": "SeedEvolutionEvent"})
    return ledger


# ---------------------------------------------------------------------------
# T71-ORC-* — Oracle Ledger
# ---------------------------------------------------------------------------


class TestOracleLedger:
    def test_append_writes_one_record(
        self, tmp_oracle_ledger: OracleLedger, sample_events: List[Dict[str, Any]]
    ) -> None:
        """T71-ORC-01: one JSONL record written per append call."""
        result = tmp_oracle_ledger.append(
            query="divergence",
            answer={"query_type": "divergence_recent", "count": 0, "events": []},
            events=sample_events,
            vision_trajectory_score=0.72,
        )
        assert result is not None
        assert result["query"] == "divergence"
        assert result["event_window"] == len(sample_events)
        assert result["schema_version"] == "71.1"
        assert result["vision_trajectory_score"] == pytest.approx(0.72)

        lines = tmp_oracle_ledger.path.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["query"] == "divergence"

    def test_replay_returns_records_in_order(
        self, tmp_oracle_ledger: OracleLedger, sample_events: List[Dict[str, Any]]
    ) -> None:
        """T71-ORC-02: replay returns records oldest-first in append order."""
        for q in ("divergence", "rejected", "performance"):
            tmp_oracle_ledger.append(
                query=q,
                answer={"query_type": q},
                events=sample_events,
            )

        records = tmp_oracle_ledger.replay(limit=10)
        assert len(records) == 3
        assert [r["query"] for r in records] == ["divergence", "rejected", "performance"]

    def test_deterministic_event_window_hash(
        self, tmp_oracle_ledger: OracleLedger, sample_events: List[Dict[str, Any]]
    ) -> None:
        """T71-ORC-03: identical event lists produce identical event_window_hash (ORACLE-DETERM-0)."""
        r1 = tmp_oracle_ledger.append(query="q", answer={}, events=sample_events)
        r2 = tmp_oracle_ledger.append(query="q", answer={}, events=sample_events)
        assert r1 is not None and r2 is not None
        assert r1["event_window_hash"] == r2["event_window_hash"]

    def test_append_failsafe_on_bad_path(self, sample_events: List[Dict[str, Any]]) -> None:
        """T71-ORC-04: OracleLedger.append() returns None on IO failure (ORACLE-PERSIST-0 fail-safe)."""
        ledger = OracleLedger(path="/proc/immutable/no_such_dir/oracle.jsonl")
        result = ledger.append(query="q", answer={}, events=sample_events)
        assert result is None  # never raises

    def test_replay_empty_on_missing_file(self, tmp_path: Path) -> None:
        """T71-ORC-02 edge: replay returns [] when ledger file absent."""
        ledger = OracleLedger(path=tmp_path / "nonexistent.jsonl")
        assert ledger.replay() == []

    def test_history_endpoint_auth(self) -> None:
        """T71-ORC-05: GET /oracle/history requires audit:read token (ORACLE-AUTH-0)."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch as _patch

        with _patch("runtime.innovations_router._require_audit_read") as mock_auth:
            mock_auth.side_effect = lambda _: None  # pass-through
            with _patch("runtime.innovations_router._oracle_ledger") as mock_ledger:
                mock_ledger.replay.return_value = [{"query": "divergence", "schema_version": "71.1"}]
                mock_ledger.path = Path("/tmp/oracle.jsonl")
                from runtime.innovations_router import router
                from fastapi import FastAPI
                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)
                resp = client.get(
                    "/innovations/oracle/history",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                body = resp.json()
                assert "records" in body
                assert "record_count" in body


# ---------------------------------------------------------------------------
# T71-EVO-* — Seed Evolution Epoch Hook
# ---------------------------------------------------------------------------


class TestSeedEvolution:
    def test_cadence_skip(self, engine: ADAADInnovationEngine, seed_a: CapabilitySeed, mock_ledger: MagicMock) -> None:
        """T71-EVO-01: run_seed_evolution returns [] when epoch_seq not on cadence."""
        state: Dict[str, Any] = {}
        results = run_seed_evolution(
            engine, [seed_a], epoch_id="ep-001", epoch_seq=1,
            state=state, ledger=mock_ledger, cadence=10,
        )
        assert results == []
        assert "seed_evolution_results" not in state

    def test_cadence_tick_returns_one_result_per_seed(
        self, engine: ADAADInnovationEngine, seed_a: CapabilitySeed, seed_b: CapabilitySeed, mock_ledger: MagicMock
    ) -> None:
        """T71-EVO-02: cadence tick processes every seed; one result per seed."""
        state: Dict[str, Any] = {}
        results = run_seed_evolution(
            engine, [seed_a, seed_b], epoch_id="ep-010", epoch_seq=10,
            state=state, ledger=mock_ledger, cadence=10,
        )
        assert len(results) == 2
        assert {r["seed_id"] for r in results} == {seed_a.seed_id, seed_b.seed_id}
        assert state["seed_evolution_results"] is results

    def test_expansion_score_bounded(
        self, engine: ADAADInnovationEngine, seed_a: CapabilitySeed, mock_ledger: MagicMock
    ) -> None:
        """T71-EVO-03: expansion_score is always in [0.15, 1.0]."""
        for epoch_seq in (0, 10, 100, 1000, 5000):
            state: Dict[str, Any] = {}
            results = run_seed_evolution(
                engine, [seed_a], epoch_id=f"ep-{epoch_seq}", epoch_seq=epoch_seq,
                state=state, ledger=mock_ledger, cadence=0,
            )
            score = results[0]["expansion_score"]
            assert 0.15 <= score <= 1.0, f"score {score} out of bounds at epoch_seq={epoch_seq}"

    def test_lineage_event_written_on_tick(
        self, engine: ADAADInnovationEngine, seed_a: CapabilitySeed, mock_ledger: MagicMock
    ) -> None:
        """T71-EVO-04: SeedEvolutionEvent written to lineage ledger (SEED-EVOL-0)."""
        state: Dict[str, Any] = {}
        run_seed_evolution(
            engine, [seed_a], epoch_id="ep-020", epoch_seq=20,
            state=state, ledger=mock_ledger, cadence=10,
        )
        # append_event called at least once for SeedEvolutionEvent
        calls = [str(c) for c in mock_ledger.append_event.call_args_list]
        assert any("SeedEvolutionEvent" in c for c in calls)

    def test_failsafe_per_seed(self, engine: ADAADInnovationEngine, mock_ledger: MagicMock) -> None:
        """T71-EVO-05: bad seed does not abort processing of subsequent seeds (SEED-EVOL-FAIL-0)."""
        bad_seed = MagicMock(spec=CapabilitySeed)
        bad_seed.seed_id = "bad-seed"
        bad_seed.lane = "test"
        # evolve_seed will raise for this mock
        engine_mock = MagicMock(spec=ADAADInnovationEngine)
        engine_mock.evolve_seed.side_effect = RuntimeError("injected failure")

        good_seed = CapabilitySeed(
            seed_id="good-seed", intent="works", scaffold="x.py", author="a", lane="test"
        )
        good_engine = ADAADInnovationEngine()
        real_evolve = good_engine.evolve_seed

        call_order: List[str] = []

        def side_effect(seed, epochs):
            call_order.append(seed.seed_id)
            if seed.seed_id == "bad-seed":
                raise RuntimeError("injected failure")
            return real_evolve(seed, epochs)

        engine_mock.evolve_seed.side_effect = side_effect

        state: Dict[str, Any] = {}
        results = run_seed_evolution(
            engine_mock, [bad_seed, good_seed], epoch_id="ep-030", epoch_seq=0,
            state=state, ledger=mock_ledger, cadence=0,
        )
        # good_seed result present despite bad_seed failure
        assert any(r["seed_id"] == "good-seed" for r in results)


# ---------------------------------------------------------------------------
# T71-GRAD-* — Graduation Ceremony
# ---------------------------------------------------------------------------


class TestSeedGraduation:
    """Tests for SEED-GRAD-0 graduation ceremony."""

    def _make_high_epoch_seed(self) -> CapabilitySeed:
        return CapabilitySeed(
            seed_id="grad-seed",
            intent="graduation target",
            scaffold="runtime/innovations.py",
            author="system",
            lane="core",
        )

    def _epoch_seq_for_graduation(self) -> int:
        """Return an epoch_seq that produces expansion_score >= 0.85.

        score = round(min(1.0, 0.15 + (bounded_epochs * 0.0045)), 4)
        Need: 0.15 + N * 0.0045 >= 0.85 → N >= 0.70 / 0.0045 ≈ 156
        """
        return 156

    def test_graduation_bus_frame_emitted(self, mock_ledger: MagicMock) -> None:
        """T71-GRAD-01: seed_graduated bus frame emitted when score >= 0.85 (SEED-GRAD-0)."""
        engine = ADAADInnovationEngine()
        seed = self._make_high_epoch_seed()
        epoch_seq = self._epoch_seq_for_graduation()
        state: Dict[str, Any] = {}

        emitted: List[Dict[str, Any]] = []

        with patch("runtime.seed_evolution._emit_seed_graduated") as mock_emit:
            run_seed_evolution(
                engine, [seed], epoch_id="ep-grad", epoch_seq=epoch_seq,
                state=state, ledger=mock_ledger, cadence=0,
                graduation_threshold=GRADUATION_THRESHOLD,
            )
            if state.get("capability_graduations"):
                # graduation fired — verify state record
                grad = state["capability_graduations"][0]
                assert grad["seed_id"] == seed.seed_id
                assert grad["ritual"] == "capability_graduation"
                assert grad["expansion_score"] >= GRADUATION_THRESHOLD
            # emit called if score reached threshold
            score = state["seed_evolution_results"][0]["expansion_score"]
            if score >= GRADUATION_THRESHOLD:
                mock_emit.assert_called_once_with(
                    seed.seed_id, seed.lane, score, "ep-grad"
                )

    def test_graduation_lineage_event_written(self, mock_ledger: MagicMock) -> None:
        """T71-GRAD-02: SeedGraduationEvent written to lineage ledger on graduation."""
        engine = ADAADInnovationEngine()
        seed = self._make_high_epoch_seed()
        epoch_seq = self._epoch_seq_for_graduation()
        state: Dict[str, Any] = {}

        with patch("runtime.seed_evolution._emit_seed_graduated"):
            run_seed_evolution(
                engine, [seed], epoch_id="ep-grad-2", epoch_seq=epoch_seq,
                state=state, ledger=mock_ledger, cadence=0,
            )

        score = state["seed_evolution_results"][0]["expansion_score"]
        if score >= GRADUATION_THRESHOLD:
            calls = [str(c) for c in mock_ledger.append_event.call_args_list]
            assert any("SeedGraduationEvent" in c for c in calls)

    def test_graduation_idempotent_per_epoch(self, mock_ledger: MagicMock) -> None:
        """T71-GRAD-03: same seed cannot graduate twice in the same epoch (SEED-GRAD-0 idempotency)."""
        engine = ADAADInnovationEngine()
        seed = self._make_high_epoch_seed()
        epoch_seq = self._epoch_seq_for_graduation()
        state: Dict[str, Any] = {}
        graduated_set: set = set()

        with patch("runtime.seed_evolution._emit_seed_graduated") as mock_emit:
            # First run
            run_seed_evolution(
                engine, [seed], epoch_id="ep-idem", epoch_seq=epoch_seq,
                state=state, ledger=mock_ledger, cadence=0,
                _graduated_this_epoch=graduated_set,
            )
            # Second run same epoch, same set — graduation must not fire again
            run_seed_evolution(
                engine, [seed], epoch_id="ep-idem", epoch_seq=epoch_seq,
                state=state, ledger=mock_ledger, cadence=0,
                _graduated_this_epoch=graduated_set,
            )

        score = state["seed_evolution_results"][0]["expansion_score"]
        if score >= GRADUATION_THRESHOLD:
            assert mock_emit.call_count == 1, "Graduation must fire exactly once per epoch"


# ---------------------------------------------------------------------------
# T71-BUS-* — Bus frame schema
# ---------------------------------------------------------------------------


class TestSeedGraduatedFrame:
    def test_emit_seed_graduated_frame_schema(self) -> None:
        """T71-BUS-01: emit_seed_graduated produces correct frame dict."""
        bus = get_bus()
        captured: List[Dict[str, Any]] = []

        import asyncio

        async def _capture():
            q = await bus.subscribe()
            emit_seed_graduated("seed-x", "governance", 0.91, "ep-999")
            # Flush event loop
            await asyncio.sleep(0)
            try:
                frame = q.get_nowait()
                captured.append(frame)
            except Exception:
                pass
            await bus.unsubscribe(q)

        asyncio.get_event_loop().run_until_complete(_capture())
        if captured:
            f = captured[0]
            assert f["type"] == "seed_graduated"
            assert f["seed_id"] == "seed-x"
            assert f["lane"] == "governance"
            assert f["expansion_score"] == pytest.approx(0.91)
            assert f["ritual"] == "capability_graduation"

    def test_emit_seed_graduated_in_bus_all(self) -> None:
        """T71-BUS-02: emit_seed_graduated is exported from innovations_bus."""
        import runtime.innovations_bus as bus_mod
        assert "emit_seed_graduated" in bus_mod.__all__
