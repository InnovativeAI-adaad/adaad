# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.governance_gate

from pathlib import Path

from runtime.governance.canon_law import CanonClause
from runtime.governance.gate_certifier import GateCertifier


def test_forbidden_tokens_rejected(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "bad.py"
    target.write_text(
        """import os
os.system('rm -rf /')
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "x" * 24})
    assert cert["passed"] is False
    assert cert["checks"]["token_ok"] is False


def test_banned_imports_rejected(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "bad_import.py"
    target.write_text(
        """import subprocess
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "y" * 24})
    assert cert["passed"] is False
    assert cert["checks"]["import_ok"] is False


def test_ast_rejects_dynamic_exec_alias_indirection(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "dynamic_alias.py"
    target.write_text(
        """import builtins as b
runner = getattr(b, 'eval')
runner('1 + 1')
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "z" * 24})
    assert cert["passed"] is False
    assert cert["checks"]["ast_ok"] is False
    assert "dynamic_primitive_alias:runner" in cert["checks"]["ast_violations"]


def test_ast_rejects_subprocess_aliased_import_usage(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "subprocess_alias.py"
    target.write_text(
        """import subprocess as sp
sp.Popen(['echo', 'hi'])
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "a" * 24})
    assert cert["passed"] is False
    assert cert["checks"]["ast_ok"] is False
    assert "module_runtime_risk:subprocess.Popen" in cert["checks"]["ast_violations"]


def test_ast_rejects_socket_import_from_alias(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "socket_import_from.py"
    target.write_text(
        """from socket import socket as sk
client = sk()
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "b" * 24})
    assert cert["passed"] is False
    assert cert["checks"]["ast_ok"] is False
    assert "module_runtime_risk:socket.socket" in cert["checks"]["ast_violations"]


def test_token_required(tmp_path: Path) -> None:
    target = tmp_path / "ok.py"
    target.write_text(
        """print('ok')
""",
        encoding="utf-8",
    )
    cert = GateCertifier().certify(target, {"cryovant_token": "short"})
    assert cert["passed"] is False
    assert cert["checks"]["auth_ok"] is False


def test_token_redacted(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "ok2.py"
    target.write_text(
        """print('ok')
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "SENSITIVE"})
    assert cert["passed"] is True
    assert "cryovant_token" not in cert.get("metadata", {})


def test_generated_at_uses_injected_clock(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "ok3.py"
    target.write_text(
        """print('ok')
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier(clock_now_iso=lambda: "2030-01-01T00:00:00Z").certify(
        target, {"cryovant_token": "fixed"}
    )
    assert cert["generated_at"] == "2030-01-01T00:00:00Z"


def test_ast_rejects_alias_chain_to_subprocess_call(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "subprocess_alias_chain.py"
    target.write_text(
        """import subprocess as sp
runner = sp
invoke = runner.Popen
invoke(['echo', 'hi'])
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "c" * 24})
    assert cert["passed"] is False
    assert cert["checks"]["ast_ok"] is False
    assert "module_runtime_risk:subprocess.Popen" in cert["checks"]["ast_violations"]


def test_ast_rejects_dynamic_exec_via_import_alias_chain(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "import_alias_chain.py"
    target.write_text(
        """loader = __import__
builtins_mod = loader('builtins')
compiler = getattr(builtins_mod, 'compile')
compiler('1 + 1', '<x>', 'eval')
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "d" * 24})
    assert cert["passed"] is False
    assert cert["checks"]["ast_ok"] is False
    assert "dynamic_primitive_alias:loader" in cert["checks"]["ast_violations"]
    assert "dynamic_primitive_alias:compiler" in cert["checks"]["ast_violations"]


def test_ast_rejects_exec_via_getattr_call_path(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "exec_getattr_path.py"
    target.write_text(
        """import builtins
getattr(builtins, 'exec')('x = 42')
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "e" * 24})
    assert cert["passed"] is False
    assert cert["checks"]["ast_ok"] is False
    assert "attribute_dynamic_primitive:builtins.exec" in cert["checks"]["ast_violations"]


def test_certify_result_contains_semantic_violations_field(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "semantic_violation_fixture.py"
    target.write_text(
        "import builtins as b\n"
        "runner = getattr(b, 'eval')\n"
        "runner('1 + 1')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)

    monkeypatch.setattr(
        "runtime.governance.gate_certifier.load_canon_law",
        lambda: {
            "IV.gate_forbidden_code_block": CanonClause(
                article="IV",
                clause_id="IV.gate_forbidden_code_block",
                applies_to="runtime.governance.gate_certifier",
                enforcement="static_analysis",
                escalation="critical",
                mutation_block=True,
                fail_closed=False,
            ),
            "V.gate_authentication_required": CanonClause(
                article="V",
                clause_id="V.gate_authentication_required",
                applies_to="runtime.governance.gate_certifier",
                enforcement="cryovant_auth",
                escalation="governance",
                mutation_block=True,
                fail_closed=True,
            ),
            "III.gate_file_must_exist": CanonClause(
                article="III",
                clause_id="III.gate_file_must_exist",
                applies_to="runtime.governance.gate_certifier",
                enforcement="file_guard",
                escalation="governance",
                mutation_block=True,
                fail_closed=False,
            ),
            "VIII.undefined_state_fail_closed": CanonClause(
                article="VIII",
                clause_id="VIII.undefined_state_fail_closed",
                applies_to="runtime.governance.gate_certifier",
                enforcement="fail_closed",
                escalation="critical",
                mutation_block=True,
                fail_closed=True,
            ),
        },
    )

    certifier = GateCertifier()
    result = certifier.certify(target, {"cryovant_token": "x" * 24})

    assert "checks" in result
    assert "semantic_violations" in result["checks"]
    semantic_violations = result["checks"]["semantic_violations"]
    assert isinstance(semantic_violations, list)
    assert semantic_violations
    assert {"kind", "detail", "line"}.issubset(semantic_violations[0].keys())


def test_token_scan_is_binding_for_certification(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "token_only_violation.py"
    target.write_text(
        'SAFE = "eval("\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "ok-token"})
    assert cert["checks"]["token_ok"] is False
    assert cert["checks"]["ast_ok"] is True
    assert cert["checks"]["import_ok"] is True
    assert cert["passed"] is False


def test_certifier_does_not_call_deprecated_verify_session(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "ok_no_verify_session.py"
    target.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr("security.cryovant.verify_session", lambda _token: (_ for _ in ()).throw(AssertionError("verify_session should not be called")))
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda _token: True)

    cert = GateCertifier().certify(target, {"cryovant_token": "token-ok"})
    assert cert["checks"]["auth_ok"] is True
    assert cert["passed"] is True
