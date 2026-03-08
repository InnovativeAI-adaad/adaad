# SPDX-License-Identifier: Apache-2.0

import sys

from scripts.run_tier0_preflight import Check, CheckResult, _print_summary, main


def test_check_skip_if_missing_default_is_fail_closed() -> None:
    check = Check(name="x", command="missing-cmd")
    assert check.skip_if_missing is False
    assert check.mandatory is True


def test_no_tests_requires_check_only(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["run_tier0_preflight.py", "--no-tests"])
    code = main()
    out = capsys.readouterr().out
    assert code != 0
    assert "[ADAAD BLOCKED]" in out


def test_summary_diagnostic_not_full_green(capsys) -> None:
    _print_summary(
        [
            CheckResult(name="schema", status="passed", detail="ok"),
            CheckResult(name="tests", status="skipped", detail="diagnostic"),
        ]
    )
    out = capsys.readouterr().out
    assert "Tier 0 diagnostic complete" in out
    assert "Tier 0 green: all mandatory checks passed." not in out
