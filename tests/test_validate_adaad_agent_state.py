# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_NAME = "validate_adaad_agent_state.py"


def _run_validator(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, f"scripts/{SCRIPT_NAME}"],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_validator_fails_when_state_file_is_missing(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / SCRIPT_NAME
    (tmp_path / "scripts" / SCRIPT_NAME).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    result = _run_validator(tmp_path)

    assert result.returncode == 1
    assert "missing_file" in result.stdout


def test_validator_fails_on_malformed_payload(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / SCRIPT_NAME
    (tmp_path / "scripts" / SCRIPT_NAME).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    malformed_state = {
        "schema_version": "1.1.0",
        "last_completed_pr": "PR-CI-01",
    }
    (tmp_path / ".adaad_agent_state.json").write_text(
        json.dumps(malformed_state, indent=2) + "\n",
        encoding="utf-8",
    )

    result = _run_validator(tmp_path)

    assert result.returncode == 1
    assert "missing_keys" in result.stdout


def test_validator_passes_on_valid_payload(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / SCRIPT_NAME
    (tmp_path / "scripts" / SCRIPT_NAME).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    state = {
        "schema_version": "1.1.0",
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

    assert result.returncode == 0
    assert "adaad_agent_state_validation:ok" in result.stdout
