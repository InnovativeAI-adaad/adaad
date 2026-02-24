# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest import mock

import json
import urllib.error

from runtime.governance.foundation import SeededDeterminismProvider
from runtime.integrations.aponi_sync import push_to_dashboard


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_error_logs_append(tmp_path: Path) -> None:
    log_path = tmp_path / "aponi.log"
    with mock.patch("runtime.integrations.aponi_sync.ERROR_LOG", log_path):
        def boom(*_args, **_kwargs):
            raise urllib.error.URLError("fail")

        with mock.patch("urllib.request.urlopen", side_effect=boom):
            assert push_to_dashboard("TEST_EVENT", {"a": 1}) is False
            assert push_to_dashboard("TEST_EVENT", {"a": 2}) is False

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_transport_failures_emit_reason_code_without_secret(tmp_path: Path) -> None:
    log_path = tmp_path / "aponi.log"
    with mock.patch("runtime.integrations.aponi_sync.ERROR_LOG", log_path):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("token=abc123")):
            assert push_to_dashboard("TEST_EVENT", {"secret": "do-not-leak"}) is False

    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["reason_code"] == "aponi_transport_failed"
    assert entry["error_type"] == "URLError"
    assert entry["payload"]["secret"] == "do-not-leak"


def test_push_uses_injected_provider_timestamp_deterministically() -> None:
    provider = SeededDeterminismProvider(seed="seed", fixed_now=None)
    captured: dict[str, object] = {}

    def _ok(req, *_args, **_kwargs):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _Response(status=204)

    with mock.patch("urllib.request.urlopen", side_effect=_ok):
        assert push_to_dashboard("TEST_EVENT", {"a": 1}, provider=provider) is True

    sent = captured["payload"]
    assert isinstance(sent, dict)
    assert sent["ts"] == provider.iso_now()
    assert sent["type"] == "TEST_EVENT"
    assert sent["payload"] == {"a": 1}


def test_success_and_error_entries_share_timestamp_format(tmp_path: Path) -> None:
    provider = SeededDeterminismProvider(seed="seed")
    log_path = tmp_path / "aponi.log"
    captured: dict[str, object] = {}

    def _ok(req, *_args, **_kwargs):
        captured["success"] = json.loads(req.data.decode("utf-8"))
        return _Response(status=200)

    with mock.patch("runtime.integrations.aponi_sync.ERROR_LOG", log_path):
        with mock.patch("urllib.request.urlopen", side_effect=_ok):
            assert push_to_dashboard("TEST_EVENT", {"ok": True}, provider=provider) is True

        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
            assert push_to_dashboard("TEST_EVENT", {"ok": False}, provider=provider) is False

    error_entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    success_entry = captured["success"]
    assert isinstance(success_entry, dict)
    assert success_entry["ts"] == error_entry["ts"]
    assert success_entry["ts"].endswith("Z")


def test_seeded_provider_timestamp_is_reused_for_success_and_error(tmp_path: Path) -> None:
    provider = SeededDeterminismProvider(seed="stable-seed")
    expected_ts = provider.iso_now()
    log_path = tmp_path / "aponi.log"
    captured: dict[str, object] = {}

    def _ok(req, *_args, **_kwargs):
        captured["success"] = json.loads(req.data.decode("utf-8"))
        return _Response(status=202)

    with mock.patch("runtime.integrations.aponi_sync.ERROR_LOG", log_path):
        with mock.patch("urllib.request.urlopen", side_effect=_ok):
            assert push_to_dashboard("TEST_EVENT", {"ok": True}, provider=provider) is True

        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
            assert push_to_dashboard("TEST_EVENT", {"ok": False}, provider=provider) is False

    success_entry = captured["success"]
    assert isinstance(success_entry, dict)
    assert success_entry["ts"] == expected_ts

    error_entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert error_entry["ts"] == expected_ts


def test_transport_failure_handling_is_unchanged(tmp_path: Path) -> None:
    log_path = tmp_path / "aponi.log"
    with mock.patch("runtime.integrations.aponi_sync.ERROR_LOG", log_path):
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("slow upstream")):
            assert push_to_dashboard("TEST_EVENT", {"a": 1}) is False

    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["reason_code"] == "aponi_transport_failed"
    assert entry["error_type"] == "TimeoutError"
    assert entry["payload"] == {"a": 1}
