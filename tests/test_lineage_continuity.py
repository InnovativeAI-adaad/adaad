import pytest

from runtime.constitution import validate_lineage_continuity


class MockMutation:
    def __init__(self, agent_id):
        self.agent_id = agent_id


def test_valid_lineage(monkeypatch):
    monkeypatch.setattr("security.ledger.lineage_v2.resolve_chain", lambda agent_id: ["a" * 64, "b" * 64, "c" * 64])
    mutation = MockMutation("agentA")
    assert validate_lineage_continuity(mutation) is True


def test_missing_parent(monkeypatch):
    monkeypatch.setattr("security.ledger.lineage_v2.resolve_chain", lambda agent_id: None)
    mutation = MockMutation("agentB")
    with pytest.raises(Exception):
        validate_lineage_continuity(mutation)


def test_tampered_chain(monkeypatch):
    monkeypatch.setattr("security.ledger.lineage_v2.resolve_chain", lambda agent_id: ["a" * 64, "corrupt"])
    mutation = MockMutation("agentC")
    with pytest.raises(Exception):
        validate_lineage_continuity(mutation)


def test_missing_genesis(monkeypatch):
    monkeypatch.setattr("security.ledger.lineage_v2.resolve_chain", lambda agent_id: ["", "b" * 64])
    mutation = MockMutation("agentD")
    with pytest.raises(Exception):
        validate_lineage_continuity(mutation)
