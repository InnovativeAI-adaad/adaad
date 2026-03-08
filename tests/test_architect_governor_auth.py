# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from adaad.agents.architect_governor import ArchitectGovernor


def test_execute_refactor_uses_governance_token_verifier(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    governor = ArchitectGovernor()

    monkeypatch.setattr(
        "security.cryovant.verify_session",
        lambda _token: (_ for _ in ()).throw(AssertionError("verify_session should not be called")),
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda _token: True)

    monkeypatch.setattr(governor.branch_manager, "create_branch", lambda _name: tmp_path)
    monkeypatch.setattr(governor.branch_manager, "promote", lambda _name, _targets: [tmp_path / t for t in _targets])
    monkeypatch.setattr(
        governor.certifier,
        "certify",
        lambda _path, _metadata=None: {"passed": True, "metadata": {}},
    )

    result = governor.execute_refactor(
        branch_name="feature-x",
        targets=["safe.py"],
        cryovant_token="token-ok",
        mutate=lambda path: path.write_text("print(1)\n", encoding="utf-8"),
    )

    assert result["success"] is True


def test_execute_refactor_raises_permission_error_for_expired_token(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    governor = ArchitectGovernor()
    def _raise_expired(_token: str) -> bool:
        from security.cryovant import TokenExpiredError

        raise TokenExpiredError("governance_token_expired:key_id=unit:expired_at=1")

    monkeypatch.setattr("security.cryovant.verify_governance_token", _raise_expired)

    with pytest.raises(PermissionError, match="Invalid cryovant_token: token_expired\\."):
        governor.execute_refactor(
            branch_name="feature-x",
            targets=["safe.py"],
            cryovant_token="expired-token",
        )

    assert any(
        record.__dict__.get("reason_code") == "architect_governor_auth_failed:token_expired"
        and "expired-token" not in record.getMessage()
        for record in caplog.records
    )


def test_execute_refactor_raises_permission_error_for_malformed_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governor = ArchitectGovernor()
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda _token: False)

    with pytest.raises(PermissionError, match="Invalid cryovant_token\\."):
        governor.execute_refactor(
            branch_name="feature-x",
            targets=["safe.py"],
            cryovant_token="malformed-token",
        )
