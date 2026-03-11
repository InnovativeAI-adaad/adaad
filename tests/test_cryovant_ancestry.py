# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from unittest.mock import Mock

from security import cryovant


def test_validate_ancestry_rejects_missing_id_with_existing_reason(monkeypatch):
    mock_log = Mock()
    mock_write = Mock()

    monkeypatch.setattr(cryovant.journal, "read_entries", lambda limit=200: [{"agent_id": "alpha"}])
    monkeypatch.setattr(cryovant.journal, "write_entry", mock_write)
    monkeypatch.setattr(cryovant.metrics, "log", mock_log)

    assert cryovant.validate_ancestry(None) is False

    mock_write.assert_called_once_with(agent_id="unknown", action="ancestry_failed", payload={"reason": "missing_id"})
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["event_type"] == "cryovant_invalid_agent_id"


def test_validate_ancestry_denies_empty_journal_without_override(monkeypatch):
    mock_log = Mock()
    mock_write = Mock()

    monkeypatch.delenv("ADAAD_ALLOW_GENESIS", raising=False)
    monkeypatch.setattr(cryovant.journal, "read_entries", lambda limit=200: [])
    monkeypatch.setattr(cryovant.journal, "write_entry", mock_write)
    monkeypatch.setattr(cryovant.metrics, "log", mock_log)

    assert cryovant.validate_ancestry("agent.alpha") is False

    mock_write.assert_called_once_with(
        agent_id="agent.alpha",
        action="ancestry_failed",
        payload={"reason": "empty_journal_denied"},
    )
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["event_type"] == "cryovant_empty_journal_denied"


def test_validate_ancestry_allows_genesis_override(monkeypatch):
    mock_log = Mock()
    mock_write = Mock()

    monkeypatch.setenv("ADAAD_ALLOW_GENESIS", "1")
    monkeypatch.setattr(cryovant.journal, "read_entries", lambda limit=200: [])
    monkeypatch.setattr(cryovant.journal, "write_entry", mock_write)
    monkeypatch.setattr(cryovant.metrics, "log", mock_log)

    assert cryovant.validate_ancestry("agent.alpha") is True

    mock_write.assert_called_once_with(
        agent_id="agent.alpha",
        action="ancestry_validated",
        payload={"reason": "genesis_override_allowed"},
    )
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["event_type"] == "cryovant_genesis_override_allowed"

def test_validate_ancestry_unknown_ancestry_reason(monkeypatch):
    mock_log = Mock()
    mock_write = Mock()

    monkeypatch.setattr(cryovant.journal, "read_entries", lambda limit=200: [{"agent_id": "agent.known"}])
    monkeypatch.setattr(cryovant.journal, "write_entry", mock_write)
    monkeypatch.setattr(cryovant.metrics, "log", mock_log)

    assert cryovant.validate_ancestry("agent.unknown") is False

    mock_write.assert_called_once()
    assert mock_write.call_args.kwargs["payload"]["reason"] == "unknown_ancestry"
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["event_type"] == "cryovant_unknown_ancestry"
    assert mock_log.call_args.kwargs["payload"]["reason"] == "unknown_ancestry"
