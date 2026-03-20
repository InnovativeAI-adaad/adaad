# SPDX-License-Identifier: Apache-2.0
"""Governed ADAAD trigger orchestration with simulation-mode safeguards."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class GateResult:
    tier: str
    gate: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class TriggerRequest:
    raw_command: str
    principal: str
    action: str
    simulation: bool
    merge_authority: bool


def parse_trigger(raw_command: str) -> TriggerRequest:
    tokens = [token for token in raw_command.strip().split() if token]
    if not tokens:
        raise ValueError("trigger_missing")

    principal = tokens[0].upper()
    if principal not in {"ADAAD", "DEVADAAD"}:
        raise ValueError("unsupported_trigger")

    action = tokens[1].lower() if len(tokens) > 1 else "run"
    simulation = action == "simulate"
    return TriggerRequest(
        raw_command=raw_command,
        principal=principal,
        action=action,
        simulation=simulation,
        merge_authority=principal == "DEVADAAD",
    )


class LedgerSchemaError(RuntimeError):
    """Raised when the simulated ledger payload is malformed."""


class VirtualLedgerWriter:
    """Validates and records ledger events without mutating real ledgers."""

    required_keys: tuple[str, ...] = ("event_type", "timestamp_utc", "payload")

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def write_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        missing = [key for key in self.required_keys if key not in event]
        if missing:
            raise LedgerSchemaError(f"ledger_schema_missing:{','.join(missing)}")

        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise LedgerSchemaError("ledger_schema_invalid:payload_not_object")

        persisted = dict(event)
        persisted["simulated"] = True
        self.events.append(persisted)
        return {"status": "validated", "simulated": True, "event_type": str(event["event_type"])}


class GitMutationAdapter:
    """Executes mutating git operations unless simulation mode is enabled."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def stage(self, *, simulation: bool) -> dict[str, Any]:
        if simulation:
            return {"status": "skipped", "simulation": True, "operation": "git_add"}
        subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        return {"status": "executed", "simulation": False, "operation": "git_add"}

    def merge(self, *, simulation: bool) -> dict[str, Any]:
        if simulation:
            return {"status": "skipped", "simulation": True, "operation": "git_merge"}
        return {"status": "noop", "simulation": False, "operation": "git_merge"}


class AdaadTriggerOrchestrator:
    """Runs Tier gates and governance orchestration for ADAAD/DEVADAAD triggers."""

    def __init__(
        self,
        *,
        repo_root: Path,
        gate_runner: Callable[[str], GateResult] | None = None,
        ledger_writer: VirtualLedgerWriter | None = None,
        git_mutation_adapter: GitMutationAdapter | None = None,
    ) -> None:
        self.repo_root = repo_root
        self._gate_runner = gate_runner or self._default_gate_runner
        self._ledger = ledger_writer or VirtualLedgerWriter()
        self._git = git_mutation_adapter or GitMutationAdapter(repo_root)

    @staticmethod
    def _default_gate_runner(gate_name: str) -> GateResult:
        return GateResult(tier="tier_1", gate=gate_name, passed=True, detail="simulated_pass")

    def _evaluate_gates(self, gate_names: Sequence[str]) -> list[GateResult]:
        return [self._gate_runner(gate_name) for gate_name in gate_names]

    def run(self, raw_command: str, *, scenario: str = "merge_ready") -> dict[str, Any]:
        request = parse_trigger(raw_command)
        scenario_map = {
            "dependency_blocked": {
                "blocked_reason": "dependency_unmerged",
                "tier_0": True,
                "tier_1": True,
            },
            "evidence_missing": {
                "blocked_reason": "evidence_row_missing",
                "tier_0": True,
                "tier_1": True,
                "tier_3": False,
            },
            "tier1_failure": {
                "blocked_reason": "tier_1_failed",
                "tier_0": True,
                "tier_1": False,
            },
            "merge_ready": {
                "blocked_reason": None,
                "tier_0": True,
                "tier_1": True,
                "tier_3": True,
                "tier_m": True,
                "replay_verification": {
                    "manifest_path": "security/replay_manifests/verified-sha.replay_manifest.v1.json",
                    "bundle_digest": "sha256:" + ("a" * 64),
                    "verification_result": "pass",
                    "verified_sha": "sha-verified-0001",
                    "schema_valid": True,
                    "signature_valid": True,
                    "divergence": False,
                },
            },
            "replay_diverged": {
                "blocked_reason": "replay_divergence_detected",
                "tier_0": True,
                "tier_1": True,
                "tier_3": True,
                "tier_m": False,
                "replay_verification": {
                    "manifest_path": "security/replay_manifests/verified-sha.replay_manifest.v1.json",
                    "bundle_digest": "sha256:" + ("b" * 64),
                    "verification_result": "fail",
                    "verified_sha": "sha-verified-0002",
                    "schema_valid": True,
                    "signature_valid": True,
                    "divergence": True,
                },
            },
        }
        profile = scenario_map.get(scenario, scenario_map["merge_ready"])

        gate_names: tuple[str, ...]
        if request.merge_authority:
            gate_names = ("tier_0", "tier_1", "tier_3", "tier_m")
        else:
            gate_names = ("tier_0", "tier_1", "tier_3")
        gate_results = self._evaluate_gates(gate_names)
        by_name = {result.gate: result for result in gate_results}
        scenario_pass = all(bool(profile.get(name, True)) for name in gate_names)
        gate_pass = all(by_name.get(name, GateResult("", name, True, "")).passed for name in gate_names)
        replay_verification = dict(profile.get("replay_verification") or {})
        replay_gate_pass = self._replay_merge_gate_passes(request=request, replay_verification=replay_verification)
        blocked_reason = profile.get("blocked_reason") if scenario != "merge_ready" else None
        if request.merge_authority and not replay_gate_pass and not blocked_reason:
            blocked_reason = "missing_replay_verification_for_verified_sha"

        decision = self._build_decision(
            request=request,
            gate_names=gate_names,
            profile=profile,
            by_name=by_name,
            blocked_reason=blocked_reason,
            scenario_pass=scenario_pass,
            gate_pass=gate_pass,
            replay_gate_pass=replay_gate_pass,
        )

        payload = {
            "trigger": request.principal,
            "action": request.action,
            "simulation": request.simulation,
            "scenario": scenario,
            "decision": {
                "status": decision["status"],
                "allow_git_mutations": decision["allow_git_mutations"],
                "mutated_repository_state": decision["mutated_repository_state"],
                "blocked_reason": decision["blocked_reason"],
            },
        }
        if replay_verification:
            payload["replay_bundle_metadata"] = {
                "manifest_path": str(replay_verification.get("manifest_path", "")).strip(),
                "bundle_digest": str(replay_verification.get("bundle_digest", "")).strip(),
                "verification_result": str(replay_verification.get("verification_result", "")).strip(),
                "verified_sha": str(replay_verification.get("verified_sha", "")).strip().lower(),
                "schema_valid": bool(replay_verification.get("schema_valid", False)),
                "signature_valid": bool(replay_verification.get("signature_valid", False)),
                "divergence": bool(replay_verification.get("divergence", False)),
            }

        ledger_response = self._ledger.write_event(
            {
                "event_type": "adaad_orchestration_attempt.v1",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
        )

        stage_result, merge_result = self._execute_git_mutations(request=request, decision=decision)

        output_lines = [
            "[ADAAD ORIENT]",
            f"Trigger: {request.principal}",
            f"Action: {request.action}",
            "simulation=true" if request.simulation else "simulation=false",
            f"Scenario: {scenario}",
            f"Status: {decision['status']}",
            f"Decision: {'allow' if decision['allow_git_mutations'] else 'deny'}",
            f"Repository mutation: {'mutated' if decision['mutated_repository_state'] else 'not_mutated'}",
        ]

        for name in gate_names:
            line_status = "PASS" if decision["evaluated_gates"][name]["passed"] else "FAIL"
            output_lines.append(f"{name}: {line_status} (simulation={'true' if request.simulation else 'false'})")
        if request.merge_authority:
            output_lines.append(f"replay_verified_sha_context: {'PASS' if replay_gate_pass else 'FAIL'}")

        if decision["blocked_reason"]:
            output_lines.append(f"Blocked reason: {decision['blocked_reason']}")

        return {
            "request": request,
            "status": decision["status"],
            "simulation": request.simulation,
            "scenario": scenario,
            "blocked_reason": decision["blocked_reason"],
            "replay_verification": replay_verification,
            "replay_gate_pass": replay_gate_pass,
            "gate_results": [asdict(result) for result in gate_results],
            "decision": decision,
            "stage_result": stage_result,
            "merge_result": merge_result,
            "ledger": ledger_response,
            "output": "\n".join(output_lines),
        }

    def _build_decision(
        self,
        *,
        request: TriggerRequest,
        gate_names: Sequence[str],
        profile: Mapping[str, Any],
        by_name: Mapping[str, GateResult],
        blocked_reason: str | None,
        scenario_pass: bool,
        gate_pass: bool,
        replay_gate_pass: bool,
    ) -> dict[str, Any]:
        evaluated_gates = {
            name: {
                "scenario_pass": bool(profile.get(name, True)),
                "gate_pass": by_name.get(name, GateResult("", name, True, "")).passed,
                "passed": bool(profile.get(name, True)) and by_name.get(name, GateResult("", name, True, "")).passed,
            }
            for name in gate_names
        }
        all_required_gates_passed = scenario_pass and gate_pass and replay_gate_pass
        allow_git_mutations = all_required_gates_passed and blocked_reason is None
        mutation_kind = "simulated" if request.simulation else ("mutated" if allow_git_mutations else "blocked")
        return {
            "status": "ready" if allow_git_mutations else "blocked",
            "blocked_reason": blocked_reason,
            "all_required_gates_passed": all_required_gates_passed,
            "allow_git_mutations": allow_git_mutations,
            "evaluated": True,
            "evaluated_gates": evaluated_gates,
            "mutation_kind": mutation_kind,
            "mutated_repository_state": allow_git_mutations and not request.simulation,
        }

    def _execute_git_mutations(self, *, request: TriggerRequest, decision: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        if not bool(decision.get("allow_git_mutations", False)):
            return (
                {"status": "skipped", "reason": "blocked", "simulation": request.simulation, "operation": "git_add"},
                {"status": "skipped", "reason": "blocked", "simulation": request.simulation, "operation": "git_merge"},
            )
        stage_result = self._git.stage(simulation=request.simulation)
        merge_result = self._git.merge(simulation=request.simulation)
        return stage_result, merge_result

    @staticmethod
    def _replay_merge_gate_passes(*, request: TriggerRequest, replay_verification: Mapping[str, Any]) -> bool:
        """Require replay verification output in merge authority flows."""
        if not request.merge_authority:
            return True
        required_str_fields = ("manifest_path", "bundle_digest", "verification_result", "verified_sha")
        for field in required_str_fields:
            if not str(replay_verification.get(field, "")).strip():
                return False
        if not bool(replay_verification.get("schema_valid", False)):
            return False
        if not bool(replay_verification.get("signature_valid", False)):
            return False
        if bool(replay_verification.get("divergence", False)):
            return False
        verification_result = str(replay_verification.get("verification_result", "")).strip().lower()
        return verification_result in {"pass", "verified", "ok"}


def run_trigger(raw_command: str, *, repo_root: Path, scenario: str = "merge_ready") -> dict[str, Any]:
    orchestrator = AdaadTriggerOrchestrator(repo_root=repo_root)
    return orchestrator.run(raw_command, scenario=scenario)


__all__ = [
    "AdaadTriggerOrchestrator",
    "GateResult",
    "GitMutationAdapter",
    "LedgerSchemaError",
    "TriggerRequest",
    "VirtualLedgerWriter",
    "parse_trigger",
    "run_trigger",
]
