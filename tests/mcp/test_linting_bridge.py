# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from runtime.constitution import CONSTITUTION_VERSION
from runtime.mcp.linting_bridge import MutationLintingBridge


class _ThrottleSnapshot:
    def __init__(self, should: bool) -> None:
        self._should = should

    def should_throttle(self) -> bool:
        return self._should


class _Monitor:
    def __init__(self, should: bool) -> None:
        self._should = should

    def snapshot(self):
        return _ThrottleSnapshot(self._should)


def test_linting_bridge_emits_stable_annotations() -> None:
    bridge = MutationLintingBridge()
    payload = {
        "complexity_delta": 0.23,
        "constitutional_compliance": 0.2,
        "stability_heuristics": 0.1,
    }

    first = bridge.analyze(payload)
    second = bridge.analyze(payload)

    assert first == second
    assert first["preview_authoritative"] is False
    assert first["gate"] == "queue_append_constitutional_evaluation"
    assert [item["severity"] for item in first["annotations"]] == ["BLOCKING", "BLOCKING", "WARNING"]
    for annotation in first["annotations"]:
        assert annotation["constitution_version"] == CONSTITUTION_VERSION


def test_linting_bridge_android_throttle_signal() -> None:
    bridge = MutationLintingBridge(android_monitor=_Monitor(True))
    payload = {"constitutional_compliance": 0.9, "stability_heuristics": 0.9}

    result = bridge.analyze(payload)

    assert result["throttle"] is True
