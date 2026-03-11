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


def test_check_key_rotation_status_rejects_invalid_max_age_env(monkeypatch, tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    (keys_dir / "private.pem").write_text("fresh", encoding="utf-8")

    monkeypatch.setattr("app.main.cryovant.KEYS_DIR", keys_dir)
    monkeypatch.setenv("ADAAD_KEY_ROTATION_MAX_AGE_DAYS", "not-an-int")

    ok, reason = Orchestrator._check_key_rotation_status(object())

    assert ok is False
    assert reason == "invalid_key_rotation_max_age_days"


def test_governance_gate_consumes_invalid_key_rotation_max_age_reason(monkeypatch) -> None:
    orch = Orchestrator(replay_mode="off")
    monkeypatch.setattr(orch.evolution_runtime, "current_epoch_id", "epoch-test")

    monkeypatch.setattr(orch, "_check_constitution_version", lambda: (True, "ok"))
    monkeypatch.setattr(orch, "_check_key_rotation_status", lambda: (False, "invalid_key_rotation_max_age_days"))
    monkeypatch.setattr(orch, "_check_ledger_integrity", lambda: (True, "ok"))
    monkeypatch.setattr(orch, "_check_mutation_engine_health", lambda: (True, "ok"))
    monkeypatch.setattr(orch, "_check_warm_pool_ready", lambda: (True, "ok"))
    monkeypatch.setattr(orch, "_check_architect_invariants", lambda: (True, "ok"))
    monkeypatch.setattr(orch, "_check_platform_resources", lambda: (True, "ok"))
    monkeypatch.setattr(orch.tier_manager, "evaluate_escalation", lambda **_: orch.tier_manager.current_tier)
    monkeypatch.setattr(orch.tier_manager, "apply", lambda *_args, **_kwargs: None)

    assert orch._governance_gate() is False
    assert orch.state["mutation_enabled"] is False
    assert {
        "check": "key_rotation",
        "reason": "invalid_key_rotation_max_age_days",
    } in orch.state["governance_gate_failed"]
