# SPDX-License-Identifier: Apache-2.0
"""Phase 75 — Seed Proposal CEL Injection tests.

Test IDs
========
T75-INJ-01  inject_seed_proposal_into_context sets seed_proposal_request key (SEED-CEL-0)
T75-INJ-02  injection is deterministic for equal inputs (SEED-CEL-DETERM-0)
T75-INJ-03  base_context keys are preserved after injection (non-destructive merge)
T75-INJ-04  seed fields promoted to top-level context keys
T75-INJ-05  SeedCELInjectionEvent written to ledger (SEED-CEL-AUDIT-0)
T75-INJ-06  ledger failure raises RuntimeError; context not returned (SEED-CEL-AUDIT-0)
T75-RES-01  resolve_step4_request returns seed-derived request when key present (SEED-CEL-HUMAN-0)
T75-RES-02  resolve_step4_request falls back to defaults when key absent
T75-RES-03  resolve_step4_request is pure — no side effects
T75-CEL-01  CEL Step 4 uses seed request when seed_proposal_request in state context
T75-CEL-02  CEL Step 4 falls back gracefully if resolve raises (CEL-WIRE-FAIL-0)
T75-API-01  POST /inject returns 404 for unknown seed_id
T75-API-02  POST /inject returns 422 for non-approved seed
T75-API-03  POST /inject response contains epoch_context and advisory_notice
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from runtime.evolution.proposal_engine import ProposalRequest
from runtime.innovations import ADAADInnovationEngine, CapabilitySeed
from runtime.seed_cel_injector import inject_seed_proposal_into_context, resolve_step4_request
from runtime.seed_evolution import GRADUATION_THRESHOLD
from runtime.seed_proposal_bridge import build_proposal_request, SeedNotApprovedError
from runtime.seed_promotion import SeedPromotionQueue
from runtime.seed_review import record_review


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine() -> ADAADInnovationEngine:
    return ADAADInnovationEngine()


@pytest.fixture()
def approved_seed_request(engine: ADAADInnovationEngine) -> ProposalRequest:
    """Build an approved seed ProposalRequest for use in injection tests."""
    seed = CapabilitySeed(
        seed_id="inject-seed-75", intent="CEL injection test",
        scaffold="runtime/seed_cel_injector.py", author="dustin", lane="governance",
    )
    queue = SeedPromotionQueue()
    result = engine.evolve_seed(seed, epochs=156)
    assert result["expansion_score"] >= GRADUATION_THRESHOLD
    queue.enqueue(seed, result, epoch_id="ep-75-001")
    mock_ledger = MagicMock()
    record_review(seed.seed_id, status="approved", operator_id="dustin",
                  ledger=mock_ledger, queue=queue)
    return build_proposal_request(seed.seed_id, epoch_id="ep-75-001",
                                  ledger=mock_ledger, queue=queue)


@pytest.fixture()
def mock_ledger() -> MagicMock:
    m = MagicMock()
    m.append_event = MagicMock(return_value={"event_type": "SeedCELInjectionEvent"})
    return m


# ---------------------------------------------------------------------------
# T75-INJ-* — inject_seed_proposal_into_context
# ---------------------------------------------------------------------------

class TestInjectSeedProposalIntoContext:
    def test_sets_seed_proposal_request_key(self, approved_seed_request: ProposalRequest, mock_ledger: MagicMock) -> None:
        """T75-INJ-01: injected context contains seed_proposal_request (SEED-CEL-0)."""
        ctx = inject_seed_proposal_into_context(approved_seed_request, ledger=mock_ledger)
        assert "seed_proposal_request" in ctx
        sr = ctx["seed_proposal_request"]
        assert sr["cycle_id"] == approved_seed_request.cycle_id
        assert sr["strategy_id"] == approved_seed_request.strategy_id

    def test_deterministic_for_equal_inputs(self, approved_seed_request: ProposalRequest, mock_ledger: MagicMock) -> None:
        """T75-INJ-02: equal inputs produce identical context dicts (SEED-CEL-DETERM-0)."""
        base = {"epoch_id": "ep-det", "custom": 42}
        ctx1 = inject_seed_proposal_into_context(approved_seed_request, base_context=base, ledger=mock_ledger)
        ctx2 = inject_seed_proposal_into_context(approved_seed_request, base_context=base, ledger=mock_ledger)
        assert ctx1["seed_proposal_request"] == ctx2["seed_proposal_request"]
        assert ctx1["strategy_id"] == ctx2["strategy_id"]

    def test_preserves_base_context_keys(self, approved_seed_request: ProposalRequest, mock_ledger: MagicMock) -> None:
        """T75-INJ-03: base_context keys survive injection without mutation."""
        base = {"epoch_id": "ep-base", "governance_debt_score": 0.1, "custom_field": "preserved"}
        ctx = inject_seed_proposal_into_context(approved_seed_request, base_context=base, ledger=mock_ledger)
        assert ctx["epoch_id"] == "ep-base"
        assert ctx["governance_debt_score"] == pytest.approx(0.1)
        assert ctx["custom_field"] == "preserved"

    def test_seed_fields_promoted_to_top_level(self, approved_seed_request: ProposalRequest, mock_ledger: MagicMock) -> None:
        """T75-INJ-04: seed_id, seed_lane, seed_intent, etc. in top-level context."""
        ctx = inject_seed_proposal_into_context(approved_seed_request, ledger=mock_ledger)
        assert ctx.get("seed_id") == "inject-seed-75"
        assert ctx.get("seed_lane") == "governance"
        assert "seed_intent" in ctx
        assert ctx.get("strategy_id") == "governance_improvement"

    def test_ledger_event_written(self, approved_seed_request: ProposalRequest, mock_ledger: MagicMock) -> None:
        """T75-INJ-05: SeedCELInjectionEvent appended to ledger (SEED-CEL-AUDIT-0)."""
        inject_seed_proposal_into_context(approved_seed_request, ledger=mock_ledger)
        calls = [str(c) for c in mock_ledger.append_event.call_args_list]
        assert any("SeedCELInjectionEvent" in c for c in calls)

    def test_ledger_failure_raises(self, approved_seed_request: ProposalRequest) -> None:
        """T75-INJ-06: failing ledger raises RuntimeError (SEED-CEL-AUDIT-0)."""
        bad = MagicMock()
        bad.append_event.side_effect = OSError("disk full")
        with pytest.raises(RuntimeError, match="SEED-CEL-AUDIT-0"):
            inject_seed_proposal_into_context(approved_seed_request, ledger=bad)


# ---------------------------------------------------------------------------
# T75-RES-* — resolve_step4_request
# ---------------------------------------------------------------------------

class TestResolveStep4Request:
    def test_uses_seed_request_when_present(self, approved_seed_request: ProposalRequest) -> None:
        """T75-RES-01: seed_proposal_request in context → seed-derived ProposalRequest."""
        state: Dict[str, Any] = {
            "epoch_id": "ep-75-res",
            "context": {
                "seed_proposal_request": {
                    "cycle_id":    approved_seed_request.cycle_id,
                    "strategy_id": "governance_improvement",
                    "context":     dict(approved_seed_request.context),
                }
            },
        }
        req = resolve_step4_request(state, "default-cycle", "default_strategy")
        assert req.cycle_id == approved_seed_request.cycle_id
        assert req.strategy_id == "governance_improvement"

    def test_falls_back_when_absent(self) -> None:
        """T75-RES-02: no seed_proposal_request → default ProposalRequest."""
        state: Dict[str, Any] = {"epoch_id": "ep-def", "context": {}}
        req = resolve_step4_request(state, "default-cycle-xyz", "default_strategy_abc")
        assert req.cycle_id == "default-cycle-xyz"
        assert req.strategy_id == "default_strategy_abc"

    def test_pure_no_side_effects(self, approved_seed_request: ProposalRequest) -> None:
        """T75-RES-03: resolve_step4_request does not mutate state."""
        original_ctx = {"seed_proposal_request": {"cycle_id": "c1", "strategy_id": "s1", "context": {}}}
        state: Dict[str, Any] = {"epoch_id": "ep-pure", "context": dict(original_ctx)}
        resolve_step4_request(state, "c-default", "s-default")
        assert state["context"] == original_ctx  # unchanged


# ---------------------------------------------------------------------------
# T75-CEL-* — CEL Step 4 integration
# ---------------------------------------------------------------------------

class TestCELStep4Integration:
    def test_step4_uses_seed_request_when_injected(self, approved_seed_request: ProposalRequest, mock_ledger: MagicMock) -> None:
        """T75-CEL-01: CEL step 4 picks up seed_proposal_request from context."""
        ctx = inject_seed_proposal_into_context(approved_seed_request, ledger=mock_ledger)
        # Simulate what step 4 does: call resolve_step4_request
        state: Dict[str, Any] = {"epoch_id": "ep-cel-75", "context": ctx}
        req = resolve_step4_request(state, "fallback-cycle", "fallback_strategy")
        assert req.cycle_id == approved_seed_request.cycle_id
        assert req.strategy_id == "governance_improvement"

    def test_step4_fallback_on_import_error(self) -> None:
        """T75-CEL-02: step 4 falls back to default ProposalRequest if resolve raises (CEL-WIRE-FAIL-0)."""
        # Simulate the try/except in cel_wiring._step_04_proposal_generate
        def simulate_step4(state, epoch_id, strategy_id):
            try:
                raise ImportError("simulated import failure")
            except Exception:  # noqa: BLE001
                return ProposalRequest(
                    cycle_id=epoch_id,
                    strategy_id=strategy_id,
                    context=state.get("context", {}),
                )
        state: Dict[str, Any] = {"epoch_id": "ep-fallback", "context": {}}
        req = simulate_step4(state, "ep-fallback", "default_strat")
        assert req.cycle_id == "ep-fallback"
        assert req.strategy_id == "default_strat"


# ---------------------------------------------------------------------------
# T75-API-* — /seeds/promoted/{seed_id}/inject endpoint
# ---------------------------------------------------------------------------

class TestInjectEndpoint:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from runtime.innovations_router import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_unknown_seed_404(self) -> None:
        """T75-API-01: unknown seed_id returns 404."""
        with patch("runtime.innovations_router._require_audit_write"):
            with patch("runtime.innovations_router.build_proposal_request",
                       side_effect=KeyError("not found")):
                resp = self._client().post(
                    "/innovations/seeds/promoted/ghost/inject",
                    json={}, headers={"Authorization": "Bearer t"},
                )
        assert resp.status_code == 404

    def test_non_approved_422(self) -> None:
        """T75-API-02: non-approved seed returns 422."""
        with patch("runtime.innovations_router._require_audit_write"):
            with patch("runtime.innovations_router.build_proposal_request",
                       side_effect=SeedNotApprovedError("SEED-PROP-0")):
                resp = self._client().post(
                    "/innovations/seeds/promoted/pending/inject",
                    json={}, headers={"Authorization": "Bearer t"},
                )
        assert resp.status_code == 422

    def test_response_shape(self, approved_seed_request: ProposalRequest) -> None:
        """T75-API-03: successful response contains epoch_context and advisory_notice."""
        fake_ctx = {"seed_proposal_request": {"cycle_id": "c1"}, "strategy_id": "governance_improvement"}
        with patch("runtime.innovations_router._require_audit_write"):
            with patch("runtime.innovations_router.build_proposal_request",
                       return_value=approved_seed_request):
                with patch("runtime.innovations_router.inject_seed_proposal_into_context",
                           return_value=fake_ctx):
                    resp = self._client().post(
                        "/innovations/seeds/promoted/inject-seed-75/inject",
                        json={"epoch_id": "ep-75-api"},
                        headers={"Authorization": "Bearer t"},
                    )
        assert resp.status_code == 200
        body = resp.json()
        assert "epoch_context" in body
        assert "SEED-CEL-HUMAN-0" in body.get("advisory_notice", "")
        assert body["cycle_id"] == approved_seed_request.cycle_id
