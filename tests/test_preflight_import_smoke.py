import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

from adaad.agents.mutation_request import MutationRequest
import runtime.preflight as preflight
from runtime.preflight import _import_smoke_check, _legacy_validate_mutation, validate_mutation_proposal_schema


def _request_for_target(target: Path) -> MutationRequest:
    return MutationRequest(
        agent_id="test_subject",
        generation_ts="0",
        intent="test",
        ops=[{"file": str(target)}],
        signature="",
        nonce="",
    )


def test_import_smoke_check_does_not_execute_module(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "side_effect_marker.txt"
    target = tmp_path / "module_with_side_effect.py"
    target.write_text(
        """
import os
os.environ['PREFLIGHT_SIDE_EFFECT'] = '1'
with open(r'""" + str(marker) + """', 'w', encoding='utf-8') as handle:
    handle.write('executed')
""",
        encoding="utf-8",
    )

    monkeypatch.delenv("PREFLIGHT_SIDE_EFFECT", raising=False)
    result = _import_smoke_check(target, None)

    assert result["ok"] is True
    assert not marker.exists()
    assert "PREFLIGHT_SIDE_EFFECT" not in os.environ


def test_import_smoke_check_reports_missing_dependency_from_source() -> None:
    result = _import_smoke_check(Path("in_memory.py"), "import definitely_missing_package_123")

    assert result["ok"] is False
    assert result["reason"] == "missing_dependency:definitely_missing_package_123"
    assert result["missing_dependency"] == ["definitely_missing_package_123"]
    assert result["optional_dependency"] == []


def test_import_smoke_check_allows_local_package_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "ROOT_DIR", tmp_path)
    package_root = tmp_path / "localpkg"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")

    result = _import_smoke_check(Path("in_memory.py"), "import localpkg.module")

    assert result["ok"] is True
    assert result["missing_dependency"] == []


def test_import_smoke_check_tracks_optional_dependency() -> None:
    result = _import_smoke_check(
        Path("in_memory.py"),
        """
try:
    import definitely_missing_optional_123
except ImportError:
    definitely_missing_optional_123 = None
""",
    )

    assert result["ok"] is True
    assert result["missing_dependency"] == []
    assert result["optional_dependency"] == ["definitely_missing_optional_123"]


def test_legacy_preflight_pipeline_preserves_structured_reason_codes(tmp_path: Path) -> None:
    target = tmp_path / "needs_dep.py"
    target.write_text("import definitely_missing_package_123\n", encoding="utf-8")
    request = _request_for_target(target)

    legacy = _legacy_validate_mutation(request)
    assert legacy["ok"] is False
    assert legacy["reason"] == "missing_dependency:definitely_missing_package_123"

    target_details = legacy["checks"]["targets"][str(target)]["import_smoke"]
    assert target_details["reason"] == "missing_dependency:definitely_missing_package_123"
    assert target_details["missing_dependency"] == ["definitely_missing_package_123"]
    assert target_details["optional_dependency"] == []


def test_legacy_preflight_pipeline_preserves_syntax_reason(tmp_path: Path) -> None:
    target = tmp_path / "broken.py"
    target.write_text("def broken(:\n", encoding="utf-8")
    request = _request_for_target(target)

    legacy = _legacy_validate_mutation(request)

    assert legacy["ok"] is False
    assert legacy["reason"].startswith("syntax_error:")
    assert legacy["checks"]["targets"][str(target)]["ast_parse"]["reason"].startswith("syntax_error:")


def test_import_smoke_check_fails_closed_with_stable_reason_code_on_parse_failure(monkeypatch) -> None:
    monkeypatch.setattr(preflight.ast, "parse", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad-ast")))
    result = _import_smoke_check(Path("broken.py"), "import os")

    assert result["ok"] is False
    assert result["reason"] == "import_analysis_failed"
    assert result["reason_code"] == "import_analysis_failed"
    assert result["operation_class"] == "governance-critical"
    assert result["context"]["error_type"] == "ValueError"



def test_validate_mutation_proposal_schema_accepts_valid_payload() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="2026-01-01T00:00:00Z",
        intent="test",
        ops=[{"op": "noop"}],
        signature="sig",
        nonce="nonce",
    )

    result = validate_mutation_proposal_schema(request.to_dict())

    assert result["ok"] is True


def test_validate_mutation_proposal_schema_rejects_unexpected_fields() -> None:
    payload = {
        "agent_id": "test_subject",
        "generation_ts": "2026-01-01T00:00:00Z",
        "intent": "test",
        "ops": [],
        "targets": [],
        "signature": "sig",
        "nonce": "nonce",
        "unexpected": True,
    }

    result = validate_mutation_proposal_schema(payload)

    assert result["ok"] is False
    assert result["reason"] == "invalid_mutation_proposal_schema"
    assert "$.unexpected:additional_property" in result["errors"]


def test_validate_mutation_fail_closed_when_legacy_preflight_disabled_in_strict_context(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "noop.py"
    target.write_text("x = 1\n", encoding="utf-8")
    request = _request_for_target(target)

    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.delenv("ADAAD_ENABLE_LEGACY_MUTATION_PREFLIGHT", raising=False)

    result = preflight.validate_mutation(request, tier=None)

    assert result["ok"] is False
    assert result["reason"] == "legacy_mutation_preflight_disabled"
    assert result["operation_class"] == "governance-critical"


def test_validate_mutation_allows_legacy_preflight_with_explicit_flag(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "noop.py"
    target.write_text("x = 1\n", encoding="utf-8")
    request = _request_for_target(target)

    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.setenv("ADAAD_ENABLE_LEGACY_MUTATION_PREFLIGHT", "1")

    result = preflight.validate_mutation(request, tier=None)

    assert result["ok"] is True
    assert result["reason"] == "ok"
