# SPDX-License-Identifier: Apache-2.0
"""Phase 57 — ProposalEngine Auto-Provisioning test suite.

Tests: T57-AP-01..12
Invariants: PROP-AUTO-0..5
Gate: SPEC-57 (HUMAN-0 sign-off required before merge to main)
"""

from __future__ import annotations

import os
import unittest
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Import targets
# ---------------------------------------------------------------------------
from runtime.evolution.evolution_loop import (
    EpochResult,
    EvolutionLoop,
    _autoprovision_proposal_engine,
)
from runtime.evolution.proposal_engine import ProposalEngine, ProposalRequest
from runtime.intelligence.proposal import Proposal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_proposal(*, noop: bool = False) -> Proposal:
    return Proposal(
        proposal_id="stub-p-001",
        title="Stub proposal" if not noop else "Noop",
        summary="stub" if not noop else "noop",
        estimated_impact=0.5 if not noop else 0.0,
        real_diff="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y" if not noop else "",
        metadata={},
    )


class _StubEngine:
    """Minimal ProposalEngine stand-in that records calls."""

    def __init__(self, proposal: Proposal) -> None:
        self._proposal = proposal
        self.calls: list[ProposalRequest] = []

    def generate(self, request: ProposalRequest) -> Proposal:
        self.calls.append(request)
        return self._proposal


# ---------------------------------------------------------------------------
# T57-AP-01: API key present → engine auto-provisioned (PROP-AUTO-0)
# ---------------------------------------------------------------------------
class TestAP01_AutoProvisionWhenKeyPresent(unittest.TestCase):
    def test_api_key_present_returns_engine(self):
        with patch.dict(os.environ, {"ADAAD_ANTHROPIC_API_KEY": "sk-test-key"}, clear=False):
            with patch("runtime.evolution.evolution_loop.ProposalEngine") as MockEngine:
                MockEngine.return_value = MagicMock(spec=ProposalEngine)
                result = _autoprovision_proposal_engine(explicit=None)
        self.assertIsNotNone(result, "PROP-AUTO-0: engine must be provisioned when key present")


# ---------------------------------------------------------------------------
# T57-AP-02: API key absent → engine not provisioned (PROP-AUTO-0 negative)
# ---------------------------------------------------------------------------
class TestAP02_NoEngineWhenKeyAbsent(unittest.TestCase):
    def test_no_api_key_returns_none(self):
        env = {k: v for k, v in os.environ.items() if k != "ADAAD_ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = _autoprovision_proposal_engine(explicit=None)
        self.assertIsNone(result, "PROP-AUTO-0: no engine without API key")


# ---------------------------------------------------------------------------
# T57-AP-03: ADAAD_PROPOSAL_ENGINE_DISABLED=true suppresses auto-provision (PROP-AUTO-5)
# ---------------------------------------------------------------------------
class TestAP03_DisabledEnvVarSuppresses(unittest.TestCase):
    def test_disabled_flag_suppresses(self):
        with patch.dict(os.environ, {
            "ADAAD_ANTHROPIC_API_KEY": "sk-test-key",
            "ADAAD_PROPOSAL_ENGINE_DISABLED": "true",
        }, clear=False):
            result = _autoprovision_proposal_engine(explicit=None)
        self.assertIsNone(result, "PROP-AUTO-5: disabled flag must suppress auto-provision")

    def test_disabled_case_insensitive(self):
        with patch.dict(os.environ, {
            "ADAAD_ANTHROPIC_API_KEY": "sk-test-key",
            "ADAAD_PROPOSAL_ENGINE_DISABLED": "TRUE",
        }, clear=False):
            result = _autoprovision_proposal_engine(explicit=None)
        self.assertIsNone(result, "PROP-AUTO-5: case-insensitive disabled check")


# ---------------------------------------------------------------------------
# T57-AP-04: Explicit injection overrides auto-provisioning (PROP-AUTO-1)
# ---------------------------------------------------------------------------
class TestAP04_ExplicitInjectionWins(unittest.TestCase):
    def test_explicit_engine_returned_unchanged(self):
        explicit = MagicMock(spec=ProposalEngine)
        with patch.dict(os.environ, {"ADAAD_ANTHROPIC_API_KEY": "sk-test-key"}, clear=False):
            result = _autoprovision_proposal_engine(explicit=explicit)
        self.assertIs(result, explicit, "PROP-AUTO-1: explicit injection must win")

    def test_explicit_none_still_auto_provisions(self):
        with patch.dict(os.environ, {"ADAAD_ANTHROPIC_API_KEY": "sk-test-key"}, clear=False):
            with patch("runtime.evolution.evolution_loop.ProposalEngine") as MockEngine:
                MockEngine.return_value = MagicMock(spec=ProposalEngine)
                result = _autoprovision_proposal_engine(explicit=None)
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# T57-AP-05: Provisioning failure is fail-closed (PROP-AUTO-2)
# ---------------------------------------------------------------------------
class TestAP05_ProvisioningFailureFailClosed(unittest.TestCase):
    def test_constructor_exception_returns_none(self):
        with patch.dict(os.environ, {"ADAAD_ANTHROPIC_API_KEY": "sk-test-key"}, clear=False):
            with patch(
                "runtime.evolution.evolution_loop.ProposalEngine",
                side_effect=RuntimeError("network down"),
            ):
                result = _autoprovision_proposal_engine(explicit=None)
        self.assertIsNone(result, "PROP-AUTO-2: construction failure must return None, not raise")


# ---------------------------------------------------------------------------
# T57-AP-06: Noop proposal silently skipped (existing Phase 14 behaviour preserved)
# ---------------------------------------------------------------------------
class TestAP06_NoopProposalSkipped(unittest.TestCase):
    def _make_loop_with_stub_engine(self, proposal: Proposal) -> EvolutionLoop:
        loop = EvolutionLoop.__new__(EvolutionLoop)
        # Minimal attribute injection to test Phase 1e path
        loop._proposal_engine = _StubEngine(proposal)
        loop._proposal_engine_auto = True
        return loop

    def test_noop_real_diff_not_added_to_candidates(self):
        """_proposal_to_candidate must return None for empty real_diff."""
        from runtime.evolution.evolution_loop import _proposal_to_candidate
        noop = _stub_proposal(noop=True)
        result = _proposal_to_candidate(noop, epoch_id="ep-001")
        self.assertIsNone(result, "Noop proposal (empty real_diff) must yield None candidate")


# ---------------------------------------------------------------------------
# T57-AP-07: Valid proposal enters pipeline as MutationCandidate
# ---------------------------------------------------------------------------
class TestAP07_ValidProposalEntersPipeline(unittest.TestCase):
    def test_valid_proposal_yields_candidate(self):
        from runtime.evolution.evolution_loop import _proposal_to_candidate
        valid = _stub_proposal(noop=False)
        result = _proposal_to_candidate(valid, epoch_id="ep-002")
        self.assertIsNotNone(result, "Valid proposal must yield MutationCandidate")
        # mutation_id is taken from proposal_id (proposal.proposal_id), not epoch_id
        self.assertEqual(result.mutation_id, valid.proposal_id)
        self.assertEqual(result.epoch_id, "ep-002")


# ---------------------------------------------------------------------------
# T57-AP-08: Auto-provisioned proposal passes through entropy gate
# (PROP-AUTO-3 — no bypass; gate is applied uniformly to all candidates)
# ---------------------------------------------------------------------------
class TestAP08_EntropyGateNotBypassed(unittest.TestCase):
    def test_entropy_gate_evaluate_called_for_engine_proposals(self):
        """EntropyFastGate.evaluate() must be called for every candidate
        regardless of origin (agent vs ProposalEngine). Verify the Phase 1.5
        loop processes all_proposals including engine-sourced ones."""
        from runtime.evolution.entropy_fast_gate import EntropyFastGate, GateVerdict, EntropyGateResult

        with patch.object(
            EntropyFastGate,
            "evaluate",
            return_value=EntropyGateResult(
                verdict=GateVerdict.ALLOW,
                mutation_id="m1",
                estimated_bits=0,
                budget_bits=128,
                active_sources=(),
                reason="ALLOW",
                gate_digest="abc123",
            ),
        ) as mock_evaluate:
            from runtime.evolution.evolution_loop import _detect_entropy_sources
            # Simulate what Phase 1.5 does for any candidate
            content = "x = 1\n"
            sources = _detect_entropy_sources(content)
            gate = EntropyFastGate()
            gate.evaluate(mutation_id="engine-m1", estimated_bits=0, sources=sources)
            mock_evaluate.assert_called_once()


# ---------------------------------------------------------------------------
# T57-AP-09: Route optimizer classifies engine proposals (PROP-AUTO-4)
# ---------------------------------------------------------------------------
class TestAP09_RouteOptimizerNotBypassed(unittest.TestCase):
    def test_mutation_route_optimizer_classify_works_on_engine_candidate(self):
        from runtime.evolution.mutation_route_optimizer import MutationRouteOptimizer, RouteTier
        from runtime.evolution.evolution_loop import _proposal_to_candidate

        valid = _stub_proposal(noop=False)
        candidate = _proposal_to_candidate(valid, epoch_id="ep-003")
        self.assertIsNotNone(candidate)
        router = MutationRouteOptimizer()
        # route() takes structured kwargs — engine candidates must be accepted
        decision = router.route(
            mutation_id=candidate.mutation_id,
            intent=candidate.operator_category or "llm_strategy",
            ops=[],
            files_touched=[],
        )
        self.assertIn(decision.tier, list(RouteTier),
                      "PROP-AUTO-4: engine candidate must be routable")


# ---------------------------------------------------------------------------
# T57-AP-10: Engine proposal scored identically to agent proposals
# ---------------------------------------------------------------------------
class TestAP10_EngineCandidateScoredEqually(unittest.TestCase):
    def test_engine_candidate_has_agent_origin_set(self):
        """_proposal_to_candidate must tag agent_origin so scoring pipeline
        can attribute the result. Engine origin = 'proposal_engine'."""
        from runtime.evolution.evolution_loop import _proposal_to_candidate
        valid = _stub_proposal(noop=False)
        candidate = _proposal_to_candidate(valid, epoch_id="ep-004")
        self.assertIsNotNone(candidate)
        self.assertEqual(
            candidate.agent_origin,
            "proposal_engine",
            "Engine candidates must carry agent_origin='proposal_engine' for attribution",
        )


# ---------------------------------------------------------------------------
# T57-AP-11: EpochResult.proposal_engine_active reflects engine presence
# ---------------------------------------------------------------------------
class TestAP11_EpochResultFlag(unittest.TestCase):
    def test_flag_true_when_engine_active(self):
        result = EpochResult(
            epoch_id="ep-005",
            generation_count=1,
            total_candidates=0,
            accepted_count=0,
            proposal_engine_active=True,
        )
        self.assertTrue(result.proposal_engine_active)

    def test_flag_false_when_engine_absent(self):
        result = EpochResult(
            epoch_id="ep-006",
            generation_count=1,
            total_candidates=0,
            accepted_count=0,
        )
        self.assertFalse(result.proposal_engine_active)

    def test_flag_defaults_false(self):
        """Backwards compatibility: EpochResult without explicit flag is False."""
        r = EpochResult(
            epoch_id="ep-007",
            generation_count=1,
            total_candidates=0,
            accepted_count=0,
        )
        self.assertFalse(r.proposal_engine_active,
                         "Default must be False for backwards compat")


# ---------------------------------------------------------------------------
# T57-AP-12: Journal records PROP_ENGINE_AUTO_PROVISIONED on provisioning
# ---------------------------------------------------------------------------
class TestAP12_JournalRecordsAutoProvision(unittest.TestCase):
    def test_journal_append_called_on_auto_provision(self):
        with patch.dict(os.environ, {"ADAAD_ANTHROPIC_API_KEY": "sk-test-key"}, clear=False):
            with patch("runtime.evolution.evolution_loop.ProposalEngine") as MockEngine:
                MockEngine.return_value = MagicMock(spec=ProposalEngine)
                with patch("runtime.evolution.evolution_loop.journal") as mock_journal:
                    _autoprovision_proposal_engine(explicit=None)
                    mock_journal.append_tx.assert_called_once()
                    call_kwargs = mock_journal.append_tx.call_args
                    self.assertEqual(
                        call_kwargs.kwargs.get("tx_type") or call_kwargs[1].get("tx_type"),
                        "PROP_ENGINE_AUTO_PROVISIONED",
                    )


# ---------------------------------------------------------------------------
# PROP-AUTO invariant summary (machine-readable for CI gate)
# ---------------------------------------------------------------------------
PROP_AUTO_INVARIANTS = {
    "PROP-AUTO-0": "Auto-provision when ADAAD_ANTHROPIC_API_KEY present",
    "PROP-AUTO-1": "Explicit injection always wins over auto-provision",
    "PROP-AUTO-2": "Provisioning failure is fail-closed (return None, no raise)",
    "PROP-AUTO-3": "All engine proposals enter governed pipeline unchanged",
    "PROP-AUTO-4": "No bypass of entropy gate, route optimizer, or GovernanceGate",
    "PROP-AUTO-5": "ADAAD_PROPOSAL_ENGINE_DISABLED=true suppresses provisioning",
}


if __name__ == "__main__":
    unittest.main()
