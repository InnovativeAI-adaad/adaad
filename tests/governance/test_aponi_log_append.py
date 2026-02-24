# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest import mock

import json
import urllib.error

from runtime.integrations.aponi_sync import push_to_dashboard


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
