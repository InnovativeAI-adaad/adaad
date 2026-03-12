# SPDX-License-Identifier: Apache-2.0
import pytest
import os

pytestmark = pytest.mark.regression_standard
os.environ.setdefault("ADAAD_ENV", "dev")
os.environ.setdefault("ADAAD_POLICY_ARTIFACT_SIGNING_KEY", "test-key")

# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

from app.main import Orchestrator


def test_run_replay_preflight_delegates_to_module(monkeypatch):
    captured = {}

    def _fake(orchestrator, dump_func, *, verify_only=False):
        captured["orchestrator"] = orchestrator
        captured["dump_func"] = dump_func
        captured["verify_only"] = verify_only
        return {"ok": True}

    monkeypatch.setattr("app.main.run_replay_preflight", _fake)
    dummy = SimpleNamespace()
    result = Orchestrator._run_replay_preflight(dummy, verify_only=True)
    assert result == {"ok": True}
    assert captured["orchestrator"] is dummy
    assert callable(captured["dump_func"])
    assert captured["verify_only"] is True


def test_run_mutation_cycle_delegates_to_module(monkeypatch):
    captured = {}

    def _fake(orchestrator):
        captured["orchestrator"] = orchestrator

    monkeypatch.setattr("app.main.run_mutation_cycle", _fake)
    dummy = SimpleNamespace()
    Orchestrator._run_mutation_cycle(dummy)
    assert captured["orchestrator"] is dummy
