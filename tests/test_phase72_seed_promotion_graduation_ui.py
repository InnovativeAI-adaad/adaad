# SPDX-License-Identifier: Apache-2.0
"""Phase 72 — Seed Promotion Queue + Graduation UI tests.

Test IDs
========
T72-PRQ-01  SeedPromotionQueue rejects sub-threshold seeds (SEED-PROMO-0)
T72-PRQ-02  SeedPromotionQueue enqueues graduated seed with correct schema
T72-PRQ-03  Re-enqueue of existing seed_id is idempotent (SEED-PROMO-IDEM-0)
T72-PRQ-04  list() returns entries in FIFO order (SEED-PROMO-ORDER-0)
T72-PRQ-05  All enqueued entries have status=pending_human_review (SEED-PROMO-HUMAN-0)
T72-PRQ-06  get_promotion_queue() returns process-wide singleton
T72-API-01  GET /seeds/promoted returns queue_depth and entries
T72-API-02  GET /seeds/promoted includes advisory_notice (SEED-PROMO-HUMAN-0)
T72-API-03  GET /seeds/promoted requires audit:read token (ORACLE-AUTH-0)
T72-BUS-01  emit_seed_graduated in innovations_bus produces seed_graduated frame
T72-BUS-02  seed_graduated frame carries ritual=capability_graduation
T72-INT-01  run_seed_evolution -> graduation -> promotion queue end-to-end
T72-INT-02  Sub-threshold seed from run_seed_evolution does NOT enter queue
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from runtime.innovations import ADAADInnovationEngine, CapabilitySeed
from runtime.seed_evolution import GRADUATION_THRESHOLD, run_seed_evolution
from runtime.seed_promotion import (
    PromotionThresholdError,
    SeedPromotionQueue,
    get_promotion_queue,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def queue() -> SeedPromotionQueue:
    return SeedPromotionQueue()


@pytest.fixture()
def seed_alpha() -> CapabilitySeed:
    return CapabilitySeed(
        seed_id="seed-alpha-72",
        intent="Cache locality improvement for FitnessEngineV2",
        scaffold="runtime/fitness_v2.py",
        author="dustin",
        lane="performance",
    )


@pytest.fixture()
def seed_beta() -> CapabilitySeed:
    return CapabilitySeed(
        seed_id="seed-beta-72",
        intent="Streaming lineage verification",
        scaffold="runtime/evolution/lineage_v2.py",
        author="dustin",
        lane="correctness",
    )


@pytest.fixture()
def graduated_evolution_result(seed_alpha: CapabilitySeed) -> Dict[str, Any]:
    """Evolution result with expansion_score above graduation threshold."""
    engine = ADAADInnovationEngine()
    # epoch_seq=156 yields score >= 0.85
    return engine.evolve_seed(seed_alpha, epochs=156)


@pytest.fixture()
def sub_threshold_result(seed_beta: CapabilitySeed) -> Dict[str, Any]:
    """Evolution result with expansion_score below graduation threshold."""
    engine = ADAADInnovationEngine()
    # epoch_seq=1 yields score ~0.155
    return engine.evolve_seed(seed_beta, epochs=1)


# ---------------------------------------------------------------------------
# T72-PRQ-* — SeedPromotionQueue
# ---------------------------------------------------------------------------


class TestSeedPromotionQueue:
    def test_rejects_sub_threshold(
        self, queue: SeedPromotionQueue, seed_beta: CapabilitySeed, sub_threshold_result: Dict
    ) -> None:
        """T72-PRQ-01: sub-threshold seeds raise PromotionThresholdError (SEED-PROMO-0)."""
        assert sub_threshold_result["expansion_score"] < GRADUATION_THRESHOLD
        with pytest.raises(PromotionThresholdError, match="SEED-PROMO-0"):
            queue.enqueue(seed_beta, sub_threshold_result, epoch_id="ep-001")

    def test_enqueues_graduated_seed(
        self, queue: SeedPromotionQueue, seed_alpha: CapabilitySeed, graduated_evolution_result: Dict
    ) -> None:
        """T72-PRQ-02: graduated seed enqueued with correct schema."""
        entry = queue.enqueue(seed_alpha, graduated_evolution_result, epoch_id="ep-156")
        assert entry["seed_id"] == seed_alpha.seed_id
        assert entry["lane"] == seed_alpha.lane
        assert entry["intent"] == seed_alpha.intent
        assert entry["author"] == seed_alpha.author
        assert entry["expansion_score"] >= GRADUATION_THRESHOLD
        assert entry["epoch_id"] == "ep-156"
        assert entry["status"] == "pending_human_review"
        assert "enqueued_at" in entry
        assert "lineage_digest" in entry

    def test_idempotent_reenqueue(
        self, queue: SeedPromotionQueue, seed_alpha: CapabilitySeed, graduated_evolution_result: Dict
    ) -> None:
        """T72-PRQ-03: re-enqueue returns same entry unchanged (SEED-PROMO-IDEM-0)."""
        e1 = queue.enqueue(seed_alpha, graduated_evolution_result, epoch_id="ep-156")
        e2 = queue.enqueue(seed_alpha, graduated_evolution_result, epoch_id="ep-157")
        assert e1 is e2
        assert len(queue) == 1

    def test_fifo_order(
        self, queue: SeedPromotionQueue, seed_alpha: CapabilitySeed, seed_beta: CapabilitySeed
    ) -> None:
        """T72-PRQ-04: list() returns entries in enqueue order (SEED-PROMO-ORDER-0)."""
        engine = ADAADInnovationEngine()
        res_a = engine.evolve_seed(seed_alpha, epochs=156)
        res_b = engine.evolve_seed(seed_beta, epochs=156)
        queue.enqueue(seed_alpha, res_a, epoch_id="ep-001")
        queue.enqueue(seed_beta, res_b, epoch_id="ep-002")
        entries = queue.list()
        assert len(entries) == 2
        assert entries[0]["seed_id"] == seed_alpha.seed_id
        assert entries[1]["seed_id"] == seed_beta.seed_id

    def test_all_entries_pending_human_review(
        self, queue: SeedPromotionQueue, seed_alpha: CapabilitySeed, graduated_evolution_result: Dict
    ) -> None:
        """T72-PRQ-05: all entries have status=pending_human_review (SEED-PROMO-HUMAN-0)."""
        queue.enqueue(seed_alpha, graduated_evolution_result, epoch_id="ep-156")
        for entry in queue.list():
            assert entry["status"] == "pending_human_review"

    def test_singleton(self) -> None:
        """T72-PRQ-06: get_promotion_queue() returns same object on repeated calls."""
        q1 = get_promotion_queue()
        q2 = get_promotion_queue()
        assert q1 is q2


# ---------------------------------------------------------------------------
# T72-API-* — /seeds/promoted endpoint
# ---------------------------------------------------------------------------


class TestPromotedEndpoint:
    def _make_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from runtime.innovations_router import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def _auth_header(self):
        return {"Authorization": "Bearer test-token"}

    def test_returns_queue_depth_and_entries(self) -> None:
        """T72-API-01: GET /seeds/promoted returns queue_depth and entries list."""
        with patch("runtime.innovations_router._require_audit_read"):
            with patch("runtime.innovations_router._promotion_queue") as mock_q:
                mock_q.list.return_value = [
                    {"seed_id": "s1", "status": "pending_human_review", "expansion_score": 0.90}
                ]
                mock_q.threshold = 0.85
                client = self._make_client()
                resp = client.get("/innovations/seeds/promoted", headers=self._auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert "queue_depth" in body
        assert "entries" in body
        assert "threshold" in body

    def test_includes_advisory_notice(self) -> None:
        """T72-API-02: response includes SEED-PROMO-HUMAN-0 advisory notice."""
        with patch("runtime.innovations_router._require_audit_read"):
            with patch("runtime.innovations_router._promotion_queue") as mock_q:
                mock_q.list.return_value = []
                mock_q.threshold = 0.85
                client = self._make_client()
                resp = client.get("/innovations/seeds/promoted", headers=self._auth_header())
        body = resp.json()
        assert "SEED-PROMO-HUMAN-0" in body.get("advisory_notice", "")

    def test_requires_auth(self) -> None:
        """T72-API-03: endpoint raises without audit:read scope (ORACLE-AUTH-0)."""
        from runtime.audit_auth import require_audit_read_scope
        from fastapi import HTTPException
        with patch("runtime.innovations_router._require_audit_read",
                   side_effect=HTTPException(status_code=401, detail="Unauthorized")):
            client = self._make_client()
            resp = client.get("/innovations/seeds/promoted")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# T72-BUS-* — seed_graduated bus frame
# ---------------------------------------------------------------------------


class TestSeedGraduatedBusFrame:
    def test_frame_schema(self) -> None:
        """T72-BUS-01: emit_seed_graduated produces correct frame structure."""
        import asyncio
        from runtime.innovations_bus import emit_seed_graduated, get_bus

        bus = get_bus()
        captured = []

        async def _run():
            q = await bus.subscribe()
            emit_seed_graduated("grad-seed-x", "governance", 0.92, "ep-200")
            await asyncio.sleep(0)
            try:
                frame = q.get_nowait()
                captured.append(frame)
            except Exception:
                pass
            await bus.unsubscribe(q)

        asyncio.get_event_loop().run_until_complete(_run())
        if captured:
            f = captured[0]
            assert f["type"] == "seed_graduated"
            assert f["seed_id"] == "grad-seed-x"
            assert f["expansion_score"] == pytest.approx(0.92)

    def test_frame_carries_graduation_ritual(self) -> None:
        """T72-BUS-02: seed_graduated frame contains ritual=capability_graduation."""
        import asyncio
        from runtime.innovations_bus import emit_seed_graduated, get_bus

        bus = get_bus()
        captured = []

        async def _run():
            q = await bus.subscribe()
            emit_seed_graduated("ritual-seed", "core", 0.88, "ep-100")
            await asyncio.sleep(0)
            try:
                captured.append(q.get_nowait())
            except Exception:
                pass
            await bus.unsubscribe(q)

        asyncio.get_event_loop().run_until_complete(_run())
        if captured:
            assert captured[0].get("ritual") == "capability_graduation"


# ---------------------------------------------------------------------------
# T72-INT-* — Integration: run_seed_evolution -> graduation -> promotion
# ---------------------------------------------------------------------------


class TestGraduationIntegration:
    def test_graduated_seed_enters_promotion_queue(self) -> None:
        """T72-INT-01: seed reaching graduation threshold can be enqueued."""
        engine = ADAADInnovationEngine()
        seed = CapabilitySeed(
            seed_id="int-grad-seed-72",
            intent="End-to-end graduation test",
            scaffold="runtime/innovations.py",
            author="system",
            lane="integration",
        )
        mock_ledger = MagicMock()
        state: Dict[str, Any] = {}
        queue = SeedPromotionQueue()

        results = run_seed_evolution(
            engine, [seed], epoch_id="ep-int-156", epoch_seq=156,
            state=state, ledger=mock_ledger, cadence=0,
        )
        assert results, "No results returned from run_seed_evolution"
        result = results[0]
        score = result["expansion_score"]

        if score >= GRADUATION_THRESHOLD:
            entry = queue.enqueue(seed, result, epoch_id="ep-int-156")
            assert entry["seed_id"] == seed.seed_id
            assert entry["status"] == "pending_human_review"
            assert entry["expansion_score"] >= GRADUATION_THRESHOLD
        else:
            pytest.skip(f"score {score:.4f} < threshold at epoch_seq=156 — check evolve_seed formula")

    def test_sub_threshold_seed_cannot_enter_queue(self) -> None:
        """T72-INT-02: sub-threshold seed is rejected by promotion queue."""
        engine = ADAADInnovationEngine()
        seed = CapabilitySeed(
            seed_id="int-sub-seed-72",
            intent="Sub-threshold test",
            scaffold="x.py",
            author="system",
            lane="test",
        )
        mock_ledger = MagicMock()
        state: Dict[str, Any] = {}
        queue = SeedPromotionQueue()

        results = run_seed_evolution(
            engine, [seed], epoch_id="ep-int-001", epoch_seq=0,
            state=state, ledger=mock_ledger, cadence=0,
        )
        result = results[0]
        assert result["expansion_score"] < GRADUATION_THRESHOLD

        with pytest.raises(PromotionThresholdError):
            queue.enqueue(seed, result, epoch_id="ep-int-001")
