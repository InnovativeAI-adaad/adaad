# SPDX-License-Identifier: Apache-2.0
"""Formal amendment workflow state model and executable invariants.

This module defines a minimal bounded model for amendment workflows and checks
safety properties derived from:
- docs/governance/SECURITY_INVARIANTS_MATRIX.md (Phase6-SEC-* subset)
- Phase 6 constitutional invariants (PHASE6-AUTH-0/STORM-0/FED-0/HUMAN-0)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import Iterable


class AmendmentState(str, Enum):
    PROPOSAL = "proposal"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FEDERATED = "federated"


class Action(str, Enum):
    PROPOSE = "propose"
    QUEUE = "queue"
    APPROVE = "approve"
    REJECT = "reject"
    FEDERATE = "federate"


@dataclass(frozen=True)
class ModelState:
    """Minimal system state for one proposal and one destination peer."""

    state: AmendmentState
    authority_level: str
    pending_count: int
    source_approved: bool
    destination_bound_to_source: bool
    human_signoff_token_present: bool


def initial_state() -> ModelState:
    return ModelState(
        state=AmendmentState.PROPOSAL,
        authority_level="governor-review",
        pending_count=0,
        source_approved=False,
        destination_bound_to_source=False,
        human_signoff_token_present=False,
    )


def transition(model: ModelState, action: Action) -> ModelState:
    """Deterministic transition function.

    Invariant-enforcing semantics:
    - PHASE6-AUTH-0 / Phase6-SEC-01: authority level is immutable.
    - PHASE6-STORM-0 / Phase6-SEC-09: at most one pending amendment.
    - PHASE6-FED-0 / Phase6-SEC-12: source approval does not auto-bind destination.
    - PHASE6-HUMAN-0 / Phase6-SEC-07: approval alone cannot commit human sign-off.
    """

    if action is Action.PROPOSE:
        if model.pending_count > 0:
            return model
        return ModelState(
            state=AmendmentState.PROPOSAL,
            authority_level=model.authority_level,
            pending_count=model.pending_count,
            source_approved=False,
            destination_bound_to_source=False,
            human_signoff_token_present=False,
        )

    if action is Action.QUEUE and model.state is AmendmentState.PROPOSAL:
        return ModelState(
            state=AmendmentState.PENDING,
            authority_level=model.authority_level,
            pending_count=1,
            source_approved=False,
            destination_bound_to_source=False,
            human_signoff_token_present=False,
        )

    if action is Action.APPROVE and model.state is AmendmentState.PENDING:
        return ModelState(
            state=AmendmentState.APPROVED,
            authority_level=model.authority_level,
            pending_count=0,
            source_approved=True,
            destination_bound_to_source=False,
            human_signoff_token_present=False,
        )

    if action is Action.REJECT and model.state in {AmendmentState.PENDING, AmendmentState.PROPOSAL}:
        return ModelState(
            state=AmendmentState.REJECTED,
            authority_level=model.authority_level,
            pending_count=0,
            source_approved=False,
            destination_bound_to_source=False,
            human_signoff_token_present=False,
        )

    if action is Action.FEDERATE and model.state in {AmendmentState.PENDING, AmendmentState.APPROVED}:
        return ModelState(
            state=AmendmentState.FEDERATED,
            authority_level=model.authority_level,
            pending_count=model.pending_count,
            source_approved=model.source_approved,
            destination_bound_to_source=False,
            human_signoff_token_present=False,
        )

    return model


def _all_traces(depth: int) -> Iterable[tuple[Action, ...]]:
    actions = tuple(Action)
    for length in range(1, depth + 1):
        for trace in product(actions, repeat=length):
            yield trace


def check_properties(depth: int = 5) -> list[str]:
    """Return violations discovered while bounded-model checking."""

    violations: list[str] = []
    for trace in _all_traces(depth):
        state = initial_state()
        for action in trace:
            state = transition(state, action)

            if state.authority_level != "governor-review":
                violations.append(f"PHASE6-AUTH-0 violated by trace={trace}")

            if state.pending_count > 1:
                violations.append(f"PHASE6-STORM-0 violated by trace={trace}")

            if state.source_approved and state.destination_bound_to_source:
                violations.append(f"PHASE6-FED-0 violated by trace={trace}")

            if state.state is AmendmentState.APPROVED and state.human_signoff_token_present:
                violations.append(f"PHASE6-HUMAN-0 violated by trace={trace}")

    return violations


def main() -> int:
    violations = check_properties()
    if violations:
        print("FORMAL_MODEL_CHECK_FAILED")
        for violation in violations:
            print(violation)
        return 1
    print("FORMAL_MODEL_CHECK_PASSED depth=5 states=bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
