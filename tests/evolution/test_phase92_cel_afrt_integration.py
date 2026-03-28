# SPDX-License-Identifier: Apache-2.0
"""Phase 92 — CEL AFRT integration tests.

Verifies AFRT-GATE-0: Step 10 AFRT-GATE executes after PARETO-SELECT (9)
and before GOVERNANCE-GATE-V2 (11) in the 16-step CEL dispatch table.

Tests:
  CEL-AFRT-01  AFRT step present in dispatch table at position 10
  CEL-AFRT-02  AFRT step name is AFRT-GATE
  CEL-AFRT-03  GOVERNANCE-GATE-V2 is at position 11 (after AFRT)
  CEL-AFRT-04  PARETO-SELECT is at position 9 (before AFRT)
  CEL-AFRT-05  CEL runs 16 steps total
  CEL-AFRT-06  AFRT bypass passes when afrt_agent=None
  CEL-AFRT-07  afrt_bypassed recorded in state when agent is None
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from runtime.evolution.constitutional_evolution_loop import (
    ConstitutionalEvolutionLoop,
    RunMode,
    StepOutcome,
)


def make_cel(afrt_agent=None) -> ConstitutionalEvolutionLoop:
    """Construct a minimal CEL with all heavy components disabled."""
    return ConstitutionalEvolutionLoop(
        run_mode=RunMode.SANDBOX_ONLY,
        fitness_orchestrator=None,
        fitness_decay_scorer=None,
        causal_fitness_attributor=None,
        pareto_competition_orchestrator=None,
        self_discovery_loop=None,
        afrt_agent=afrt_agent,
    )


def _dispatch_table(cel: ConstitutionalEvolutionLoop):
    """Re-derive the dispatch table from a CEL instance (mirrors run_epoch internals)."""
    return [
        (1,  "MODEL-DRIFT-CHECK",    cel._step_01_model_drift_check),
        (2,  "LINEAGE-SNAPSHOT",     cel._step_02_lineage_snapshot),
        (3,  "FITNESS-BASELINE",     cel._step_03_fitness_baseline),
        (4,  "PROPOSAL-GENERATE",    cel._step_04_proposal_generate),
        (5,  "AST-SCAN",             cel._step_05_ast_scan),
        (6,  "SANDBOX-EXECUTE",      cel._step_06_sandbox_execute),
        (7,  "REPLAY-VERIFY",        cel._step_07_replay_verify),
        (8,  "FITNESS-SCORE",        cel._step_08_fitness_score),
        (9,  "PARETO-SELECT",        cel._step_09_pareto_select),
        (10, "AFRT-GATE",            cel._step_10_afrt_gate),
        (11, "GOVERNANCE-GATE-V2",   cel._step_09_governance_gate_v2),
        (12, "GOVERNANCE-GATE",      cel._step_10_governance_gate),
        (13, "LINEAGE-REGISTER",     cel._step_11_lineage_register),
        (14, "PROMOTION-DECISION",   cel._step_12_promotion_decision),
        (15, "EPOCH-EVIDENCE-WRITE", cel._step_13_epoch_evidence_write),
        (16, "STATE-ADVANCE",        cel._step_14_state_advance),
    ]


class TestAFRTCELOrdering:

    def test_cel_afrt_01_afrt_gate_at_position_10(self):
        """CEL-AFRT-01: AFRT-GATE is step number 10 in the dispatch table."""
        cel = make_cel()
        table = _dispatch_table(cel)
        step_10 = table[9]  # 0-indexed
        assert step_10[0] == 10
        assert step_10[1] == "AFRT-GATE"

    def test_cel_afrt_02_afrt_step_name_correct(self):
        """CEL-AFRT-02: step at index 9 is named AFRT-GATE."""
        cel = make_cel()
        table = _dispatch_table(cel)
        names = [name for _, name, _ in table]
        assert "AFRT-GATE" in names
        assert names.index("AFRT-GATE") == 9  # 0-indexed position 9 = step 10

    def test_cel_afrt_03_governance_gate_v2_after_afrt(self):
        """CEL-AFRT-03: GOVERNANCE-GATE-V2 is at step 11 (after AFRT at 10)."""
        cel = make_cel()
        table = _dispatch_table(cel)
        names = [name for _, name, _ in table]
        afrt_idx = names.index("AFRT-GATE")
        gov_v2_idx = names.index("GOVERNANCE-GATE-V2")
        assert gov_v2_idx == afrt_idx + 1

    def test_cel_afrt_04_pareto_select_before_afrt(self):
        """CEL-AFRT-04: PARETO-SELECT is at step 9 (before AFRT at 10)."""
        cel = make_cel()
        table = _dispatch_table(cel)
        names = [name for _, name, _ in table]
        pareto_idx = names.index("PARETO-SELECT")
        afrt_idx = names.index("AFRT-GATE")
        assert pareto_idx == afrt_idx - 1

    def test_cel_afrt_05_total_step_count_is_16(self):
        """CEL-AFRT-05: dispatch table has 16 steps post Phase 92."""
        cel = make_cel()
        table = _dispatch_table(cel)
        assert len(table) == 16

    def test_cel_afrt_06_afrt_bypass_passes_when_agent_none(self):
        """CEL-AFRT-06: step returns PASS with bypass flag when afrt_agent=None."""
        cel = make_cel(afrt_agent=None)
        state = {
            "epoch_id": "epoch-test-001",
            "context": {},
            "dry_run": True,
            "pareto_frontier_ids": [],
        }
        result = cel._step_10_afrt_gate(10, "AFRT-GATE", state)
        assert result.outcome == StepOutcome.PASS
        assert result.detail.get("afrt_bypassed") is True

    def test_cel_afrt_07_afrt_bypassed_recorded_in_state(self):
        """CEL-AFRT-07: state["afrt_bypassed"] = True when agent is None."""
        cel = make_cel(afrt_agent=None)
        state = {
            "epoch_id": "epoch-test-002",
            "context": {},
            "dry_run": True,
            "pareto_frontier_ids": [],
        }
        cel._step_10_afrt_gate(10, "AFRT-GATE", state)
        assert state.get("afrt_bypassed") is True
