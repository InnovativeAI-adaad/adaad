# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import sys

from runtime.tools.execution_contract import (
    ToolExecutionRequest,
    classify_tool_result_for_governance,
    evaluate_governance_tool_findings,
    execute_tool_request,
    normalize_tool_output,
)


def test_normalize_tool_output_is_deterministic() -> None:
    raw = "line1  \r\nline2\rline3\n\n"
    assert normalize_tool_output(raw) == "line1\nline2\nline3"


def test_execute_tool_request_missing_dependency_classified() -> None:
    request = ToolExecutionRequest(
        tool_id="missing-tool",
        check_kind="lint",
        command=("__definitely_missing_executable__", "--version"),
    )
    result = execute_tool_request(request)

    assert result.status == "missing_dependency"
    finding = classify_tool_result_for_governance(result)
    assert finding.tier == "block"
    assert finding.should_block is True


def test_execute_tool_request_captures_normalized_output() -> None:
    request = ToolExecutionRequest(
        tool_id="echo-check",
        check_kind="dependency",
        command=(sys.executable, "-c", "import sys; print('ok\\r\\nvalue'); print('warn\\r', file=sys.stderr)"),
    )
    result = execute_tool_request(request)

    assert result.ok is True
    assert result.stdout == "ok\nvalue"
    assert result.stderr == "warn"


def test_evaluate_governance_tool_findings_tiers_are_stable() -> None:
    blocked = execute_tool_request(
        ToolExecutionRequest(
            tool_id="lint-fail",
            check_kind="lint",
            command=(sys.executable, "-c", "import sys; sys.exit(1)"),
        )
    )
    warned = execute_tool_request(
        ToolExecutionRequest(
            tool_id="dep-fail",
            check_kind="dependency",
            command=(sys.executable, "-c", "import sys; sys.exit(2)"),
        )
    )

    summary = evaluate_governance_tool_findings([blocked, warned])
    assert summary["ok"] is False
    assert summary["highest_tier"] == "block"
    assert summary["counts"] == {"block": 1, "warn": 1, "advisory": 0}
