# SPDX-License-Identifier: Apache-2.0
"""Regression tests for phase sequence consistency validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression_standard


def _load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_phase_sequence_consistency",
        Path("scripts/validate_phase_sequence_consistency.py"),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_accepts_current_canonical_expected_next_format() -> None:
    module = _load_validator_module()

    errors: list[str] = []
    module._validate_state_next_pr_matches_active_progression(
        errors,
        "Phase 94 — INNOV-10 roadmap execution",
    )

    assert errors == []


def test_rejects_regression_to_already_shipped_phase() -> None:
    module = _load_validator_module()

    errors: list[str] = []
    module._validate_state_next_pr_matches_active_progression(
        errors,
        "Phase 90 — INNOV-06 Cryptographic Evolution Proof DAG",
    )

    assert any("regresses to already shipped phase 90" in error for error in errors)
    assert any("is not serial" in error for error in errors)
