# SPDX-License-Identifier: Apache-2.0

import importlib
import sys

import pytest
pytestmark = pytest.mark.regression_standard


def _reload_legacy_modes_module() -> None:
    sys.modules.pop("runtime.api.legacy_modes", None)


def test_legacy_modes_fail_closed_in_strict_context(monkeypatch: pytest.MonkeyPatch) -> None:
    _reload_legacy_modes_module()
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.delenv("ADAAD_ENABLE_LEGACY_ORCHESTRATION_MODES", raising=False)

    with pytest.raises(RuntimeError, match="legacy_orchestration_modes_disabled"):
        importlib.import_module("runtime.api.legacy_modes")


def test_legacy_modes_can_be_explicitly_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _reload_legacy_modes_module()
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.setenv("ADAAD_ENABLE_LEGACY_ORCHESTRATION_MODES", "1")

    module = importlib.import_module("runtime.api.legacy_modes")

    assert hasattr(module, "BeastModeLoop")
    assert hasattr(module, "DreamMode")
