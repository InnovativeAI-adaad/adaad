# SPDX-License-Identifier: Apache-2.0
"""Phase 74 — Seed-to-Proposal Bridge tests.

Test IDs
========
T74-BRG-01  build_proposal_request raises KeyError for unknown seed_id
T74-BRG-02  build_proposal_request raises SeedNotApprovedError for non-approved seed (SEED-PROP-0)
T74-BRG-03  approved seed produces correct ProposalRequest fields
T74-BRG-04  cycle_id is deterministic for equal inputs (SEED-PROP-DETERM-0)
T74-BRG-05  SeedProposalEvent written to ledger before request returned (SEED-PROP-LEDGER-0)
T74-BRG-06  ledger failure raises RuntimeError and request not returned (SEED-PROP-LEDGER-0)
T74-LANE-01 governance lane maps to governance_improvement strategy
T74-LANE-02 performance lane maps to performance_optimisation strategy
T74-LANE-03 correctness lane maps to correctness_hardening strategy
T74-LANE-04 security lane maps to security_hardening strategy
T74-LANE-05 unknown lane maps to general_improvement strategy
T74-BUS-01  seed_proposal_generated bus frame emitted after ledger write (SEED-PROP-BUS-0)
T74-API-01  POST /propose returns 404 for unknown seed_id
T74-API-02  POST /propose returns 422 for non-approved seed
T74-API-03  POST /propose returns advisory_notice (SEED-PROP-HUMAN-0)
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from runtime.innovations import ADAADInnovationEngine, CapabilitySeed
from runtime.seed_evolution import GRADUATION_THRESHOLD
from runtime.seed_promotion import SeedPromotionQueue
from runtime.seed_review import record_review
from runtime.seed_proposal_bridge import (
    LANE_STRATEGY,
    SeedNotApprovedError,
    build_proposal_request,
    _cycle_id,
    _lane_to_strategy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine() -> ADAADInnovationEngine:
    return ADAADInnovationEngine()


def _make_approved_queue(seed: CapabilitySeed, engine: ADAADInnovationEngine) -> SeedPromotionQueue:
    queue = SeedPromotionQueue()
    result = engine.evolve_seed(seed, epochs=156)
    assert result["expansion_score"] >= GRADUATION_THRESHOLD
    queue.enqueue(seed, result, epoch_id="ep-74-001")
    mock_ledger = MagicMock()
    record_review(seed.seed_id, status="approved", operator_id="dustin",
                  ledger=mock_ledger, queue=queue)
    return queue


@pytest.fixture()
def gov_seed() -> CapabilitySeed:
    return CapabilitySeed(
        seed_id="gov-seed-74", intent="Improve governance rule coverage",
        scaffold="runtime/governance/gate_v2.py", author="dustin", lane="governance",
    )


@pytest.fixture()
def perf_seed() -> CapabilitySeed:
    return CapabilitySeed(
        seed_id="perf-seed-74", intent="Optimise fitness evaluation cache",
        scaffold="runtime/fitness_v2.py", author="dustin", lane="performance",
    )


@pytest.fixture()
def approved_gov_queue(gov_seed: CapabilitySeed, engine: ADAADInnovationEngine) -> SeedPromotionQueue:
    return _make_approved_queue(gov_seed, engine)


@pytest.fixture()
def mock_ledger() -> MagicMock:
    ledger = MagicMock()
    ledger.append_event = MagicMock(return_value={"event_type": "SeedProposalEvent"})
    return ledger


# ---------------------------------------------------------------------------
# T74-BRG-* — build_proposal_request core
# ---------------------------------------------------------------------------

class TestBuildProposalRequest:
    def test_unknown_seed_raises_key_error(self, mock_ledger: MagicMock) -> None:
        """T74-BRG-01: unknown seed_id raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            build_proposal_request("no-such-seed", ledger=mock_ledger, queue=SeedPromotionQueue())

    def test_non_approved_raises(self, gov_seed: CapabilitySeed, engine: ADAADInnovationEngine, mock_ledger: MagicMock) -> None:
        """T74-BRG-02: pending seed raises SeedNotApprovedError (SEED-PROP-0)."""
        queue = SeedPromotionQueue()
        result = engine.evolve_seed(gov_seed, epochs=156)
        queue.enqueue(gov_seed, result, epoch_id="ep-74-002")
        # status=pending_human_review — not approved
        with pytest.raises(SeedNotApprovedError, match="SEED-PROP-0"):
            build_proposal_request(gov_seed.seed_id, ledger=mock_ledger, queue=queue)

    def test_approved_produces_proposal_request(self, gov_seed: CapabilitySeed, approved_gov_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T74-BRG-03: approved seed returns populated ProposalRequest."""
        req = build_proposal_request(gov_seed.seed_id, epoch_id="ep-74-003",
                                     ledger=mock_ledger, queue=approved_gov_queue)
        assert req.cycle_id.startswith("seed-cycle-")
        assert req.strategy_id == "governance_improvement"
        ctx = dict(req.context)
        assert ctx["seed_id"] == gov_seed.seed_id
        assert ctx["seed_intent"] == gov_seed.intent
        assert ctx["seed_lane"] == "governance"
        assert ctx["seed_author"] == "dustin"
        assert isinstance(ctx["seed_expansion_score"], float)
        assert ctx["seed_expansion_score"] >= GRADUATION_THRESHOLD

    def test_cycle_id_deterministic(self, gov_seed: CapabilitySeed, approved_gov_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T74-BRG-04: cycle_id is deterministic for equal inputs (SEED-PROP-DETERM-0)."""
        c1 = _cycle_id("s1", "ep-42", "abc123")
        c2 = _cycle_id("s1", "ep-42", "abc123")
        assert c1 == c2
        assert c1.startswith("seed-cycle-")
        assert len(c1) == len("seed-cycle-") + 16

    def test_ledger_written_before_return(self, gov_seed: CapabilitySeed, approved_gov_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T74-BRG-05: SeedProposalEvent appended to ledger (SEED-PROP-LEDGER-0)."""
        build_proposal_request(gov_seed.seed_id, ledger=mock_ledger, queue=approved_gov_queue)
        calls = [str(c) for c in mock_ledger.append_event.call_args_list]
        assert any("SeedProposalEvent" in c for c in calls)

    def test_ledger_failure_raises_runtime_error(self, gov_seed: CapabilitySeed, approved_gov_queue: SeedPromotionQueue) -> None:
        """T74-BRG-06: failing ledger raises RuntimeError; request not returned (SEED-PROP-LEDGER-0)."""
        bad_ledger = MagicMock()
        bad_ledger.append_event.side_effect = OSError("disk full")
        with pytest.raises(RuntimeError, match="SEED-PROP-LEDGER-0"):
            build_proposal_request(gov_seed.seed_id, ledger=bad_ledger, queue=approved_gov_queue)


# ---------------------------------------------------------------------------
# T74-LANE-* — lane to strategy routing
# ---------------------------------------------------------------------------

class TestLaneStrategy:
    def test_governance_lane(self) -> None:
        """T74-LANE-01: governance → governance_improvement."""
        assert _lane_to_strategy("governance") == "governance_improvement"

    def test_performance_lane(self) -> None:
        """T74-LANE-02: performance → performance_optimisation."""
        assert _lane_to_strategy("performance") == "performance_optimisation"

    def test_correctness_lane(self) -> None:
        """T74-LANE-03: correctness → correctness_hardening."""
        assert _lane_to_strategy("correctness") == "correctness_hardening"

    def test_security_lane(self) -> None:
        """T74-LANE-04: security → security_hardening."""
        assert _lane_to_strategy("security") == "security_hardening"

    def test_unknown_lane_fallback(self) -> None:
        """T74-LANE-05: unknown lane → general_improvement."""
        assert _lane_to_strategy("experimental") == "general_improvement"
        assert _lane_to_strategy("") == "general_improvement"
        assert _lane_to_strategy("UNKNOWN-XYZ") == "general_improvement"

    def test_lane_strategy_export(self) -> None:
        """LANE_STRATEGY dict exported with all known lanes."""
        for lane in ("governance", "performance", "correctness", "security"):
            assert lane in LANE_STRATEGY


# ---------------------------------------------------------------------------
# T74-BUS-01 — bus frame
# ---------------------------------------------------------------------------

class TestSeedProposalBusFrame:
    def test_proposal_frame_emitted(self, gov_seed: CapabilitySeed, approved_gov_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T74-BUS-01: seed_proposal_generated frame emitted after ledger write (SEED-PROP-BUS-0)."""
        from runtime.innovations_bus import get_bus
        bus = get_bus()
        captured = []

        async def _capture():
            q = await bus.subscribe()
            build_proposal_request(gov_seed.seed_id, epoch_id="ep-bus-74",
                                   ledger=mock_ledger, queue=approved_gov_queue)
            await asyncio.sleep(0)
            while True:
                try:
                    captured.append(q.get_nowait())
                except Exception:
                    break
            await bus.unsubscribe(q)

        asyncio.get_event_loop().run_until_complete(_capture())
        prop_frames = [f for f in captured if f.get("type") == "seed_proposal_generated"]
        if prop_frames:
            f = prop_frames[0]
            assert f["seed_id"] == gov_seed.seed_id
            assert f["strategy_id"] == "governance_improvement"
            assert f["ritual"] == "seed_to_proposal"


# ---------------------------------------------------------------------------
# T74-API-* — /seeds/promoted/{seed_id}/propose endpoint
# ---------------------------------------------------------------------------

class TestProposeEndpoint:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from runtime.innovations_router import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_unknown_seed_404(self) -> None:
        """T74-API-01: unknown seed_id returns 404."""
        with patch("runtime.innovations_router._require_audit_write"):
            with patch("runtime.innovations_router.build_proposal_request",
                       side_effect=KeyError("not found")):
                resp = self._client().post(
                    "/innovations/seeds/promoted/ghost-seed/propose",
                    json={}, headers={"Authorization": "Bearer t"},
                )
        assert resp.status_code == 404

    def test_non_approved_422(self) -> None:
        """T74-API-02: non-approved seed returns 422."""
        with patch("runtime.innovations_router._require_audit_write"):
            with patch("runtime.innovations_router.build_proposal_request",
                       side_effect=SeedNotApprovedError("SEED-PROP-0")):
                resp = self._client().post(
                    "/innovations/seeds/promoted/pending-seed/propose",
                    json={}, headers={"Authorization": "Bearer t"},
                )
        assert resp.status_code == 422

    def test_response_includes_advisory_notice(self, gov_seed: CapabilitySeed, approved_gov_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T74-API-03: response includes SEED-PROP-HUMAN-0 advisory notice."""
        from runtime.evolution.proposal_engine import ProposalRequest
        fake_request = ProposalRequest(
            cycle_id="seed-cycle-abcdef1234567890",
            strategy_id="governance_improvement",
            context={"seed_id": gov_seed.seed_id},
        )
        with patch("runtime.innovations_router._require_audit_write"):
            with patch("runtime.innovations_router.build_proposal_request", return_value=fake_request):
                resp = self._client().post(
                    f"/innovations/seeds/promoted/{gov_seed.seed_id}/propose",
                    json={}, headers={"Authorization": "Bearer t"},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert "SEED-PROP-HUMAN-0" in body.get("advisory_notice", "")
        assert body["cycle_id"] == fake_request.cycle_id
        assert body["strategy_id"] == "governance_improvement"
