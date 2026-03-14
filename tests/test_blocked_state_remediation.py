# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json

import pytest

from adaad.orchestrator.remediation import format_blocked_state, gate_id_for_tier0_check


pytestmark = pytest.mark.regression_standard


def _extract_remediation_json(message: str) -> dict[str, object]:
    line = next(item for item in message.splitlines() if item.startswith("Remediation JSON: "))
    return json.loads(line.split("Remediation JSON: ", 1)[1])


def test_tier0_blocked_message_is_machine_parseable_and_complete() -> None:
    message = format_blocked_state(
        status="[ADAAD BLOCKED]",
        gate_id="TIER0_DETERMINISM_LINT",
        failure_detail="non-zero exit: 1",
        action_required="Fix deterministic violations and rerun Tier 0.",
    )

    assert "Action required: Fix deterministic violations and rerun Tier 0." in message
    payload = _extract_remediation_json(message)
    assert payload["status"] == "ADAAD BLOCKED"
    assert payload["gate_id"] == "TIER0_DETERMINISM_LINT"
    assert payload["minimal_repro_command"] == "python tools/lint_determinism.py runtime/ security/ adaad/orchestrator/ app/main.py"
    assert payload["expected_pass_condition"]
    assert payload["probable_root_causes"]


def test_tier1_blocked_message_includes_action_required_and_repro() -> None:
    message = format_blocked_state(
        status="[ADAAD BLOCKED]",
        gate_id="TIER1_FULL_TEST_SUITE",
        failure_detail="test failure: tests/example.py::test_case",
    )

    payload = _extract_remediation_json(message)
    assert payload["gate_type"] == "tier1"
    assert payload["minimal_repro_command"] == "PYTHONPATH=. pytest tests/ -q"
    assert payload["action_required"] == payload["next_allowed_action"]


def test_tier_m_merge_blocked_message_includes_required_fields() -> None:
    message = format_blocked_state(
        status="[DEVADAAD MERGE-BLOCKED]",
        gate_id="TIERM_WORKING_CODE_ASSERTION",
        failure_detail="merge sha regression detected",
        action_required="Re-run all gates on merge SHA before merge.",
    )

    payload = _extract_remediation_json(message)
    assert payload["status"] == "DEVADAAD MERGE-BLOCKED"
    assert payload["gate_type"] == "tier_m"
    assert payload["expected_pass_condition"] == "merge SHA test run has 0 failed tests and 0 skipped tests in scope"
    assert payload["action_required"] == "Re-run all gates on merge SHA before merge."


def test_tier0_check_mapping_is_deterministic() -> None:
    assert gate_id_for_tier0_check("schema validation") == "TIER0_SCHEMA_VALIDATION"

    with pytest.raises(KeyError, match="unknown_tier0_check"):
        gate_id_for_tier0_check("unknown gate")
