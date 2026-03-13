# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest

from adaad.agents.base_agent import validate_agents


pytestmark = pytest.mark.regression_standard


def _write_agent(agent_dir: Path, module_source: str) -> None:
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "meta.json").write_text(json.dumps({"id": agent_dir.name}), encoding="utf-8")
    (agent_dir / "dna.json").write_text("{}", encoding="utf-8")
    (agent_dir / "certificate.json").write_text("{}", encoding="utf-8")
    (agent_dir / "__init__.py").write_text(module_source, encoding="utf-8")


def test_validate_agents_reports_missing_function(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "adaad.agents.base_agent.metrics.log",
        lambda event_type, payload, level: events.append({"event_type": event_type, "payload": payload, "level": level}),
    )

    _write_agent(
        tmp_path / "broken_agent",
        """
class BrokenAgent:
    def info(self) -> dict:
        return {}

    def run(self, input=None) -> dict:
        return {}

    def score(self, output: dict) -> float:
        return 1.0
""",
    )

    valid, errors = validate_agents(tmp_path)
    assert not valid
    assert any("AGENT_CONTRACT_MISSING_FUNCTION:mutate" in err for err in errors)
    failure_event = next(event for event in events if event["event_type"] == "agent_validation_failed")
    assert "AGENT_CONTRACT_MISSING_FUNCTION" in failure_event["payload"]["error_codes"]


def test_validate_agents_reports_signature_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "adaad.agents.base_agent.metrics.log",
        lambda event_type, payload, level: events.append({"event_type": event_type, "payload": payload, "level": level}),
    )

    _write_agent(
        tmp_path / "signature_agent",
        """
class SignatureAgent:
    def info(self) -> dict:
        return {}

    def run(self, input) -> dict:
        return {}

    def mutate(self, src) -> str:
        return src

    def score(self, output: dict) -> float:
        return 1.0
""",
    )

    valid, errors = validate_agents(tmp_path)
    assert not valid
    assert any("AGENT_CONTRACT_SIGNATURE_MISMATCH:run" in err for err in errors)
    assert any("AGENT_CONTRACT_SIGNATURE_MISMATCH:mutate" in err for err in errors)


def test_validate_agents_accepts_valid_agent_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "adaad.agents.base_agent.metrics.log",
        lambda event_type, payload, level: events.append({"event_type": event_type, "payload": payload, "level": level}),
    )

    _write_agent(
        tmp_path / "valid_agent",
        """
class ValidAgent:
    def info(self) -> dict:
        return {"id": "valid"}

    def run(self, input=None) -> dict:
        return {"input": input}

    def mutate(self, src: str) -> str:
        return src

    def score(self, output: dict) -> float:
        return 1.0
""",
    )

    valid, errors = validate_agents(tmp_path)
    assert valid
    assert errors == []
    assert any(event["event_type"] == "agent_validation_passed" for event in events)
