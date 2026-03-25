# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import asyncio
import pytest
pytestmark = pytest.mark.regression_standard

from fastapi.testclient import TestClient

import server


def test_ws_events_handshake_frame() -> None:
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/events") as websocket:
            frame = websocket.receive_json()

    assert frame["type"] == "hello"
    assert frame["channels"] == ["metrics", "journal", "innovations"]
    assert frame["status"] == "live"
    assert frame["endpoint_meta"]["history_caps"]["metrics_limit_max"] == 500
    assert frame["endpoint_meta"]["history_caps"]["journal_limit_max"] == 500
    assert frame["endpoint_meta"]["queue_policy"] == "drop_oldest"


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


def test_ws_events_honors_history_limits(monkeypatch) -> None:
    observed_limits = {"metrics": None, "journal": None}

    def _tail(limit=200):
        observed_limits["metrics"] = limit
        return []

    def _read_entries(limit=200):
        observed_limits["journal"] = limit
        return []

    monkeypatch.setattr(server.metrics, "tail", _tail)
    monkeypatch.setattr(server.journal, "read_entries", _read_entries)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/events?metrics_limit=7&journal_limit=9") as websocket:
            websocket.receive_json()
            websocket.receive_json()

    assert observed_limits["metrics"] == 7
    assert observed_limits["journal"] == 9


def test_ws_events_burst_frames_drop_oldest_and_emit_metrics(monkeypatch) -> None:
    class FakeBus:
        def __init__(self) -> None:
            self.unsubscribed = 0

        async def subscribe(self):
            self.queue: asyncio.Queue = asyncio.Queue()
            for i in range(8):
                self.queue.put_nowait({"type": "cel_step", "seq": i, "ts": f"2026-01-01T00:00:0{i}Z"})
            return self.queue

        async def unsubscribe(self, _q):
            self.unsubscribed += 1

    bus = FakeBus()
    metrics_events: list[tuple[str, dict]] = []
    monkeypatch.setattr(server.metrics, "tail", lambda limit=200: [])
    monkeypatch.setattr(server.journal, "read_entries", lambda limit=200: [])
    monkeypatch.setattr(server.metrics, "log", lambda event_type, payload=None, level="INFO", element_id=None: metrics_events.append((event_type, payload or {})))
    monkeypatch.setattr("runtime.innovations_bus.get_bus", lambda: bus)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/events?relay_queue_limit=2&heartbeat_interval_s=1&stale_timeout_s=30") as websocket:
            websocket.receive_json()
            websocket.receive_json()
            websocket.send_json({"type": "pong"})
            websocket.receive_json()

    assert bus.unsubscribed == 1
    assert any(event == "ws_events_frames_dropped" for event, _ in metrics_events)


def test_ws_events_stale_client_timeout_disconnect_reason(monkeypatch) -> None:
    class FakeBus:
        def __init__(self) -> None:
            self.queue: asyncio.Queue = asyncio.Queue()

        async def subscribe(self):
            return self.queue

        async def unsubscribe(self, _q):
            return None

    bus = FakeBus()
    disconnect_payloads: list[dict] = []
    monkeypatch.setattr(server.metrics, "tail", lambda limit=200: [])
    monkeypatch.setattr(server.journal, "read_entries", lambda limit=200: [])
    monkeypatch.setattr(server.metrics, "log", lambda event_type, payload=None, level="INFO", element_id=None: disconnect_payloads.append(payload or {}) if event_type == "ws_events_disconnect" else None)
    monkeypatch.setattr("runtime.innovations_bus.get_bus", lambda: bus)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/events?heartbeat_interval_s=1&stale_timeout_s=2") as websocket:
            websocket.receive_json()
            websocket.receive_json()
            final_frame = {}
            for _ in range(6):
                final_frame = websocket.receive_json()
                if final_frame.get("type") == "disconnect":
                    break

    assert disconnect_payloads
    assert final_frame.get("type") == "disconnect"
    assert final_frame.get("reason") == "stale_client_timeout"
    assert disconnect_payloads[-1]["cause"] == "stale_client_timeout"
