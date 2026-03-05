# SPDX-License-Identifier: Apache-2.0
"""Constraint Interpreter — ADAAD-8 / Policy Simulation Mode

Converts parsed ConstraintExpression objects (from dsl_grammar.py) into a
SimulationPolicy object that is structurally compatible with the GovernanceGate
evaluation interface.

Isolation invariant: SimulationPolicy.simulation is always True at construction.
The GovernanceGate boundary checks this flag before any state-affecting operation.
Caller convention is insufficient — the flag is enforced structurally.

Design:
- SimulationPolicy is a frozen dataclass; fields cannot be mutated post-construction.
- interpret_policy() accepts a list of ConstraintExpression objects and returns a
  SimulationPolicy with simulation=True always present.
- interpret_policy_block() is a convenience wrapper accepting raw DSL text.
- Conflicting constraint types raise SimulationPolicyError at construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from runtime.governance.simulation.dsl_grammar import (
    ConstraintExpression,
    ConstraintType,
    DSL_GRAMMAR_VERSION,
    SimulationDSLError,
    parse_policy_block,
)


# ---------------------------------------------------------------------------
# Policy error
# ---------------------------------------------------------------------------

class SimulationPolicyError(Exception):
    """Raised when a SimulationPolicy cannot be constructed from the given constraints."""


# ---------------------------------------------------------------------------
# SimulationPolicy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SimulationPolicy:
    """A fully interpreted, immutable simulation policy.

    This object is structurally compatible with GovernanceGate evaluation.
    The ``simulation`` field is always True — it cannot be set to False at
    construction and is checked at the GovernanceGate boundary before any
    state-affecting operation.

    Fields mirror constraint types 1:1; None means "no constraint applied."
    """

    # Isolation flag — always True; checked at GovernanceGate boundary.
    simulation: bool

    # Constraint fields (None = not constrained)
    require_approvals: Optional[Dict[str, Any]] = None       # {tier: str, count: int}
    max_risk_score: Optional[float] = None                   # [0.0, 1.0]
    max_mutations_per_epoch: Optional[int] = None            # >= 1
    max_complexity_delta: Optional[float] = None             # [0.0, 1.0]
    freeze_tiers: List[str] = field(default_factory=list)    # list of frozen tier names
    require_rules: List[Dict[str, Any]] = field(default_factory=list)  # [{rule_id, severity}]
    min_test_coverage: Optional[float] = None                # [0.0, 1.0]
    max_entropy_per_epoch: Optional[float] = None            # [0.0, 1.0]
    escalate_reviewers_on_risk: Optional[Dict[str, Any]] = None  # {threshold, count}
    require_lineage_depth: Optional[int] = None              # >= 1

    # Provenance
    constraint_count: int = 0
    grammar_version: str = DSL_GRAMMAR_VERSION
    source_expressions: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Structural invariant: simulation must always be True.
        if not self.simulation:
            raise SimulationPolicyError(
                "SimulationPolicy.simulation must be True. "
                "Live policy execution must not use SimulationPolicy objects."
            )

    def is_tier_frozen(self, tier: str) -> bool:
        """Return True if the given tier is frozen under this policy."""
        return tier in self.freeze_tiers

    def to_dict(self) -> Dict[str, Any]:
        """Return a serialisable dict representation of this policy."""
        return {
            "simulation": self.simulation,
            "constraint_count": self.constraint_count,
            "grammar_version": self.grammar_version,
            "require_approvals": self.require_approvals,
            "max_risk_score": self.max_risk_score,
            "max_mutations_per_epoch": self.max_mutations_per_epoch,
            "max_complexity_delta": self.max_complexity_delta,
            "freeze_tiers": list(self.freeze_tiers),
            "require_rules": list(self.require_rules),
            "min_test_coverage": self.min_test_coverage,
            "max_entropy_per_epoch": self.max_entropy_per_epoch,
            "escalate_reviewers_on_risk": self.escalate_reviewers_on_risk,
            "require_lineage_depth": self.require_lineage_depth,
            "source_expressions": list(self.source_expressions),
        }


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------

def interpret_policy(expressions: Sequence[ConstraintExpression]) -> SimulationPolicy:
    """Interpret a sequence of ConstraintExpression objects into a SimulationPolicy.

    Raises:
        SimulationPolicyError: If duplicate conflicting constraints are present for
            single-valued fields, or if any structural invariant is violated.

    Returns:
        SimulationPolicy with simulation=True always set.
    """
    require_approvals: Optional[Dict[str, Any]] = None
    max_risk_score: Optional[float] = None
    max_mutations_per_epoch: Optional[int] = None
    max_complexity_delta: Optional[float] = None
    freeze_tiers: List[str] = []
    require_rules: List[Dict[str, Any]] = []
    min_test_coverage: Optional[float] = None
    max_entropy_per_epoch: Optional[float] = None
    escalate_reviewers_on_risk: Optional[Dict[str, Any]] = None
    require_lineage_depth: Optional[int] = None
    source_expressions: List[str] = []

    for expr in expressions:
        source_expressions.append(expr.raw_expression)
        ct = expr.constraint_type
        kw = expr.kwargs

        if ct == ConstraintType.REQUIRE_APPROVALS:
            if require_approvals is not None:
                raise SimulationPolicyError(
                    "Duplicate constraint: require_approvals may only appear once per policy block."
                )
            require_approvals = {"tier": kw["tier"], "count": int(kw["count"])}

        elif ct == ConstraintType.MAX_RISK_SCORE:
            if max_risk_score is not None:
                raise SimulationPolicyError(
                    "Duplicate constraint: max_risk_score may only appear once per policy block."
                )
            max_risk_score = float(kw["threshold"])

        elif ct == ConstraintType.MAX_MUTATIONS_PER_EPOCH:
            if max_mutations_per_epoch is not None:
                raise SimulationPolicyError(
                    "Duplicate constraint: max_mutations_per_epoch may only appear once per policy block."
                )
            max_mutations_per_epoch = int(kw["count"])

        elif ct == ConstraintType.MAX_COMPLEXITY_DELTA:
            if max_complexity_delta is not None:
                raise SimulationPolicyError(
                    "Duplicate constraint: max_complexity_delta may only appear once per policy block."
                )
            max_complexity_delta = float(kw["delta"])

        elif ct == ConstraintType.FREEZE_TIER:
            tier = str(kw["tier"])
            if tier in freeze_tiers:
                raise SimulationPolicyError(
                    f"Duplicate constraint: freeze_tier for tier={tier!r} appears more than once."
                )
            freeze_tiers.append(tier)

        elif ct == ConstraintType.REQUIRE_RULE:
            rule_id = str(kw["rule_id"])
            severity = str(kw.get("severity", "BLOCKING")).upper()
            # Duplicates on the same rule_id are rejected.
            existing = [r for r in require_rules if r["rule_id"] == rule_id]
            if existing:
                raise SimulationPolicyError(
                    f"Duplicate constraint: require_rule for rule_id={rule_id!r} appears more than once."
                )
            require_rules.append({"rule_id": rule_id, "severity": severity})

        elif ct == ConstraintType.MIN_TEST_COVERAGE:
            if min_test_coverage is not None:
                raise SimulationPolicyError(
                    "Duplicate constraint: min_test_coverage may only appear once per policy block."
                )
            min_test_coverage = float(kw["threshold"])

        elif ct == ConstraintType.MAX_ENTROPY_PER_EPOCH:
            if max_entropy_per_epoch is not None:
                raise SimulationPolicyError(
                    "Duplicate constraint: max_entropy_per_epoch may only appear once per policy block."
                )
            max_entropy_per_epoch = float(kw["ceiling"])

        elif ct == ConstraintType.ESCALATE_REVIEWERS_ON_RISK:
            if escalate_reviewers_on_risk is not None:
                raise SimulationPolicyError(
                    "Duplicate constraint: escalate_reviewers_on_risk may only appear once per policy block."
                )
            escalate_reviewers_on_risk = {
                "threshold": float(kw["threshold"]),
                "count": int(kw["count"]),
            }

        elif ct == ConstraintType.REQUIRE_LINEAGE_DEPTH:
            if require_lineage_depth is not None:
                raise SimulationPolicyError(
                    "Duplicate constraint: require_lineage_depth may only appear once per policy block."
                )
            require_lineage_depth = int(kw["min"])

    return SimulationPolicy(
        simulation=True,
        require_approvals=require_approvals,
        max_risk_score=max_risk_score,
        max_mutations_per_epoch=max_mutations_per_epoch,
        max_complexity_delta=max_complexity_delta,
        freeze_tiers=list(freeze_tiers),
        require_rules=list(require_rules),
        min_test_coverage=min_test_coverage,
        max_entropy_per_epoch=max_entropy_per_epoch,
        escalate_reviewers_on_risk=escalate_reviewers_on_risk,
        require_lineage_depth=require_lineage_depth,
        constraint_count=len(expressions),
        grammar_version=DSL_GRAMMAR_VERSION,
        source_expressions=list(source_expressions),
    )


def interpret_policy_block(dsl_text: str) -> SimulationPolicy:
    """Parse and interpret a multi-line DSL policy block into a SimulationPolicy.

    Convenience wrapper combining parse_policy_block() and interpret_policy().

    Args:
        dsl_text: Multi-line DSL expression block; comments (#) and blank lines ignored.

    Returns:
        SimulationPolicy with simulation=True always set.

    Raises:
        SimulationDSLError: On any DSL parse failure.
        SimulationPolicyError: On conflicting or duplicate constraints.
    """
    expressions = parse_policy_block(dsl_text)
    return interpret_policy(expressions)


__all__ = [
    "SimulationPolicy",
    "SimulationPolicyError",
    "interpret_policy",
    "interpret_policy_block",
]
