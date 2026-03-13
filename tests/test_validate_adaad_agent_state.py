# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression_standard

SCRIPT_NAME = "validate_adaad_agent_state.py"
OUTPUT_PREFIX = "adaad_agent_state_validation:"


@pytest.fixture
def validator_workspace(tmp_path: Path) -> Path:
    src_scripts = Path(__file__).resolve().parents[1] / "scripts"
    dst_scripts = tmp_path / "scripts"
    shutil.copytree(src_scripts, dst_scripts)
    return tmp_path


@pytest.fixture
def valid_state_payload() -> dict[str, object]:
    return {
        "schema_version": "1.5.0",
        "last_completed_pr": "PR-CI-01",
        "next_pr": "PR-CI-02",
        "active_phase": "Phase 0 Track A",
        "last_invocation": None,
        "blocked_reason": None,
        "blocked_at_gate": None,
        "blocked_at_tier": None,
        "last_gate_results": {
            "tier_0": "not_run",
            "tier_1": "not_run",
            "tier_2": "not_applicable",
            "tier_3": "not_run",
        },
        "open_findings": ["C-02"],
        "value_checkpoints_reached": [],
        "pending_evidence_rows": ["spdx-header-compliance"],
    }


def _run_validator(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, f"scripts/{SCRIPT_NAME}"],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_state(cwd: Path, payload: dict[str, object]) -> None:
    (cwd / ".adaad_agent_state.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_validator_fails_when_state_file_is_missing(validator_workspace: Path) -> None:
    result = _run_validator(validator_workspace)

    assert result.returncode == 1
    assert f"{OUTPUT_PREFIX}failed" in result.stdout
    assert "missing_file" in result.stdout


def test_validator_passes_on_valid_current_payload(
    validator_workspace: Path,
    valid_state_payload: dict[str, object],
) -> None:
    _write_state(validator_workspace, valid_state_payload)

    result = _run_validator(validator_workspace)

    assert result.returncode == 0
    assert f"{OUTPUT_PREFIX}ok" in result.stdout


def test_validator_fails_on_unsupported_schema_version(
    validator_workspace: Path,
    valid_state_payload: dict[str, object],
) -> None:
    valid_state_payload["schema_version"] = "9.9.9"
    _write_state(validator_workspace, valid_state_payload)

    result = _run_validator(validator_workspace)

    assert result.returncode == 1
    assert f"{OUTPUT_PREFIX}failed" in result.stdout
    assert "schema_version:expected_1.5.0" in result.stdout


def test_validator_fails_when_required_top_level_key_is_missing(
    validator_workspace: Path,
    valid_state_payload: dict[str, object],
) -> None:
    valid_state_payload.pop("next_pr")
    _write_state(validator_workspace, valid_state_payload)

    result = _run_validator(validator_workspace)

    assert result.returncode == 1
    assert f"{OUTPUT_PREFIX}failed" in result.stdout
    assert "missing_keys:next_pr" in result.stdout


def test_validator_fails_on_invalid_last_gate_results_status_value(
    validator_workspace: Path,
    valid_state_payload: dict[str, object],
) -> None:
    gate_results = valid_state_payload["last_gate_results"]
    assert isinstance(gate_results, dict)
    gate_results["tier_1"] = "unknown"
    _write_state(validator_workspace, valid_state_payload)

    result = _run_validator(validator_workspace)

    assert result.returncode == 1
    assert f"{OUTPUT_PREFIX}failed" in result.stdout
    assert "last_gate_results.tier_1:invalid_status" in result.stdout


def test_validator_fails_on_wrong_type_for_nullable_or_string_fields(
    validator_workspace: Path,
    valid_state_payload: dict[str, object],
) -> None:
    valid_state_payload["last_invocation"] = []
    valid_state_payload["blocked_reason"] = 123
    _write_state(validator_workspace, valid_state_payload)

    result = _run_validator(validator_workspace)

    assert result.returncode == 1
    assert f"{OUTPUT_PREFIX}failed" in result.stdout
    assert "last_invocation:expected_string_or_null" in result.stdout
    assert "blocked_reason:expected_string_or_null" in result.stdout


def test_validator_accepts_optional_null_fields(
    validator_workspace: Path,
    valid_state_payload: dict[str, object],
) -> None:
    valid_state_payload["last_invocation"] = None
    valid_state_payload["blocked_reason"] = None
    valid_state_payload["blocked_at_gate"] = None
    valid_state_payload["blocked_at_tier"] = None
    _write_state(validator_workspace, valid_state_payload)

    result = _run_validator(validator_workspace)

    assert result.returncode == 0
    assert "adaad_agent_state_validation:ok" in result.stdout


def test_validator_fails_on_unsupported_schema_version(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / SCRIPT_NAME
    (tmp_path / "scripts" / SCRIPT_NAME).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    state = {
        "schema_version": "1.0.0",
        "last_completed_pr": "PR-CI-01",
        "next_pr": "PR-CI-02",
        "active_phase": "Phase 0 Track A",
        "last_invocation": None,
        "blocked_reason": None,
        "blocked_at_gate": None,
        "blocked_at_tier": None,
        "last_gate_results": {
            "tier_0": "not_run",
            "tier_1": "not_run",
            "tier_2": "not_applicable",
            "tier_3": "not_run",
        },
        "open_findings": ["C-02"],
        "value_checkpoints_reached": [],
        "pending_evidence_rows": ["spdx-header-compliance"],
    }
    (tmp_path / ".adaad_agent_state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    result = _run_validator(tmp_path)

    assert result.returncode == 1
    # Keep this aligned with the reason code emitted by `_validate_state` in
    # `scripts/validate_adaad_agent_state.py` when schema_version != "1.5.0".
    assert "schema_version:expected_" in result.stdout
    assert "1.5.0" in result.stdout
