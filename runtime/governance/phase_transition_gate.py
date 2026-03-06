# SPDX-License-Identifier: Apache-2.0
"""
PhaseTransitionGate — governed autonomy level advancement for ADAAD.

Purpose:
    Enforces that no autonomy level increase occurs without satisfying a
    multi-criteria stability gate. Prevents phase skipping, premature
    autonomy escalation, and undocumented transitions.

Architecture:
    Phase numbering maps directly to autonomy levels:
        Phase 0 → L0 (Manual)
        Phase 1 → L1 (Supervised)
        Phase 2 → L2 (Constrained)
        Phase 3 → L3 (Adaptive)
        Phase 4 → L4 (Governed Autonomous)

    Each transition is governed by a GateCriteria object that specifies:
        - min_approved_mutations: minimum lineage-verified approved mutations
        - min_mutation_pass_rate: fraction of mutations that must pass tests
        - lineage_completeness: fraction of mutations with full lineage chains
        - audit_chain_intact: whether the SHA-256 audit chain must be intact
        - min_consecutive_clean_epochs: consecutive epochs with no failures

    A PhaseTransitionRecord is written to the audit ledger for every
    attempted and successful transition.

Governance invariants:
    - Phase transitions can only advance by one level at a time (no skipping).
    - Transitions require operator_id — a human must explicitly trigger them.
    - All criteria are evaluated deterministically from measurable inputs.
    - A failed gate produces a detailed GateResult with per-criterion outcomes.
    - The gate is fail-closed: any missing data defaults to the failing state.
    - Rollback is always available: demote_phase() is an operator-only action.

Android/Pydroid3 compatibility:
    - Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.timeutils import now_iso

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STATE_PATH = Path("data/phase_transition_state.json")
DEFAULT_AUDIT_PATH = Path("data/phase_transition_audit.jsonl")
MAX_PHASE = 4


# ---------------------------------------------------------------------------
# Autonomy level enum
# ---------------------------------------------------------------------------

class AutonomyLevel(IntEnum):
    L0_MANUAL        = 0
    L1_SUPERVISED    = 1
    L2_CONSTRAINED   = 2
    L3_ADAPTIVE      = 3
    L4_GOVERNED_AUTO = 4

    def label(self) -> str:
        labels = {
            0: "Manual",
            1: "Supervised",
            2: "Constrained",
            3: "Adaptive",
            4: "Governed Autonomous",
        }
        return labels[self.value]


# ---------------------------------------------------------------------------
# Gate criteria per phase transition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateCriteria:
    """
    Multi-criteria gate for a specific phase transition.
    All thresholds must be satisfied simultaneously.
    """
    target_phase: int
    min_approved_mutations: int         # Min human-approved mutations in lineage
    min_mutation_pass_rate: float       # Fraction of mutations passing all tests
    min_lineage_completeness: float     # Fraction of mutations with full lineage
    audit_chain_intact: bool            # Whether SHA-256 audit chain must pass
    min_consecutive_clean_epochs: int   # Consecutive epochs with zero failures
    description: str = ""              # Human-readable description of this gate


# Canonical gate criteria — each transition has deterministic requirements
PHASE_GATE_CRITERIA: Dict[int, GateCriteria] = {
    1: GateCriteria(
        target_phase=1,
        min_approved_mutations=1,
        min_mutation_pass_rate=0.50,
        min_lineage_completeness=0.50,
        audit_chain_intact=True,
        min_consecutive_clean_epochs=1,
        description="Phase 0→1: First governed loop with human approval gate active",
    ),
    2: GateCriteria(
        target_phase=2,
        min_approved_mutations=5,
        min_mutation_pass_rate=0.65,
        min_lineage_completeness=0.70,
        audit_chain_intact=True,
        min_consecutive_clean_epochs=3,
        description="Phase 1→2: Governed Explore/Exploit loop with full CI/CD integration",
    ),
    3: GateCriteria(
        target_phase=3,
        min_approved_mutations=15,
        min_mutation_pass_rate=0.87,
        min_lineage_completeness=0.95,
        audit_chain_intact=True,
        min_consecutive_clean_epochs=5,
        description="Phase 2→3: Adaptive scoring engine active, G3+ lineage depth",
    ),
    4: GateCriteria(
        target_phase=4,
        min_approved_mutations=30,
        min_mutation_pass_rate=0.87,
        min_lineage_completeness=1.00,
        audit_chain_intact=True,
        min_consecutive_clean_epochs=10,
        description="Phase 3→4: Compound evolution, G7+ lineage, per-generation review",
    ),
}


# ---------------------------------------------------------------------------
# Gate evaluation data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CriterionResult:
    """Result for a single gate criterion."""
    name: str
    passed: bool
    actual: Any
    required: Any
    detail: str


@dataclass(frozen=True)
class GateResult:
    """
    Full result of a phase transition gate evaluation.
    gate_passed is True only when ALL criteria pass.
    """
    target_phase: int
    gate_passed: bool
    criteria_results: List[CriterionResult]
    evaluated_at: str
    operator_id: str
    gate_digest: str

    def failed_criteria(self) -> List[CriterionResult]:
        return [c for c in self.criteria_results if not c.passed]

    def to_payload(self) -> Dict[str, Any]:
        d = asdict(self)
        d["failed_criteria"] = [asdict(c) for c in self.failed_criteria()]
        return d


@dataclass(frozen=True)
class PhaseTransitionRecord:
    """Immutable audit record of a phase transition attempt."""
    from_phase: int
    to_phase: int
    gate_passed: bool
    operator_id: str
    timestamp: str
    gate_digest: str
    notes: str


@dataclass
class PhaseState:
    """Mutable phase state — persisted across sessions."""
    current_phase: int = 0
    transition_history: List[Dict[str, Any]] = field(default_factory=list)
    consecutive_clean_epochs: int = 0

    def autonomy_level(self) -> AutonomyLevel:
        return AutonomyLevel(min(self.current_phase, MAX_PHASE))


# ---------------------------------------------------------------------------
# EvidenceBundle — caller-provided metric inputs for gate evaluation
# ---------------------------------------------------------------------------

@dataclass
class TransitionEvidence:
    """
    Caller-provided evidence used to evaluate gate criteria.
    All fields must be measured from live system state before calling
    evaluate_gate() or attempt_transition().

    Fields:
        approved_mutation_count:     Total human-approved mutations in lineage.
        mutation_pass_rate:          Fraction of mutations passing all tests [0,1].
        lineage_completeness:        Fraction of mutations with full lineage [0,1].
        audit_chain_intact:          Whether SHA-256 audit chain passes integrity check.
        consecutive_clean_epochs:    Epochs with zero governance failures in sequence.
        additional_context:          Optional dict of supplementary metrics for audit.
    """
    approved_mutation_count: int
    mutation_pass_rate: float
    lineage_completeness: float
    audit_chain_intact: bool
    consecutive_clean_epochs: int
    additional_context: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# PhaseTransitionGate
# ---------------------------------------------------------------------------

class PhaseTransitionGate:
    """
    Governed phase transition controller for ADAAD autonomy level advancement.

    Usage:
        gate = PhaseTransitionGate()

        # Evaluate readiness without committing
        result = gate.evaluate_gate(
            target_phase=2,
            evidence=TransitionEvidence(
                approved_mutation_count=8,
                mutation_pass_rate=0.72,
                lineage_completeness=0.88,
                audit_chain_intact=True,
                consecutive_clean_epochs=4,
            ),
            operator_id="dreezy66",
        )
        print(result.gate_passed)          # True/False
        print(result.failed_criteria())    # [] if all pass

        # Attempt the transition (commits if gate passes)
        success, result = gate.attempt_transition(
            target_phase=2,
            evidence=evidence,
            operator_id="dreezy66",
            notes="Phase 2 readiness confirmed after 8 approved mutations",
        )

        # Emergency rollback (operator only)
        gate.demote_phase(to_phase=1, operator_id="dreezy66", reason="instability")

    Args:
        state_path: Path for persistent phase state JSON.
        audit_path: Path for immutable transition audit JSONL.
        audit_writer: Optional callable(event_type, payload) for external ledger.
    """

    def __init__(
        self,
        state_path: Path = DEFAULT_STATE_PATH,
        audit_path: Path = DEFAULT_AUDIT_PATH,
        audit_writer: Optional[Any] = None,
    ) -> None:
        self._state_path = state_path
        self._audit_path = audit_path
        self._audit = audit_writer
        self._state = self._load_state()
        self._ensure_paths()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_phase(self) -> int:
        return self._state.current_phase

    @property
    def autonomy_level(self) -> AutonomyLevel:
        return self._state.autonomy_level()

    @property
    def consecutive_clean_epochs(self) -> int:
        return self._state.consecutive_clean_epochs

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def evaluate_gate(
        self,
        target_phase: int,
        evidence: TransitionEvidence,
        operator_id: str,
    ) -> GateResult:
        """
        Evaluate whether the gate criteria for target_phase are satisfied.
        Does NOT commit a transition — read-only evaluation.

        Args:
            target_phase:  The phase to evaluate readiness for.
            evidence:      Caller-provided measurement bundle.
            operator_id:   Human operator requesting the evaluation.

        Returns:
            GateResult with per-criterion outcomes and overall gate_passed flag.

        Raises:
            ValueError: If target_phase is invalid or would skip a phase.
        """
        self._validate_target_phase(target_phase)
        criteria = PHASE_GATE_CRITERIA[target_phase]
        results = self._evaluate_criteria(criteria, evidence)
        gate_passed = all(r.passed for r in results)
        evaluated_at = now_iso()

        digest = self._compute_gate_digest(
            target_phase=target_phase,
            gate_passed=gate_passed,
            operator_id=operator_id,
            evaluated_at=evaluated_at,
        )

        return GateResult(
            target_phase=target_phase,
            gate_passed=gate_passed,
            criteria_results=results,
            evaluated_at=evaluated_at,
            operator_id=operator_id,
            gate_digest=digest,
        )

    def attempt_transition(
        self,
        target_phase: int,
        evidence: TransitionEvidence,
        operator_id: str,
        notes: str = "",
    ) -> tuple[bool, GateResult]:
        """
        Attempt a phase transition. If gate passes, commits the transition.
        Always writes an audit record regardless of outcome.

        Args:
            target_phase:  Target phase to advance to.
            evidence:      Caller-provided measurement bundle.
            operator_id:   Human operator authorising the attempt.
            notes:         Human-readable notes for the audit record.

        Returns:
            (success: bool, gate_result: GateResult)
        """
        result = self.evaluate_gate(target_phase, evidence, operator_id)

        record = PhaseTransitionRecord(
            from_phase=self._state.current_phase,
            to_phase=target_phase,
            gate_passed=result.gate_passed,
            operator_id=operator_id,
            timestamp=result.evaluated_at,
            gate_digest=result.gate_digest,
            notes=notes,
        )

        self._write_audit("phase_transition_attempt", {
            **asdict(record),
            "criteria_results": [asdict(c) for c in result.criteria_results],
            "evidence": asdict(evidence) if evidence.additional_context is None
                        else {**asdict(evidence)},
        })

        if result.gate_passed:
            self._state.current_phase = target_phase
            self._state.transition_history.append(asdict(record))
            self._save_state()

            if self._audit is not None:
                try:
                    self._audit("phase_transition_committed", {
                        "from_phase": record.from_phase,
                        "to_phase": target_phase,
                        "autonomy_level": AutonomyLevel(target_phase).label(),
                        "operator_id": operator_id,
                    })
                except Exception:  # noqa: BLE001
                    pass

        return result.gate_passed, result

    def record_epoch_outcome(self, clean: bool) -> None:
        """
        Update the consecutive clean epoch counter.
        Call after every epoch completes.

        Args:
            clean: True if the epoch had zero governance failures.
        """
        if clean:
            self._state.consecutive_clean_epochs += 1
        else:
            self._state.consecutive_clean_epochs = 0
        self._save_state()

    def demote_phase(
        self,
        to_phase: int,
        operator_id: str,
        reason: str,
    ) -> None:
        """
        Emergency demotion to a lower phase (operator-only, always available).
        Always succeeds — no gate criteria required for demotion.
        Writes a demotion audit record.

        Args:
            to_phase:    Target phase to revert to (must be ≤ current_phase).
            operator_id: Human operator performing the demotion.
            reason:      Human-readable reason for the demotion.
        """
        if to_phase > self._state.current_phase:
            raise ValueError(
                f"demote_target_exceeds_current:{to_phase} > {self._state.current_phase}"
            )
        if to_phase < 0:
            raise ValueError(f"invalid_demote_target:{to_phase}")

        from_phase = self._state.current_phase
        self._state.current_phase = to_phase
        self._state.consecutive_clean_epochs = 0
        self._save_state()

        self._write_audit("phase_demotion", {
            "from_phase": from_phase,
            "to_phase": to_phase,
            "operator_id": operator_id,
            "reason": reason,
            "timestamp": now_iso(),
        })

        if self._audit is not None:
            try:
                self._audit("phase_demoted", {
                    "from_phase": from_phase,
                    "to_phase": to_phase,
                    "operator_id": operator_id,
                })
            except Exception:  # noqa: BLE001
                pass

    def get_criteria(self, target_phase: int) -> GateCriteria:
        """Return the gate criteria for a target phase (read-only)."""
        if target_phase not in PHASE_GATE_CRITERIA:
            raise ValueError(f"no_criteria_for_phase:{target_phase}")
        return PHASE_GATE_CRITERIA[target_phase]

    def health_snapshot(self) -> Dict[str, Any]:
        """Return a governance-ready health snapshot."""
        level = self._state.autonomy_level()
        return {
            "current_phase": self._state.current_phase,
            "autonomy_level": level.value,
            "autonomy_level_label": level.label(),
            "consecutive_clean_epochs": self._state.consecutive_clean_epochs,
            "transition_count": len(self._state.transition_history),
            "last_transition": (
                self._state.transition_history[-1]
                if self._state.transition_history else None
            ),
        }

    def transition_history(self) -> List[Dict[str, Any]]:
        """Return the full transition history."""
        return list(self._state.transition_history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_target_phase(self, target_phase: int) -> None:
        if target_phase < 1 or target_phase > MAX_PHASE:
            raise ValueError(f"invalid_target_phase:{target_phase}")
        if target_phase != self._state.current_phase + 1:
            raise ValueError(
                f"phase_skip_not_allowed: current={self._state.current_phase} "
                f"target={target_phase} (must advance by exactly 1)"
            )
        if target_phase not in PHASE_GATE_CRITERIA:
            raise ValueError(f"no_criteria_defined_for_phase:{target_phase}")

    def _evaluate_criteria(
        self,
        criteria: GateCriteria,
        evidence: TransitionEvidence,
    ) -> List[CriterionResult]:
        results: List[CriterionResult] = []

        # 1. Approved mutations
        results.append(CriterionResult(
            name="min_approved_mutations",
            passed=evidence.approved_mutation_count >= criteria.min_approved_mutations,
            actual=evidence.approved_mutation_count,
            required=criteria.min_approved_mutations,
            detail=(
                f"approved={evidence.approved_mutation_count} "
                f"required={criteria.min_approved_mutations}"
            ),
        ))

        # 2. Mutation pass rate
        results.append(CriterionResult(
            name="min_mutation_pass_rate",
            passed=round(evidence.mutation_pass_rate, 4) >= criteria.min_mutation_pass_rate,
            actual=round(evidence.mutation_pass_rate, 4),
            required=criteria.min_mutation_pass_rate,
            detail=(
                f"pass_rate={evidence.mutation_pass_rate:.4f} "
                f"required={criteria.min_mutation_pass_rate}"
            ),
        ))

        # 3. Lineage completeness
        results.append(CriterionResult(
            name="min_lineage_completeness",
            passed=round(evidence.lineage_completeness, 4) >= criteria.min_lineage_completeness,
            actual=round(evidence.lineage_completeness, 4),
            required=criteria.min_lineage_completeness,
            detail=(
                f"completeness={evidence.lineage_completeness:.4f} "
                f"required={criteria.min_lineage_completeness}"
            ),
        ))

        # 4. Audit chain integrity
        results.append(CriterionResult(
            name="audit_chain_intact",
            passed=evidence.audit_chain_intact == criteria.audit_chain_intact,
            actual=evidence.audit_chain_intact,
            required=criteria.audit_chain_intact,
            detail=f"intact={evidence.audit_chain_intact}",
        ))

        # 5. Consecutive clean epochs
        actual_clean = max(
            evidence.consecutive_clean_epochs,
            self._state.consecutive_clean_epochs,
        )
        results.append(CriterionResult(
            name="min_consecutive_clean_epochs",
            passed=actual_clean >= criteria.min_consecutive_clean_epochs,
            actual=actual_clean,
            required=criteria.min_consecutive_clean_epochs,
            detail=(
                f"clean_epochs={actual_clean} "
                f"required={criteria.min_consecutive_clean_epochs}"
            ),
        ))

        return results

    def _compute_gate_digest(
        self,
        target_phase: int,
        gate_passed: bool,
        operator_id: str,
        evaluated_at: str,
    ) -> str:
        canonical = json.dumps(
            {
                "current_phase": self._state.current_phase,
                "target_phase": target_phase,
                "gate_passed": gate_passed,
                "operator_id": operator_id,
                "evaluated_at": evaluated_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _load_state(self) -> PhaseState:
        if not self._state_path.exists():
            return PhaseState()
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            state = PhaseState()
            state.current_phase = int(raw.get("current_phase", 0))
            state.consecutive_clean_epochs = int(raw.get("consecutive_clean_epochs", 0))
            state.transition_history = list(raw.get("transition_history", []))
            return state
        except (json.JSONDecodeError, KeyError, TypeError):
            return PhaseState()

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(
                {
                    "current_phase": self._state.current_phase,
                    "consecutive_clean_epochs": self._state.consecutive_clean_epochs,
                    "transition_history": self._state.transition_history,
                },
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_audit(self, event_type: str, payload: Dict[str, Any]) -> None:
        entry = {
            "event_type": event_type,
            "timestamp": now_iso(),
            "payload": payload,
        }
        with self._audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    def _ensure_paths(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_path.touch(exist_ok=True)


__all__ = [
    "AutonomyLevel",
    "GateCriteria",
    "GateResult",
    "CriterionResult",
    "TransitionEvidence",
    "PhaseTransitionRecord",
    "PhaseTransitionGate",
    "PHASE_GATE_CRITERIA",
    "MAX_PHASE",
]
