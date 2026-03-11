import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from runtime.api.orchestration import StatusEnvelope
from runtime.boot.preflight import BootPreflightService, evaluate_boot_invariants


def test_boot_preflight_signed_artifacts_ok(monkeypatch) -> None:
    monkeypatch.setattr("runtime.boot.preflight.verify_required_artifacts", lambda: {"governance_policy": "sha256:abc"})
    result = BootPreflightService().validate_signed_artifacts()
    assert result.status == "ok"


def test_boot_preflight_signed_artifacts_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.boot.preflight.verify_required_artifacts",
        lambda: (_ for _ in ()).throw(ValueError("governance_policy:invalid_signature")),
    )
    result = BootPreflightService().validate_signed_artifacts()
    assert result.status == "error"
    assert result.reason.startswith("critical_artifact_verification:")


def test_evaluate_boot_invariants_missing_required_invariant_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(BootPreflightService, "validate_gatekeeper", lambda self: StatusEnvelope(status="ok"))
    monkeypatch.setattr(BootPreflightService, "validate_runtime_profile", lambda self, replay_mode: StatusEnvelope(status="ok"))
    monkeypatch.setattr(
        BootPreflightService,
        "validate_invariants",
        lambda self: StatusEnvelope(status="error", reason="invariants_failed:missing_required_invariant"),
    )

    result = evaluate_boot_invariants(replay_mode="strict", agents_root=Path("app/agents"))

    assert result.status == "error"
    assert result.payload["event_type"] == "boot_invariant_evaluation.v1"
    assert result.payload["reason_code"] == "boot_invariant_governance_invariants_failed"
    assert result.payload["failed_check"] == "governance_invariants"
    assert result.payload["failed_reason"] == "invariants_failed:missing_required_invariant"


def test_evaluate_boot_invariants_malformed_envelope_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(BootPreflightService, "validate_gatekeeper", lambda self: {"status": "ok"})

    result = evaluate_boot_invariants(replay_mode="audit", agents_root=Path("app/agents"))

    assert result.status == "error"
    assert result.reason == "boot_invariant_payload_malformed"
    assert result.payload == {
        "event_type": "boot_invariant_evaluation.v1",
        "status": "error",
        "reason_code": "boot_invariant_payload_malformed",
        "failed_check": "gatekeeper",
        "replay_mode": "audit",
        "checks": [{"check": "constitution_version", "status": "ok"}],
    }
