# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from runtime.api.orchestration import StatusEnvelope
from runtime.boot.artifact_verifier import verify_required_artifacts
from runtime.invariants import verify_all
from runtime.preflight import validate_boot_runtime_profile, validate_constitution_version_config
from security import cryovant
from security.gatekeeper_protocol import run_gatekeeper


class BootPreflightService:
    """Evaluates boot prerequisites through explicit typed envelopes."""


    def validate_constitution_version(self) -> StatusEnvelope:
        constitution = validate_constitution_version_config()
        if not constitution.get("ok"):
            return StatusEnvelope(
                status="error",
                reason=constitution.get("reason", "constitution_version_validation_failed"),
                evidence_refs=("runtime.preflight.validate_constitution_version_config",),
                payload=constitution,
            )
        return StatusEnvelope(
            status="ok",
            evidence_refs=("runtime.preflight.validate_constitution_version_config",),
            payload=constitution,
        )

    def validate_gatekeeper(self) -> StatusEnvelope:
        gate = run_gatekeeper()
        if not gate.get("ok"):
            missing = ",".join(gate.get("missing", []))
            return StatusEnvelope(
                status="error",
                reason=f"gatekeeper_failed:{missing}",
                evidence_refs=("security.gatekeeper_protocol",),
                payload=gate,
            )
        return StatusEnvelope(status="ok", evidence_refs=("security.gatekeeper_protocol",), payload=gate)

    def validate_runtime_profile(self, *, replay_mode: str) -> StatusEnvelope:
        boot_profile = validate_boot_runtime_profile(replay_mode=replay_mode)
        if not boot_profile.get("ok"):
            return StatusEnvelope(
                status="error",
                reason=f"boot_runtime_profile_failed:{boot_profile.get('reason', 'unknown')}",
                evidence_refs=("runtime.preflight.validate_boot_runtime_profile",),
                payload=boot_profile,
            )
        return StatusEnvelope(
            status="ok",
            evidence_refs=("runtime.preflight.validate_boot_runtime_profile",),
            payload=boot_profile,
        )

    def validate_invariants(self) -> StatusEnvelope:
        ok, failures = verify_all()
        if not ok:
            return StatusEnvelope(
                status="error",
                reason=f"invariants_failed:{','.join(failures)}",
                evidence_refs=("runtime.invariants.verify_all",),
                payload={"failures": failures},
            )
        return StatusEnvelope(status="ok", evidence_refs=("runtime.invariants.verify_all",), payload={})

    def validate_cryovant(self, agents_root: Path) -> StatusEnvelope:
        if not cryovant.validate_environment():
            return StatusEnvelope(
                status="error",
                reason="cryovant_environment",
                evidence_refs=("security.cryovant.validate_environment",),
                payload={},
            )
        repair = os.getenv("ADAAD_ENV") == "dev"
        certified, errors = cryovant.certify_agents(agents_root, repair=repair)
        if not certified:
            return StatusEnvelope(
                status="error",
                reason=f"cryovant_certification:{','.join(errors)}",
                evidence_refs=("security.cryovant.certify_agents",),
                payload={"errors": errors},
            )
        return StatusEnvelope(status="ok", evidence_refs=("security.cryovant.certify_agents",), payload={})

    def validate_signed_artifacts(self) -> StatusEnvelope:
        try:
            checks = verify_required_artifacts()
        except ValueError as exc:
            return StatusEnvelope(
                status="error",
                reason=f"critical_artifact_verification:{exc}",
                evidence_refs=("runtime.boot.artifact_verifier.verify_required_artifacts",),
                payload={},
            )
        return StatusEnvelope(
            status="ok",
            evidence_refs=("runtime.boot.artifact_verifier.verify_required_artifacts",),
            payload={"checks": checks},
        )


def evaluate_boot_invariants(*, replay_mode: str, agents_root: Path) -> StatusEnvelope:
    """Canonical boot-invariant entrypoint with stable machine-readable failure payloads."""

    service = BootPreflightService()
    checks: list[dict[str, str]] = []
    validators: tuple[tuple[str, str, Callable[[], StatusEnvelope]], ...] = (
        (
            "constitution_version",
            "boot_invariant_constitution_version_failed",
            service.validate_constitution_version,
        ),
        (
            "gatekeeper",
            "boot_invariant_gatekeeper_failed",
            service.validate_gatekeeper,
        ),
        (
            "runtime_profile",
            "boot_invariant_runtime_profile_failed",
            lambda: service.validate_runtime_profile(replay_mode=replay_mode),
        ),
        (
            "governance_invariants",
            "boot_invariant_governance_invariants_failed",
            service.validate_invariants,
        ),
        (
            "cryovant",
            "boot_invariant_cryovant_failed",
            lambda: service.validate_cryovant(agents_root),
        ),
        (
            "signed_artifacts",
            "boot_invariant_signed_artifacts_failed",
            service.validate_signed_artifacts,
        ),
    )

    for check_name, reason_code, validator in validators:
        envelope = validator()
        if not isinstance(envelope, StatusEnvelope) or envelope.status not in {"ok", "error"}:
            return StatusEnvelope(
                status="error",
                reason="boot_invariant_payload_malformed",
                evidence_refs=("runtime.boot.preflight.evaluate_boot_invariants",),
                payload={
                    "event_type": "boot_invariant_evaluation.v1",
                    "status": "error",
                    "reason_code": "boot_invariant_payload_malformed",
                    "failed_check": check_name,
                    "replay_mode": replay_mode,
                    "checks": checks,
                },
            )

        if envelope.status != "ok":
            return StatusEnvelope(
                status="error",
                reason=envelope.reason or reason_code,
                evidence_refs=("runtime.boot.preflight.evaluate_boot_invariants",) + envelope.evidence_refs,
                payload={
                    "event_type": "boot_invariant_evaluation.v1",
                    "status": "error",
                    "reason_code": reason_code,
                    "failed_check": check_name,
                    "failed_reason": envelope.reason,
                    "replay_mode": replay_mode,
                    "checks": checks,
                    "check_payload": envelope.payload,
                },
            )

        checks.append({"check": check_name, "status": "ok"})

    return StatusEnvelope(
        status="ok",
        reason="ok",
        evidence_refs=("runtime.boot.preflight.evaluate_boot_invariants",),
        payload={
            "event_type": "boot_invariant_evaluation.v1",
            "status": "ok",
            "reason_code": "ok",
            "replay_mode": replay_mode,
            "checks": checks,
        },
    )
