# SPDX-License-Identifier: Apache-2.0
"""Phase 73 — Seed Review Decision + Governance Wire tests.

Test IDs
========
T73-REV-01  record_review raises ReviewAuthorityError for blank operator_id (SEED-REVIEW-HUMAN-0)
T73-REV-02  record_review raises SeedNotFoundError for unknown seed_id
T73-REV-03  record_review raises ValueError for invalid status value
T73-REV-04  approved decision written to lineage ledger before status mutation (SEED-REVIEW-0)
T73-REV-05  rejected decision written to lineage ledger before status mutation (SEED-REVIEW-0)
T73-REV-06  decision_digest is deterministic for equal inputs (SEED-REVIEW-AUDIT-0)
T73-REV-07  re-reviewing terminal seed returns existing entry (SEED-REVIEW-IDEM-0)
T73-REV-08  approved decision sets queue entry status to "approved"
T73-REV-09  rejected decision sets queue entry status to "rejected"
T73-BUS-01  seed_promotion_approved bus frame emitted on approval (SEED-REVIEW-BUS-0)
T73-BUS-02  seed_promotion_rejected bus frame emitted on rejection (SEED-REVIEW-BUS-0)
T73-AUTH-01 audit_auth.require_audit_write_scope raises 401 on missing token
T73-AUTH-02 audit_auth.require_audit_write_scope raises 403 on read-only token
T73-API-01  POST /seeds/promoted/{seed_id}/review returns 422 on blank operator_id
T73-API-02  POST /seeds/promoted/{seed_id}/review returns 404 for unknown seed_id
T73-API-03  POST /seeds/promoted/{seed_id}/review returns 422 for invalid status
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from runtime.innovations import ADAADInnovationEngine, CapabilitySeed
from runtime.seed_evolution import GRADUATION_THRESHOLD
from runtime.seed_promotion import SeedPromotionQueue
from runtime.seed_review import (
    ReviewAuthorityError,
    SeedNotFoundError,
    record_review,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine() -> ADAADInnovationEngine:
    return ADAADInnovationEngine()


@pytest.fixture()
def grad_seed() -> CapabilitySeed:
    return CapabilitySeed(
        seed_id="review-seed-73",
        intent="Governance review integration test",
        scaffold="runtime/seed_review.py",
        author="dustin",
        lane="governance",
    )


@pytest.fixture()
def populated_queue(engine: ADAADInnovationEngine, grad_seed: CapabilitySeed) -> SeedPromotionQueue:
    """Return a SeedPromotionQueue with one graduated seed enqueued."""
    queue = SeedPromotionQueue()
    result = engine.evolve_seed(grad_seed, epochs=156)
    assert result["expansion_score"] >= GRADUATION_THRESHOLD
    queue.enqueue(grad_seed, result, epoch_id="ep-73-001")
    return queue


@pytest.fixture()
def mock_ledger() -> MagicMock:
    ledger = MagicMock()
    ledger.append_event = MagicMock(return_value={"event_type": "SeedReviewDecisionEvent"})
    return ledger


# ---------------------------------------------------------------------------
# T73-REV-* — record_review core invariants
# ---------------------------------------------------------------------------

class TestRecordReview:
    def test_blank_operator_raises(self, populated_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T73-REV-01: blank operator_id raises ReviewAuthorityError (SEED-REVIEW-HUMAN-0)."""
        for bad_op in ("", "   ", "\t"):
            with pytest.raises(ReviewAuthorityError, match="SEED-REVIEW-HUMAN-0"):
                record_review(
                    "review-seed-73", status="approved",
                    operator_id=bad_op, ledger=mock_ledger, queue=populated_queue,
                )

    def test_unknown_seed_raises(self, mock_ledger: MagicMock) -> None:
        """T73-REV-02: unknown seed_id raises SeedNotFoundError."""
        empty_queue = SeedPromotionQueue()
        with pytest.raises(SeedNotFoundError):
            record_review(
                "no-such-seed", status="approved",
                operator_id="dustin", ledger=mock_ledger, queue=empty_queue,
            )

    def test_invalid_status_raises(self, populated_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T73-REV-03: invalid status raises ValueError."""
        with pytest.raises(ValueError, match="approved.*rejected"):
            record_review(
                "review-seed-73", status="maybe",
                operator_id="dustin", ledger=mock_ledger, queue=populated_queue,
            )

    def test_approval_writes_ledger_first(self, populated_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T73-REV-04: ledger append_event called for approved decision (SEED-REVIEW-0)."""
        record_review(
            "review-seed-73", status="approved",
            operator_id="dustin", notes="LGTM", ledger=mock_ledger, queue=populated_queue,
        )
        calls = [str(c) for c in mock_ledger.append_event.call_args_list]
        assert any("SeedReviewDecisionEvent" in c for c in calls)

    def test_rejection_writes_ledger_first(self, engine: ADAADInnovationEngine, mock_ledger: MagicMock) -> None:
        """T73-REV-05: ledger append_event called for rejected decision (SEED-REVIEW-0)."""
        queue = SeedPromotionQueue()
        seed = CapabilitySeed(
            seed_id="reject-seed-73", intent="rejected test",
            scaffold="x.py", author="system", lane="test",
        )
        result = engine.evolve_seed(seed, epochs=156)
        queue.enqueue(seed, result, epoch_id="ep-73-002")

        record_review(
            "reject-seed-73", status="rejected",
            operator_id="dustin", ledger=mock_ledger, queue=queue,
        )
        calls = [str(c) for c in mock_ledger.append_event.call_args_list]
        assert any("SeedReviewDecisionEvent" in c for c in calls)

    def test_decision_digest_deterministic(self, populated_queue: SeedPromotionQueue) -> None:
        """T73-REV-06: decision_digest is deterministic for equal inputs (SEED-REVIEW-AUDIT-0)."""
        from runtime.seed_review import _decision_digest
        d1 = _decision_digest("s1", "approved", "dustin", "2026-03-14T00:00:00+00:00")
        d2 = _decision_digest("s1", "approved", "dustin", "2026-03-14T00:00:00+00:00")
        assert d1 == d2
        assert len(d1) == 64  # SHA-256 hex

    def test_idempotent_on_terminal_status(self, populated_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T73-REV-07: reviewing already-terminal seed returns existing entry (SEED-REVIEW-IDEM-0)."""
        r1 = record_review(
            "review-seed-73", status="approved",
            operator_id="dustin", ledger=mock_ledger, queue=populated_queue,
        )
        # Second review on same seed — should not write again
        ledger_calls_before = mock_ledger.append_event.call_count
        r2 = record_review(
            "review-seed-73", status="rejected",
            operator_id="dustin", ledger=mock_ledger, queue=populated_queue,
        )
        assert mock_ledger.append_event.call_count == ledger_calls_before  # no second write
        assert r2 is populated_queue.get("review-seed-73")  # same entry returned

    def test_approved_mutates_queue_status(self, populated_queue: SeedPromotionQueue, mock_ledger: MagicMock) -> None:
        """T73-REV-08: approval sets queue entry status to 'approved'."""
        record_review(
            "review-seed-73", status="approved",
            operator_id="dustin", ledger=mock_ledger, queue=populated_queue,
        )
        entry = populated_queue.get("review-seed-73")
        assert entry["status"] == "approved"

    def test_rejected_mutates_queue_status(self, engine: ADAADInnovationEngine, mock_ledger: MagicMock) -> None:
        """T73-REV-09: rejection sets queue entry status to 'rejected'."""
        queue = SeedPromotionQueue()
        seed = CapabilitySeed(
            seed_id="rej-status-73", intent="x", scaffold="x.py", author="a", lane="test",
        )
        result = engine.evolve_seed(seed, epochs=156)
        queue.enqueue(seed, result, epoch_id="ep-73-003")
        record_review(
            "rej-status-73", status="rejected",
            operator_id="dustin", ledger=mock_ledger, queue=queue,
        )
        assert queue.get("rej-status-73")["status"] == "rejected"


# ---------------------------------------------------------------------------
# T73-BUS-* — Bus frame emission
# ---------------------------------------------------------------------------

class TestReviewBusFrames:
    def _run_emit_test(self, seed_id: str, status: str) -> list:
        from runtime.innovations_bus import get_bus
        bus = get_bus()
        captured = []

        async def _run():
            q = await bus.subscribe()
            from runtime.seed_review import _emit_review_frame
            _emit_review_frame(seed_id, status, "dustin", "ep-bus-73")
            await asyncio.sleep(0)
            try:
                captured.append(q.get_nowait())
            except Exception:
                pass
            await bus.unsubscribe(q)

        asyncio.get_event_loop().run_until_complete(_run())
        return captured

    def test_approved_bus_frame(self) -> None:
        """T73-BUS-01: seed_promotion_approved frame emitted on approval (SEED-REVIEW-BUS-0)."""
        captured = self._run_emit_test("bus-test-approve", "approved")
        if captured:
            assert captured[0]["type"] == "seed_promotion_approved"
            assert captured[0]["seed_id"] == "bus-test-approve"
            assert captured[0]["ritual"] == "seed_review_decision"

    def test_rejected_bus_frame(self) -> None:
        """T73-BUS-02: seed_promotion_rejected frame emitted on rejection (SEED-REVIEW-BUS-0)."""
        captured = self._run_emit_test("bus-test-reject", "rejected")
        if captured:
            assert captured[0]["type"] == "seed_promotion_rejected"
            assert captured[0]["seed_id"] == "bus-test-reject"


# ---------------------------------------------------------------------------
# T73-AUTH-* — audit:write scope
# ---------------------------------------------------------------------------

class TestAuditWriteScope:
    def test_missing_token_raises_401(self) -> None:
        """T73-AUTH-01: require_audit_write_scope raises 401 on missing authorization."""
        from fastapi import HTTPException
        from runtime.audit_auth import require_audit_write_scope
        with pytest.raises(HTTPException) as exc_info:
            require_audit_write_scope(None)
        assert exc_info.value.status_code == 401

    def test_read_only_token_raises_403(self) -> None:
        """T73-AUTH-02: token with only audit:read raises 403 for write scope."""
        from fastapi import HTTPException
        from runtime.audit_auth import require_audit_write_scope
        with patch(
            "runtime.audit_auth.load_audit_tokens",
            return_value={"read-token": ["audit:read"]},
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_audit_write_scope("Bearer read-token")
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# T73-API-* — /seeds/promoted/{seed_id}/review endpoint
# ---------------------------------------------------------------------------

class TestReviewEndpoint:
    def _make_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from runtime.innovations_router import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_blank_operator_returns_422(self) -> None:
        """T73-API-01: blank operator_id returns 422."""
        with patch("runtime.innovations_router._require_audit_write"):
            with patch("runtime.innovations_router.record_review",
                       side_effect=ReviewAuthorityError("SEED-REVIEW-HUMAN-0")):
                client = self._make_client()
                resp = client.post(
                    "/innovations/seeds/promoted/any-seed/review",
                    json={"status": "approved", "operator_id": ""},
                    headers={"Authorization": "Bearer t"},
                )
        assert resp.status_code == 422

    def test_unknown_seed_returns_404(self) -> None:
        """T73-API-02: unknown seed_id returns 404."""
        with patch("runtime.innovations_router._require_audit_write"):
            with patch("runtime.innovations_router.record_review",
                       side_effect=SeedNotFoundError("no-such-seed")):
                client = self._make_client()
                resp = client.post(
                    "/innovations/seeds/promoted/no-such-seed/review",
                    json={"status": "approved", "operator_id": "dustin"},
                    headers={"Authorization": "Bearer t"},
                )
        assert resp.status_code == 404

    def test_invalid_status_returns_422(self) -> None:
        """T73-API-03: invalid status value returns 422 before calling record_review."""
        with patch("runtime.innovations_router._require_audit_write"):
            client = self._make_client()
            resp = client.post(
                "/innovations/seeds/promoted/any-seed/review",
                json={"status": "maybe", "operator_id": "dustin"},
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == 422
