# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
from pathlib import Path

from app.main import Orchestrator


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_check_key_rotation_status_attestation_first(monkeypatch, tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    _write(
        keys_dir / "rotation.json",
        {
            "interval_seconds": 3600,
            "last_rotation_ts": 1700000000,
            "last_rotation_iso": "2024-01-01T00:00:00Z",
        },
    )
    (keys_dir / "private.pem").write_text("stale", encoding="utf-8")

    monkeypatch.setattr("app.main.cryovant.KEYS_DIR", keys_dir)

    ok, reason = Orchestrator._check_key_rotation_status(object())

    assert ok is True
    assert reason == "attestation_ok"


def test_check_key_rotation_status_attestation_invalid_blocks_fallback(monkeypatch, tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    _write(keys_dir / "rotation.json", {"interval_seconds": 3600})
    (keys_dir / "private.pem").write_text("fresh", encoding="utf-8")

    monkeypatch.setattr("app.main.cryovant.KEYS_DIR", keys_dir)

    ok, reason = Orchestrator._check_key_rotation_status(object())

    assert ok is False
    assert reason == "rotation_attestation_invalid:missing_required:attestation_hash,next_rotation_due,policy_days,previous_rotation_date,rotation_date"


def test_check_key_rotation_status_uses_dev_signature_mode_when_no_keys(monkeypatch, tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("app.main.cryovant.KEYS_DIR", keys_dir)
    monkeypatch.setattr("app.main.cryovant.dev_signature_allowed", lambda _: True)

    ok, reason = Orchestrator._check_key_rotation_status(object())

    assert ok is True
    assert reason == "dev_signature_mode"
