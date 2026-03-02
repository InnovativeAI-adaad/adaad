# SPDX-License-Identifier: Apache-2.0

from runtime.boot.preflight import BootPreflightService


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

