# SPDX-License-Identifier: Apache-2.0
"""Regression tests for phase sequence consistency validation."""

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import importlib.util
from pathlib import Path


def _load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_phase_sequence_consistency",
        Path("scripts/validate_phase_sequence_consistency.py"),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_next_pr_cannot_point_to_already_merged_phase6_pr(monkeypatch) -> None:
    module = _load_validator_module()

    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda *args, **kwargs: "abc Merge pull request #999 PR-PHASE6-04",
    )

    errors: list[str] = []
    module._validate_state_next_pr_not_merged(errors, "PR-PHASE6-02")

    assert any("already merged canonical PR" in item for item in errors)
