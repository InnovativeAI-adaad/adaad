# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import builtins
import socket

import pytest

from runtime.evolution.replay_state_machine import ReplayStateMachine


def _events() -> list[dict[str, object]]:
    return [
        {
            "epoch_id": "epoch-001",
            "passed": True,
            "decision": "match",
            "replay_score": 1.0,
            "federation_drift_detected": False,
        },
        {
            "epoch_id": "epoch-002",
            "passed": False,
            "decision": "diverge",
            "replay_score": 0.4,
            "federation_drift_detected": True,
        },
    ]


def test_identical_input_stream_is_hash_and_manifest_stable() -> None:
    stream = _events()

    first = ReplayStateMachine.transition(
        mode="strict",
        fail_closed=True,
        verify_target="all_epochs",
        events=stream,
        prior_state={"state_hash": "sha256:base"},
    )
    second = ReplayStateMachine.transition(
        mode="strict",
        fail_closed=True,
        verify_target="all_epochs",
        events=stream,
        prior_state={"state_hash": "sha256:base"},
    )

    assert first["next_state"]["state_hash"] == second["next_state"]["state_hash"]
    assert first["manifest_payload"] == second["manifest_payload"]
    assert first["invariant_checks"]["halt_reason"] == "federation_drift_detected"
    assert first["invariant_checks"]["divergence_class"] == "federation_drift_detected"


def test_state_machine_performs_no_filesystem_or_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("state machine attempted side effect")

    monkeypatch.setattr(builtins, "open", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    result = ReplayStateMachine.transition(
        mode="audit",
        fail_closed=False,
        verify_target="single_epoch",
        events=[{"epoch_id": "epoch-1", "passed": True, "federation_drift_detected": False}],
        prior_state=None,
    )

    assert result["invariant_checks"]["decision"] == "continue"
    assert result["invariant_checks"]["halt_reason"] is None
