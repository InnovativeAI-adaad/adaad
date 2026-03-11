# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.promotion_state_machine import (
    PromotionState,
    PromotionTransitionContext,
    TransitionGuardFailed,
    require_transition,
)
from runtime.mutation_lifecycle import LifecycleTransitionError, MutationLifecycleContext, transition


def test_promotion_state_machine_allows_declared_transitions_with_guards(monkeypatch) -> None:
    import security.cryovant as _cryovant
    monkeypatch.setattr(_cryovant, "signature_valid", lambda sig: sig == "cryovant-static-valid-signature")
    context = PromotionTransitionContext(
        signature="cryovant-static-valid-signature",
        trust_mode="prod",
        fitness_score=0.9,
        fitness_threshold=0.5,
    )

    proposed_to_certified = require_transition(PromotionState.PROPOSED, PromotionState.CERTIFIED, context)
    certified_to_activated = require_transition(PromotionState.CERTIFIED, PromotionState.ACTIVATED, context)

    assert proposed_to_certified["ok"] is True
    assert certified_to_activated["ok"] is True


def test_promotion_state_machine_rejects_guard_failures() -> None:
    context = PromotionTransitionContext(signature="bad", trust_mode="prod", fitness_score=0.1, fitness_threshold=0.5)

    with pytest.raises(TransitionGuardFailed, match="guard_failed:certified->activated") as exc:
        require_transition(PromotionState.CERTIFIED, PromotionState.ACTIVATED, context)

    assert exc.value.guard_report["cryovant_signature_validity"]["ok"] is False
    assert exc.value.guard_report["fitness_threshold_gate"]["ok"] is False


def test_mutation_lifecycle_guard_rejection_emits_rejected_event(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rejected_payloads: list[dict[str, object]] = []

    monkeypatch.setattr("runtime.mutation_lifecycle._record_rejection", lambda payload: rejected_payloads.append(payload))
    context = MutationLifecycleContext(
        mutation_id="mut-reject",
        agent_id="agent-1",
        epoch_id="epoch-1",
        signature="invalid",
        trust_mode="prod",
        state_dir=tmp_path / "state",
    )

    with pytest.raises(LifecycleTransitionError, match="guard_failed:proposed->staged"):
        transition("proposed", "staged", context)

    assert len(rejected_payloads) == 1
    assert rejected_payloads[0]["to_state"] == "staged"
    assert rejected_payloads[0]["guard_report"]["ok"] is False


def test_promotion_state_machine_fail_closes_on_founders_key_rotation_failure(monkeypatch) -> None:
    import security.cryovant as _cryovant
    monkeypatch.setattr(_cryovant, "signature_valid", lambda sig: sig == "cryovant-static-valid-signature")
    context = PromotionTransitionContext(
        signature="cryovant-static-valid-signature",
        trust_mode="prod",
        fitness_score=0.9,
        fitness_threshold=0.5,
        founders_law_check=lambda: (False, ["FL-KEY-ROTATION-V1:stale"]),
    )

    with pytest.raises(TransitionGuardFailed, match="guard_failed:certified->activated") as exc:
        require_transition(PromotionState.CERTIFIED, PromotionState.ACTIVATED, context)

    assert exc.value.guard_report["founders_law_invariant_gate"]["ok"] is False
    assert exc.value.guard_report["founders_law_invariant_gate"]["failures"] == ["FL-KEY-ROTATION-V1:stale"]
