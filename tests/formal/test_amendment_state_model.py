# SPDX-License-Identifier: Apache-2.0
from tools.formal.amendment_state_model import (
    Action,
    AmendmentState,
    check_properties,
    initial_state,
    transition,
)


def test_bounded_model_has_no_invariant_violations() -> None:
    assert check_properties(depth=4) == []


def test_pending_count_is_bounded_by_one() -> None:
    state = initial_state()
    state = transition(state, Action.QUEUE)
    again = transition(state, Action.PROPOSE)
    assert state.pending_count == 1
    assert again.pending_count == 1


def test_source_approval_does_not_bind_destination_after_federation() -> None:
    state = initial_state()
    state = transition(state, Action.QUEUE)
    state = transition(state, Action.APPROVE)
    federated = transition(state, Action.FEDERATE)
    assert federated.state == AmendmentState.FEDERATED
    assert federated.source_approved is True
    assert federated.destination_bound_to_source is False
