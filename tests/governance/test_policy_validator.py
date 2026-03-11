import pytest
pytestmark = pytest.mark.governance_gate
# SPDX-License-Identifier: Apache-2.0

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from types import ModuleType

from runtime.governance.policy_validator import PolicyValidator


def _install_fake_constitution(monkeypatch, *, should_pass: bool) -> None:
    fake_module = ModuleType("runtime.constitution")
    fake_module.CONSTITUTION_VERSION = "v-test"

    def fake_loader(path: Path, expected_version: str) -> None:
        assert expected_version == "v-test"
        if not should_pass:
            raise ValueError("invalid policy")

    fake_module.load_constitution_policy = fake_loader
    monkeypatch.setitem(sys.modules, "runtime.constitution", fake_module)


def test_policy_validator_successful_validation_with_cleanup_success(monkeypatch) -> None:
    _install_fake_constitution(monkeypatch, should_pass=True)

    result = PolicyValidator().validate('{"ok": true}')

    assert result.valid
    assert result.errors == []


def test_policy_validator_validation_failure_with_cleanup_success(monkeypatch) -> None:
    _install_fake_constitution(monkeypatch, should_pass=False)

    result = PolicyValidator().validate("{}")

    assert not result.valid
    assert result.errors[0] == "invalid policy"
    assert result.errors[1].startswith("ledger_hash:")


def test_policy_validator_cleanup_failure_is_non_fatal(monkeypatch) -> None:
    _install_fake_constitution(monkeypatch, should_pass=True)

    def raise_oserror_on_unlink(self: Path) -> None:
        raise OSError("simulated cleanup failure")

    monkeypatch.setattr(Path, "unlink", raise_oserror_on_unlink)

    result = PolicyValidator().validate('{"ok": true}')

    assert result.valid
    assert result.errors == ["Temporary policy file cleanup failed: simulated cleanup failure"]


def test_policy_validator_parallel_validate_has_no_cross_talk(monkeypatch) -> None:
    fake_module = ModuleType("runtime.constitution")
    fake_module.CONSTITUTION_VERSION = "v-test"

    def fake_loader(path: Path, expected_version: str) -> None:
        assert expected_version == "v-test"
        if path.read_text(encoding="utf-8") == "{}":
            raise ValueError("invalid policy")

    fake_module.load_constitution_policy = fake_loader
    monkeypatch.setitem(sys.modules, "runtime.constitution", fake_module)

    valid_policy = '{"ok": true}'
    payloads = [valid_policy if i % 2 == 0 else "{}" for i in range(100)]

    validator = PolicyValidator()
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(validator.validate, payloads))

    for payload, result in zip(payloads, results, strict=True):
        expected_valid = payload == valid_policy
        assert result.valid is expected_valid
        if expected_valid:
            assert result.errors == []
        else:
            assert result.errors[0] == "invalid policy"
            assert result.errors[1].startswith("ledger_hash:")
