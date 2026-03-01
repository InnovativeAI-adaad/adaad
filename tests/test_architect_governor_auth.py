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
