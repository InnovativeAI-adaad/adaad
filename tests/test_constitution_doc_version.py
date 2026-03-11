import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from app.main import Orchestrator


class _FakeDocPath:
    def exists(self):
        return True

    def read_text(self, encoding="utf-8"):
        return "# ADAAD Framework v1.2.3\n\nVersion: 1.2.3\n"


class _FakeDocsDir:
    def __truediv__(self, _name):
        return _FakeDocPath()


class _FakeParent:
    def __truediv__(self, _name):
        return _FakeDocsDir()


class _FakeRoot:
    parent = _FakeParent()


def test_load_constitution_doc_version_returns_correct_version_from_markdown(monkeypatch):
    orch = Orchestrator(replay_mode="off")
    monkeypatch.setattr("app.main.APP_ROOT", _FakeRoot())
    assert orch._load_constitution_doc_version() == "1.2.3"


def test_load_constitution_doc_version_mismatch_triggers_governance_gate_failure(monkeypatch):
    orch = Orchestrator(replay_mode="off")
    monkeypatch.delenv("ADAAD_CONSTITUTION_VERSION", raising=False)
    monkeypatch.setattr(orch, "_load_constitution_doc_version", lambda: "9.9.9")

    ok, reason = orch._check_constitution_version()
    assert ok is False
    assert reason.startswith("constitution_version_mismatch:")
