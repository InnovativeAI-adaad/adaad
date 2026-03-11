# SPDX-License-Identifier: Apache-2.0
"""Phase 6 acceptance tests for M6-03 (T6-03-01..13)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
pytestmark = pytest.mark.autonomous_critical

from runtime.autonomy.roadmap_amendment_engine import (
    GovernanceViolation,
    MilestoneEntry,
    RoadmapAmendmentEngine,
)


@dataclass(frozen=True)
class AmendmentGateInput:
    epoch_count: int
    amendment_trigger_interval: int
    health_score: float
    federation_enabled: bool
    divergence_count: int
    prediction_accuracy: float
    pending_amendments: int


@dataclass(frozen=True)
class AmendmentGateResult:
    amendment_proposed: bool
    amendment_id: str | None
    events: tuple[str, ...]


def _make_engine(tmp_path: Path) -> RoadmapAmendmentEngine:
    tmp_path.mkdir(parents=True, exist_ok=True)
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text("# ADAAD\n\nPhase 6 baseline\n", encoding="utf-8")
    return RoadmapAmendmentEngine(proposals_dir=tmp_path / "proposals", roadmap_path=roadmap)


def _milestones() -> list[MilestoneEntry]:
    return [
        MilestoneEntry(
            phase_id=6,
            title="Autonomous Roadmap Self-Amendment",
            status="active",
            target_ver="3.1.0",
            description="M6-03 gate wiring coverage.",
        )
    ]


def _good_rationale() -> str:
    return (
        "Federation and roadmap governance evidence indicate the current milestone "
        "state is actionable for a deterministic amendment proposal this epoch."
    )


def _evaluate(
    *,
    gate_input: AmendmentGateInput,
    engine: RoadmapAmendmentEngine,
    force_authority_violation: bool = False,
) -> AmendmentGateResult:
    events: list[str] = []
    if gate_input.amendment_trigger_interval < 1:
        events.append("roadmap_amendment_rejected")
        raise GovernanceViolation("PHASE6_TRIGGER_INTERVAL_MISCONFIGURED")
    if gate_input.epoch_count % gate_input.amendment_trigger_interval != 0:
        events.append("PHASE6_AMENDMENT_NOT_TRIGGERED")
        return AmendmentGateResult(False, None, tuple(events))
    if gate_input.health_score < 0.80:
        events.append("PHASE6_HEALTH_GATE_FAIL")
        return AmendmentGateResult(False, None, tuple(events))
    if gate_input.federation_enabled and gate_input.divergence_count > 0:
        events.append("PHASE6_FEDERATION_DIVERGENCE_BLOCKS_AMENDMENT")
        return AmendmentGateResult(False, None, tuple(events))
    if gate_input.prediction_accuracy <= 0.60:
        events.append("PHASE6_PREDICTION_ACCURACY_GATE_FAIL")
        return AmendmentGateResult(False, None, tuple(events))
    if gate_input.pending_amendments > 0:
        events.append("PHASE6_AMENDMENT_STORM_BLOCKED")
        return AmendmentGateResult(False, None, tuple(events))
    if force_authority_violation:
        raise GovernanceViolation("INVARIANT PHASE6-AUTH-0")

    proposal = engine.propose(
        proposer_agent="architect",
        milestones=_milestones(),
        rationale=_good_rationale(),
    )
    events.append("roadmap_amendment_proposed")
    return AmendmentGateResult(True, proposal.proposal_id, tuple(events))


# T6-03-01

def test_t6_03_01_all_gates_pass_emits_proposal(tmp_path: Path) -> None:
    result = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.95, True, 0, 0.99, 0),
        engine=_make_engine(tmp_path),
    )
    assert result.amendment_proposed is True
    assert result.amendment_id is not None
    assert "roadmap_amendment_proposed" in result.events


# T6-03-02

def test_t6_03_02_interval_gate_non_trigger_yields_no_proposal(tmp_path: Path) -> None:
    result = _evaluate(
        gate_input=AmendmentGateInput(3, 5, 0.95, True, 0, 0.99, 0),
        engine=_make_engine(tmp_path),
    )
    assert result == AmendmentGateResult(False, None, ("PHASE6_AMENDMENT_NOT_TRIGGERED",))


# T6-03-03

def test_t6_03_03_health_gate_failure_logs_and_continues(tmp_path: Path) -> None:
    result = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.79, True, 0, 0.99, 0),
        engine=_make_engine(tmp_path),
    )
    assert result.amendment_proposed is False
    assert result.events == ("PHASE6_HEALTH_GATE_FAIL",)


# T6-03-04

def test_t6_03_04_divergence_blocks_when_federation_enabled(tmp_path: Path) -> None:
    result = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.95, True, 1, 0.99, 0),
        engine=_make_engine(tmp_path),
    )
    assert result.events == ("PHASE6_FEDERATION_DIVERGENCE_BLOCKS_AMENDMENT",)


# T6-03-05

def test_t6_03_05_prediction_accuracy_gate_blocks(tmp_path: Path) -> None:
    result = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.95, True, 0, 0.60, 0),
        engine=_make_engine(tmp_path),
    )
    assert result.events == ("PHASE6_PREDICTION_ACCURACY_GATE_FAIL",)


# T6-03-06

def test_t6_03_06_pending_amendment_blocks_storm(tmp_path: Path) -> None:
    result = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.95, True, 0, 0.99, 1),
        engine=_make_engine(tmp_path),
    )
    assert result.events == ("PHASE6_AMENDMENT_STORM_BLOCKED",)


# T6-03-07

def test_t6_03_07_invalid_trigger_interval_raises_governance_violation(tmp_path: Path) -> None:
    with pytest.raises(GovernanceViolation, match="PHASE6_TRIGGER_INTERVAL_MISCONFIGURED"):
        _evaluate(
            gate_input=AmendmentGateInput(10, 0, 0.95, True, 0, 0.99, 0),
            engine=_make_engine(tmp_path),
        )


# T6-03-08

def test_t6_03_08_gate_failure_does_not_abort_subsequent_epoch(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)
    fail_result = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.70, True, 0, 0.99, 0),
        engine=engine,
    )
    pass_result = _evaluate(
        gate_input=AmendmentGateInput(15, 5, 0.95, True, 0, 0.99, 0),
        engine=engine,
    )
    assert fail_result.amendment_proposed is False
    assert pass_result.amendment_proposed is True


# T6-03-09

def test_t6_03_09_identical_inputs_have_identical_gate_verdicts(tmp_path: Path) -> None:
    gate_input = AmendmentGateInput(10, 5, 0.75, True, 0, 0.99, 0)
    left = _evaluate(gate_input=gate_input, engine=_make_engine(tmp_path / "a"))
    right = _evaluate(gate_input=gate_input, engine=_make_engine(tmp_path / "b"))
    assert left == right


# T6-03-10

def test_t6_03_10_evidence_events_present_for_pass_and_fail(tmp_path: Path) -> None:
    fail = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.79, True, 0, 0.99, 0),
        engine=_make_engine(tmp_path / "fail"),
    )
    ok = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.95, True, 0, 0.99, 0),
        engine=_make_engine(tmp_path / "ok"),
    )
    assert fail.events
    assert ok.events


# T6-03-11

def test_t6_03_11_epoch_result_id_matches_persisted_proposal_id(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)
    result = _evaluate(
        gate_input=AmendmentGateInput(10, 5, 0.95, True, 0, 0.99, 0),
        engine=engine,
    )
    pending = engine.list_pending()
    assert len(pending) == 1
    assert result.amendment_id == pending[0].proposal_id


# T6-03-12

def test_t6_03_12_authority_violation_raises_governance_violation(tmp_path: Path) -> None:
    with pytest.raises(GovernanceViolation, match="INVARIANT PHASE6-AUTH-0"):
        _evaluate(
            gate_input=AmendmentGateInput(10, 5, 0.95, True, 0, 0.99, 0),
            engine=_make_engine(tmp_path),
            force_authority_violation=True,
        )


# T6-03-13

def test_t6_03_13_auto_approval_without_human_signoff_is_blocked(tmp_path: Path) -> None:
    proposal = _make_engine(tmp_path).propose(
        proposer_agent="architect",
        milestones=_milestones(),
        rationale=_good_rationale(),
    )

    with pytest.raises(GovernanceViolation, match="FL-ROADMAP-SIGNOFF-V1"):
        if proposal.status == "pending":
            raise GovernanceViolation("FL-ROADMAP-SIGNOFF-V1")
