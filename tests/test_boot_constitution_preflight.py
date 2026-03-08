# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from app.boot_preflight import validate_boot_environment
from runtime.boot.preflight import evaluate_boot_invariants


def test_app_boot_preflight_rejects_constitution_version_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("ADAAD_CONSTITUTION_VERSION", "9.9.9")

    with pytest.raises(SystemExit, match="constitution_version_mismatch"):
        validate_boot_environment()


def test_runtime_boot_preflight_rejects_constitution_version_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_CONSTITUTION_VERSION", "9.9.9")
    result = evaluate_boot_invariants(replay_mode="audit", agents_root=Path("app/agents"))

    assert result.status == "error"
    assert result.payload["failed_check"] == "constitution_version"
    assert result.payload["reason_code"] == "boot_invariant_constitution_version_failed"
    assert str(result.payload["failed_reason"]).startswith("constitution_version_mismatch:")
