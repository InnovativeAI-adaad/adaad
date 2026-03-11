import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

import sys

from scripts.run_tier0_preflight import (
    Check,
    CheckResult,
    _command_exists,
    _missing_test_extras,
    _print_summary,
    _test_mode_enabled,
    main,
)


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


def test_command_exists_plain_command() -> None:
    assert _command_exists("python scripts/validate_governance_schemas.py")


def test_command_exists_env_prefixed_command() -> None:
    assert _command_exists("PYTHONPATH=. pytest tests/ -q")


def test_command_exists_multiple_assignments() -> None:
    assert _command_exists("A=1 B=2 pytest tests/ -q")


def test_command_exists_missing_executable() -> None:
    assert not _command_exists("A=1 __definitely_missing_executable__ --version")


def test_test_mode_enabled_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_TEST_MODE", "1")
    assert _test_mode_enabled() is True


def test_missing_test_extras_collects_missing(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cryptography":
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    missing = _missing_test_extras()
    assert "cryptography" in missing


def test_main_blocks_when_test_mode_missing_extras(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ADAAD_TEST_MODE", "1")
    monkeypatch.setattr(sys, "argv", ["run_tier0_preflight.py"])
    monkeypatch.setattr("scripts.run_tier0_preflight._missing_test_extras", lambda: ["cryptography"])

    code = main()
    out = capsys.readouterr().out

    assert code == 2
    assert "[ADAAD BLOCKED] missing test-mode extras" in out
