# SPDX-License-Identifier: Apache-2.0
"""Governed ADAAD trigger orchestration with simulation-mode safeguards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
        return {"status": "validated", "simulated": True, "event_type": str(event["event_type"]) }


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
            },
        }
        profile = scenario_map.get(scenario, scenario_map["merge_ready"])

        gate_names = ("tier_0", "tier_1", "tier_3")
        gate_results = self._evaluate_gates(gate_names)
        by_name = {result.gate: result for result in gate_results}
        scenario_pass = all(bool(profile.get(name, True)) for name in gate_names)
        gate_pass = all(by_name.get(name, GateResult("", "", True, "")).passed for name in gate_names)
        blocked_reason = profile.get("blocked_reason") if scenario != "merge_ready" else None

        ledger_response = self._ledger.write_event(
            {
                "event_type": "adaad_orchestration_attempt.v1",
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "payload": {
                    "trigger": request.principal,
                    "action": request.action,
                    "simulation": request.simulation,
                    "scenario": scenario,
                },
            }
        )

        stage_result = self._git.stage(simulation=request.simulation)
        merge_result = self._git.merge(simulation=request.simulation)

        status = "blocked" if blocked_reason or not scenario_pass or not gate_pass else "ready"
        output_lines = [
            "[ADAAD ORIENT]",
            f"Trigger: {request.principal}",
            f"Action: {request.action}",
            f"simulation=true" if request.simulation else "simulation=false",
            f"Scenario: {scenario}",
            f"Status: {status}",
        ]

        for name in gate_names:
            line_status = "PASS" if bool(profile.get(name, True)) and by_name.get(name, GateResult("", "", True, "")).passed else "FAIL"
            output_lines.append(f"{name}: {line_status} (simulation={'true' if request.simulation else 'false'})")

        if blocked_reason:
            output_lines.append(f"Blocked reason: {blocked_reason}")

        return {
            "request": request,
            "status": status,
            "simulation": request.simulation,
            "scenario": scenario,
            "blocked_reason": blocked_reason,
            "gate_results": [result.__dict__ for result in gate_results],
            "stage_result": stage_result,
            "merge_result": merge_result,
            "ledger": ledger_response,
            "output": "\n".join(output_lines),
        }


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
