from __future__ import annotations

from pathlib import Path

from app.orchestration.contracts import StatusEnvelope
from runtime.invariants import verify_all
from runtime.preflight import validate_boot_runtime_profile
from security import cryovant
from security.gatekeeper_protocol import run_gatekeeper


class BootPreflightService:
    """Evaluates boot prerequisites through explicit typed envelopes."""

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
        certified, errors = cryovant.certify_agents(agents_root)
        if not certified:
            return StatusEnvelope(
                status="error",
                reason=f"cryovant_certification:{','.join(errors)}",
                evidence_refs=("security.cryovant.certify_agents",),
                payload={"errors": errors},
            )
        return StatusEnvelope(status="ok", evidence_refs=("security.cryovant.certify_agents",), payload={})
