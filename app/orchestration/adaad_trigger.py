# SPDX-License-Identifier: Apache-2.0
"""Governed ADAAD trigger orchestration with verified-SHA merge safeguards."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping, Sequence

from runtime.api.governance_events import (
    build_merge_attestation_event,
    build_merge_attestation_payload,
)


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


class AttestationWriteError(RuntimeError):
    """Raised when merge attestation emission fails closed."""


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

    def merge(
        self,
        *,
        simulation: bool,
        verified_sha: str,
        merge_target_sha: str,
    ) -> dict[str, Any]:
        if simulation:
            return {"status": "skipped", "simulation": True, "operation": "git_merge"}
        normalized_verified_sha = self._resolve_commit(verified_sha)
        normalized_merge_target_sha = self._resolve_commit(merge_target_sha)
        if normalized_verified_sha != normalized_merge_target_sha:
            raise ValueError("merge_target_mismatch_verified_sha")

        pre_merge_head_sha = self._git_stdout("git", "rev-parse", "HEAD")
        subprocess.run(
            ["git", "merge", "--no-ff", "--no-edit", normalized_merge_target_sha],
            cwd=self.repo_root,
            check=True,
        )
        merge_commit_sha = self._git_stdout("git", "rev-parse", "HEAD")
        return {
            "status": "executed",
            "simulation": False,
            "operation": "git_merge",
            "verified_sha": normalized_verified_sha,
            "merge_target_sha": normalized_merge_target_sha,
            "pre_merge_head_sha": pre_merge_head_sha,
            "merge_commit_sha": merge_commit_sha,
        }

    def _resolve_commit(self, revision: str) -> str:
        normalized_revision = str(revision).strip()
        if not normalized_revision:
            raise ValueError("missing_revision")
        return self._git_stdout("git", "rev-parse", "--verify", normalized_revision).lower()

    def _git_stdout(self, *args: str) -> str:
        completed = subprocess.run(
            list(args),
            cwd=self.repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()


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

    def run(
        self,
        raw_command: str,
        *,
        scenario: str = "merge_ready",
        replay_verification: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
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
                "merge_context": {
                    "pr_number": 65,
                    "pr_id": "PR-PHASE65-01",
                    "merge_sha": "c" * 40,
                    "tier_0_digest": "sha256:" + ("d" * 64),
                    "tier_1_tests_passed": 412,
                    "tier_1_tests_failed": 0,
                    "tier_2_replay_digest": "sha256:" + ("e" * 64),
                    "tier_3_evidence_complete": True,
                    "tier_m_working_code": True,
                    "operator_session": "devadaad-session-0001",
                    "human_signoff_token": None,
                },
                "replay_verification": {
                    "manifest_path": "security/replay_manifests/verified-sha.replay_manifest.v1.json",
                    "bundle_digest": "sha256:" + ("a" * 64),
                    "verification_result": "pass",
                    "verified_sha": "c" * 40,
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
                "merge_context": {
                    "pr_number": 65,
                    "pr_id": "PR-PHASE65-01",
                    "merge_sha": "f" * 40,
                    "tier_0_digest": "sha256:" + ("1" * 64),
                    "tier_1_tests_passed": 410,
                    "tier_1_tests_failed": 2,
                    "tier_2_replay_digest": "sha256:" + ("b" * 64),
                    "tier_3_evidence_complete": True,
                    "tier_m_working_code": False,
                    "operator_session": "devadaad-session-0002",
                    "human_signoff_token": None,
                },
                "replay_verification": {
                    "manifest_path": "security/replay_manifests/verified-sha.replay_manifest.v1.json",
                    "bundle_digest": "sha256:" + ("b" * 64),
                    "verification_result": "fail",
                    "verified_sha": "f" * 40,
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
        gate_pass = all(by_name.get(name, GateResult("", "", True, "")).passed for name in gate_names)
        replay_verification = dict(replay_verification or profile.get("replay_verification") or {})
        verified_sha = str(replay_verification.get("verified_sha", "")).strip().lower()
        merge_target_sha = str(replay_verification.get("merge_target_sha", "")).strip().lower()
        merge_target_matches_verified_sha = bool(verified_sha) and verified_sha == merge_target_sha
        replay_gate_pass = self._replay_merge_gate_passes(request=request, replay_verification=replay_verification)
        blocked_reason = profile.get("blocked_reason") if scenario != "merge_ready" else None
        if request.merge_authority and not replay_gate_pass and not blocked_reason:
            blocked_reason = "missing_merge_sha_verification"

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
                "verified_sha": verified_sha,
                "merge_target_sha": merge_target_sha,
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

        stage_result = self._git.stage(simulation=request.simulation)
        status = "blocked" if blocked_reason or not scenario_pass or not gate_pass or not replay_gate_pass else "ready"
        merge_result = {"status": "skipped", "simulation": request.simulation, "operation": "git_merge"}
        attestation_result: dict[str, Any] | None = None
        attestation_attempted = False

        if request.merge_authority and status == "ready":
            attestation_attempted = True
            try:
                attestation_result = self._write_merge_attestation(
                    request=request,
                    profile=profile,
                    replay_verification=replay_verification,
                )
            except Exception as exc:
                blocked_reason = "attestation_write_failed"
                status = "blocked"
                merge_result = {
                    "status": "blocked",
                    "simulation": request.simulation,
                    "operation": "git_merge",
                    "detail": str(exc),
                }
            else:
                merge_result = self._git.merge(simulation=request.simulation)
        elif not request.merge_authority:
            merge_result = self._git.merge(simulation=request.simulation)

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
            attestation_status = "PASS" if attestation_result else "FAIL" if attestation_attempted else "SKIP"
            output_lines.append(f"merge_attestation: {attestation_status}")

        if decision["blocked_reason"]:
            output_lines.append(f"Blocked reason: {decision['blocked_reason']}")

        return {
            "request": request,
            "status": decision["status"],
            "simulation": request.simulation,
            "scenario": scenario,
            "blocked_reason": blocked_reason,
            "verified_sha": verified_sha,
            "merge_target_sha": merge_target_sha,
            "merge_target_matches_verified_sha": merge_target_matches_verified_sha,
            "replay_verification": replay_verification,
            "replay_gate_pass": replay_gate_pass,
            "gate_results": [asdict(result) for result in gate_results],
            "decision": decision,
            "stage_result": stage_result,
            "merge_result": merge_result,
            "merge_attestation": attestation_result,
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
        required_str_fields = ("manifest_path", "bundle_digest", "verification_result", "verified_sha", "merge_target_sha")
        for field in required_str_fields:
            if not str(replay_verification.get(field, "")).strip():
                return False
        if str(replay_verification.get("verified_sha", "")).strip().lower() != str(
            replay_verification.get("merge_target_sha", "")
        ).strip().lower():
            return False
        if not bool(replay_verification.get("schema_valid", False)):
            return False
        if not bool(replay_verification.get("signature_valid", False)):
            return False
        if bool(replay_verification.get("divergence", False)):
            return False
        verification_result = str(replay_verification.get("verification_result", "")).strip().lower()
        return verification_result in {"pass", "verified", "ok"}

    def _write_merge_attestation(
        self,
        *,
        request: TriggerRequest,
        profile: Mapping[str, Any],
        replay_verification: Mapping[str, Any],
    ) -> dict[str, Any]:
        merge_context = dict(profile.get("merge_context") or {})
        if not merge_context:
            raise AttestationWriteError("merge_attestation_context_missing")

        timestamp_utc = datetime.now(timezone.utc).isoformat()
        payload = build_merge_attestation_payload(
            pr_id=str(merge_context.get("pr_id", "")).strip(),
            merge_sha=str(merge_context.get("merge_sha", "")).strip(),
            tier_0_digest=str(merge_context.get("tier_0_digest", "")).strip(),
            tier_1_tests_passed=int(merge_context.get("tier_1_tests_passed", 0)),
            tier_1_tests_failed=int(merge_context.get("tier_1_tests_failed", 0)),
            tier_2_replay_digest=str(merge_context["tier_2_replay_digest"]).strip()
            if merge_context.get("tier_2_replay_digest") is not None
            else None,
            tier_3_evidence_complete=bool(merge_context.get("tier_3_evidence_complete", False)),
            tier_m_working_code=bool(merge_context.get("tier_m_working_code", False)),
            triggered_by=request.principal,
            operator_session=str(merge_context.get("operator_session", "")).strip(),
            timestamp_utc=timestamp_utc,
            human_signoff_token=merge_context.get("human_signoff_token"),
        )
        event = build_merge_attestation_event(
            pr_number=int(merge_context.get("pr_number", 0)),
            merge_sha=payload["merge_sha"],
            payload=payload,
            sequence=1,
        )
        try:
            ledger_response = self._ledger.write_event(
                {
                    "event_type": event["event_type"],
                    "timestamp_utc": timestamp_utc,
                    "payload": event,
                }
            )
        except Exception as exc:
            raise AttestationWriteError(str(exc)) from exc
        return {
            "status": "validated",
            "ledger": ledger_response,
            "event": event,
            "replay_verified_sha": str(replay_verification.get("verified_sha", "")).strip().lower(),
        }


def run_trigger(
    raw_command: str,
    *,
    repo_root: Path,
    scenario: str = "merge_ready",
    replay_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    orchestrator = AdaadTriggerOrchestrator(repo_root=repo_root)
    return orchestrator.run(raw_command, scenario=scenario, replay_verification=replay_verification)


__all__ = [
    "AdaadTriggerOrchestrator",
    "AttestationWriteError",
    "GateResult",
    "GitMutationAdapter",
    "LedgerSchemaError",
    "TriggerRequest",
    "VirtualLedgerWriter",
    "parse_trigger",
    "run_trigger",
]
