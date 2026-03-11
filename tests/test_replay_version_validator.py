# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
from unittest import mock

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.replay import ReplayEngine, ReplayVersionValidator


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def test_replay_engine_version_validate_delegates_strict_mode() -> None:
    engine = ReplayEngine()
    payload = {
        "scoring_algorithm_version": "v1",
        "governor_version": "3",
    }

    with mock.patch.object(ReplayVersionValidator, "validate", return_value={"mode": "strict", "ok": True, "decision": "allow", "details": {}}) as patched:
        report = engine.version_validate(payload, mode="strict")

    patched.assert_called_once_with(payload, mode="strict")
    assert report == {"mode": "strict", "ok": True, "decision": "allow", "details": {}}


def test_replay_engine_version_validate_structural_contract_and_determinism() -> None:
    engine = ReplayEngine()
    payload = {
        "scoring_algorithm_version": "v1",
        "governor_version": "3",
    }

    report = engine.version_validate(payload, mode="strict")
    report_2 = engine.version_validate(payload, mode="strict")

    assert report["mode"] == "strict"
    assert {"mode", "ok", "decision", "details"}.issubset(set(report.keys()))
    assert report["mode"] != "audit"
    assert report == report_2
    assert _hash(report) == _hash(report_2)


def test_replay_engine_version_validate_audit_mode_allows_divergence() -> None:
    engine = ReplayEngine()
    payload = {
        "scoring_algorithm_version": "v1",
        "governor_version": "3",
        "replay_scoring_algorithm_version": "v2",
    }

    report = engine.version_validate(payload, mode="audit")

    assert report["mode"] == "audit"
    assert report["ok"] is True
    assert report["decision"] in {"allow", "allow_with_divergence"}


def test_replay_engine_version_validate_missing_field_fails_closed() -> None:
    engine = ReplayEngine()
    payload = {
        "scoring_algorithm_version": "v1",
    }

    report = engine.version_validate(payload, mode="strict")

    assert report["ok"] is False
    assert report["decision"] == "reject"
    assert "governor_version" in report["details"]["missing_required"]


def test_replay_engine_version_validate_invalid_mode_raises() -> None:
    engine = ReplayEngine()

    with pytest.raises(ValueError):
        engine.version_validate({"scoring_algorithm_version": "v1", "governor_version": "3"}, mode="invalid_mode")
