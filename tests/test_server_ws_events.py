# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from fastapi.testclient import TestClient

import server


def test_ws_events_handshake_frame() -> None:
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/events") as websocket:
            frame = websocket.receive_json()

    assert frame == {"type": "hello", "channels": ["metrics", "journal"], "status": "live"}


def test_ws_events_message_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        server.metrics,
        "tail",
        lambda limit=200: [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "event": "governance_decision_recorded",
                "level": "INFO",
                "payload": {"decision_id": "d-1"},
            }
        ],
    )
    monkeypatch.setattr(
        server.journal,
        "read_entries",
        lambda limit=200: [
            {
                "timestamp": "2026-01-01T00:00:01Z",
                "agent_id": "system",
                "action": "mutation_applied",
                "payload": {"mutation_id": "m-1"},
            }
        ],
    )

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/events") as websocket:
            websocket.receive_json()  # hello frame
            frame = websocket.receive_json()

    assert frame["type"] == "event_batch"
    assert isinstance(frame["events"], list)
    assert len(frame["events"]) == 2
    channels = {event["channel"] for event in frame["events"]}
    assert channels == {"metrics", "journal"}
    for event in frame["events"]:
        assert set(event.keys()) == {"channel", "kind", "timestamp", "event"}
        assert isinstance(event["event"], dict)
