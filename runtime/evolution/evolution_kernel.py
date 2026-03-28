# SPDX-License-Identifier: Apache-2.0
"""Deterministic orchestration kernel for mutation cycles."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from runtime.api.app_layer import push_to_dashboard
from runtime.api.agents import (
    MutationEngine,
    MutationRequest,
    adapt_generated_request_payload,
    iter_agent_dirs,
    load_skill_weights,
    select_strategy,
)
from runtime.api.mutation import MutationExecutor
from runtime import ROOT_DIR
from runtime import metrics
from runtime.evolution.change_classifier import apply_metadata_updates, classify_mutation_change
from runtime.evolution.mutation_fitness_evaluator import MutationFitnessEvaluator
from runtime.governance.policy_validator import PolicyValidator
from runtime.preflight import validate_mutation_proposal_schema
from security import cryovant


class EvolutionKernel:
    """Single entrypoint for mutation-cycle orchestration."""

    def __init__(
        self,
        *,
        agents_root: Path,
        lineage_dir: Path,
        compatibility_adapter: Any | None = None,
        mutation_executor: MutationExecutor | None = None,
    ) -> None:
        self.agents_root = Path(agents_root)
        self.lineage_dir = Path(lineage_dir)
        self.compatibility_adapter = compatibility_adapter
        self.mutation_executor = mutation_executor or MutationExecutor(self.agents_root)
        self.policy_validator = PolicyValidator()
        self.fitness_evaluator = MutationFitnessEvaluator()
        self.policy_path = ROOT_DIR / "governance" / "governance_policy_v1.json"

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def load_agent(self, agent_path: str | Path) -> Dict[str, Any]:
        """Load deterministic agent bundle from app/agents metadata files."""
        root = Path(agent_path)
        payload = {
            "agent_path": str(root),
            "meta": self._read_json(root / "meta.json"),
            "dna": self._read_json(root / "dna.json"),
            "certificate": self._read_json(root / "certificate.json"),
        }
        payload["agent_id"] = str(payload["meta"].get("name") or root.name)
        return payload

    def propose_mutation(self, agent: Mapping[str, Any]) -> Dict[str, Any]:
        """Select and score a mutation strategy deterministically."""
        agent_path = Path(str(agent.get("agent_path") or ""))
        state_path = ROOT_DIR / "data" / "mutation_engine_state.json"
        metrics_path = ROOT_DIR / "data" / "metrics.jsonl"

        skill_weights = load_skill_weights(state_path)
        intent, ops = select_strategy(agent_path, skill_weights=skill_weights)

        request = MutationRequest(
            agent_id=str(agent.get("agent_id") or agent_path.name),
            generation_ts="",
            intent=intent,
            ops=ops,
            signature="",
            nonce="",
        )
        engine = MutationEngine(metrics_path=metrics_path, state_path=state_path)
        selected_request, scores = engine.select([request])

        return {
            "request": (selected_request or request).to_dict(),
            "scores": scores,
            "selected_intent": (selected_request.intent if selected_request else intent),
        }

    def validate_mutation(self, policy: Mapping[str, Any] | str | None, mutation: Mapping[str, Any]) -> Dict[str, Any]:
        """Validate mutation against governance policy artifact and policy parser."""
        raw_policy: Dict[str, Any]
        if isinstance(policy, Mapping):
            raw_policy = dict(policy)
        elif isinstance(policy, str) and policy.strip():
            raw_policy = json.loads(policy)
        else:
            raw_policy = self._read_json(self.policy_path)

        validator_result = self.policy_validator.validate(json.dumps(raw_policy, sort_keys=True))
        mutation_has_ops = bool(mutation.get("ops") or mutation.get("targets"))
        return {
            "valid": validator_result.valid and mutation_has_ops,
            "policy_valid": validator_result.valid,
            "mutation_has_ops": mutation_has_ops,
            "errors": list(validator_result.errors),
            "policy_path": str(self.policy_path),
        }

    def execute_in_sandbox(self, agent: Mapping[str, Any], mutation: Mapping[str, Any]) -> Dict[str, Any]:
        """Execute mutation through current MutationExecutor sandbox workflow."""
        request_payload = mutation.get("request") if "request" in mutation else mutation
        adapted_payload = adapt_generated_request_payload(dict(request_payload))
        proposal_validation = validate_mutation_proposal_schema(adapted_payload)
        if not proposal_validation.get("ok"):
            return {
                "status": "rejected",
                "reason": proposal_validation.get("reason", "invalid_mutation_proposal_schema"),
                "errors": list(proposal_validation.get("errors") or []),
            }
        request = MutationRequest.from_dict(adapted_payload)
        if not request.agent_id:
            request.agent_id = str(agent.get("agent_id") or "")
        return self.mutation_executor.execute(request)

    def evaluate_fitness(
        self,
        agent: Mapping[str, Any],
        mutation_payload: Mapping[str, Any],
        goal_graph_optional: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Evaluate deterministic fitness using kernel evaluator module."""
        return self.fitness_evaluator.evaluate(
            str(agent.get("agent_id") or ""),
            dict(mutation_payload),
            goal_graph_optional,
        )

    def sign_certificate(self, agent: Mapping[str, Any]) -> Dict[str, Any]:
        """Sign/evolve agent certificate using cryovant lineage signer."""
        agent_id = str(agent.get("agent_id") or "")
        agent_path = Path(str(agent.get("agent_path") or ""))
        return cryovant.evolve_certificate(agent_id, agent_path, self.lineage_dir, {})


    @staticmethod
    def _execution_succeeded(execution_result: Mapping[str, Any]) -> bool:
        status = str(execution_result.get("status") or "").strip().lower()
        return bool(status) and status not in {"rejected", "failed", "error"}

    @staticmethod
    def _fitness_accepted(fitness_result: Mapping[str, Any]) -> bool:
        if bool(fitness_result.get("accepted")):
            return True
        policy = fitness_result.get("policy")
        if isinstance(policy, Mapping) and bool(policy.get("accepted")):
            return True
        return bool(fitness_result.get("passed"))

    @staticmethod
    def _lineage_linkage(agent_id: str, mutation_payload: Mapping[str, Any], execution_result: Mapping[str, Any]) -> Dict[str, Any]:
        mutation_id = (
            mutation_payload.get("mutation_id")
            or execution_result.get("mutation_id")
            or execution_result.get("cycle_id")
        )
        if mutation_id:
            return {"lineage_linkage_type": "mutation_id", "lineage_linkage": str(mutation_id)}
        canonical_payload = json.dumps(
            {
                "agent_id": agent_id,
                "mutation": dict(mutation_payload),
                "execution": dict(execution_result),
            },
            sort_keys=True,
        )
        linkage = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        return {"lineage_linkage_type": "deterministic_hash", "lineage_linkage": f"sha256:{linkage}"}

    @staticmethod
    def _disposition_for_outcome(
        *,
        execution_status: str,
        execution_succeeded: bool,
        fitness_accepted: bool,
        rejected: bool,
        cosmetic_only: bool,
    ) -> str:
        if cosmetic_only:
            return "cosmetic_only"
        if rejected:
            return "rejected"
        if execution_succeeded and fitness_accepted:
            return "promoted"
        if execution_succeeded and not fitness_accepted:
            return "quarantined"
        if execution_status in {"failed", "error"}:
            return "failed"
        return "rejected"

    def _emit_cycle_outcome(
        self,
        *,
        agent_id: str,
        change_classification: str,
        change_reason: str,
        execution_result: Mapping[str, Any],
        fitness_result: Mapping[str, Any],
        certificate_result: Mapping[str, Any],
        mutation_payload: Mapping[str, Any],
        rejected: bool = False,
        cosmetic_only: bool = False,
    ) -> Dict[str, Any]:
        execution_status = str(execution_result.get("status") or "not_executed")
        execution_succeeded = self._execution_succeeded(execution_result)
        fitness_accepted = self._fitness_accepted(fitness_result)
        certificate_status = str(certificate_result.get("status") or ("signed" if certificate_result else "not_attempted"))
        disposition = self._disposition_for_outcome(
            execution_status=execution_status,
            execution_succeeded=execution_succeeded,
            fitness_accepted=fitness_accepted,
            rejected=rejected,
            cosmetic_only=cosmetic_only,
        )
        linkage = self._lineage_linkage(agent_id, mutation_payload, execution_result)
        event_payload: Dict[str, Any] = {
            "schema_version": "evolution.cycle_outcome.v1",
            "agent_id": agent_id,
            "change_classification": change_classification,
            "change_reason": change_reason,
            "execution_status": execution_status,
            "execution_succeeded": execution_succeeded,
            "fitness_score": fitness_result.get("score"),
            "fitness_accepted": fitness_accepted,
            "certificate_status": certificate_status,
            "certificate_signed": certificate_status not in {"skipped", "not_attempted", ""},
            "signing_status": certificate_status,
            "disposition": disposition,
            "promote_disposition": disposition,
            "cosmetic_only": cosmetic_only,
            **linkage,
        }
        metrics.log(event_type="evolution_cycle_outcome", payload=event_payload)
        push_to_dashboard("evolution_cycle_outcome", event_payload)
        return event_payload

    def run_cycle(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Run one mutation cycle, preferring compatibility adapter when explicitly selected."""
        if self.compatibility_adapter is not None and agent_id is None:
            return self.compatibility_adapter.run_cycle(agent_id)

        available_agents = list(iter_agent_dirs(self.agents_root))
        if not available_agents:
            raise RuntimeError("no_agents_available")

        available_agents_by_resolved = {agent_path.resolve(): agent_path for agent_path in available_agents}

        if agent_id is None:
            target_agent_path = available_agents[0]
        else:
            candidate_path = (self.agents_root / agent_id.replace(":", "/")).resolve()
            target_agent_path = available_agents_by_resolved.get(candidate_path)
            if target_agent_path is None:
                raise RuntimeError(f"agent_not_found:{agent_id}")

        agent = self.load_agent(target_agent_path)
        trigger_signal = self._load_previous_cycle_signal(str(agent.get("agent_id") or ""))
        trigger_decision = self._should_mutate(
            previous_failed=bool(trigger_signal.get("previous_failed")),
            previous_quarantined=bool(trigger_signal.get("previous_quarantined")),
            latest_fitness_score=float(trigger_signal.get("latest_fitness_score", 1.0) or 1.0),
            latest_fitness_threshold=float(trigger_signal.get("latest_fitness_threshold", 0.7) or 0.7),
            manual_trigger=manual_trigger,
        )
        metrics.log(
            event_type="mutation_trigger_decision",
            payload={
                "agent_id": agent.get("agent_id"),
                **trigger_decision,
            },
        )
        if not bool(trigger_decision.get("should_mutate")):
            return {
                "status": "skipped",
                "reason": "mutation_not_triggered_policy",
                "agent_id": agent.get("agent_id"),
                "trigger_evidence": trigger_decision,
                "kernel_path": True,
            }

        mutation = self.propose_mutation(agent)
        change_decision = classify_mutation_change(target_agent_path, mutation.get("request") or mutation)
        if not change_decision.run_mutation:
            metadata = apply_metadata_updates(target_agent_path)
            cryovant.touch_non_functional_metadata(
                str(agent.get("agent_id") or ""),
                target_agent_path,
                metadata_version=int(metadata.get("version", 0) or 0),
                mutation_count=int(metadata.get("mutation_count", 0) or 0),
                metadata_last_mutation=str(metadata.get("last_mutation") or ""),
            )
            metrics.log(
                event_type="cosmetic_update_only",
                payload={
                    "agent_id": agent.get("agent_id"),
                    "change_reason": change_decision.reason,
                    "metadata_version": metadata.get("version"),
                    "metadata_mutation_count": metadata.get("mutation_count"),
                    "metadata_last_mutation": metadata.get("last_mutation"),
                },
            )
            cycle_event = self._emit_cycle_outcome(
                agent_id=str(agent.get("agent_id") or ""),
                change_classification=change_decision.classification,
                change_reason=change_decision.reason,
                execution_result={"status": "skipped_non_functional"},
                fitness_result={"accepted": False, "score": None},
                certificate_result={"status": "skipped", "reason": "non_functional_change"},
                mutation_payload=mutation.get("request") or mutation,
                cosmetic_only=True,
            )
            return {
                "status": "metadata_only",
                "agent_id": agent.get("agent_id"),
                "change_classification": change_decision.classification,
                "change_reason": change_decision.reason,
                "cosmetic_only": True,
                "metadata": {
                    "mutation_count": metadata.get("mutation_count"),
                    "version": metadata.get("version"),
                    "last_mutation": metadata.get("last_mutation"),
                },
                "cycle_outcome_event": cycle_event,
                "kernel_path": True,
            }
        mutation_payload = mutation.get("request") or mutation
        validation = self.validate_mutation(None, mutation_payload)
        if not validation.get("valid"):
            cycle_event = self._emit_cycle_outcome(
                agent_id=str(agent.get("agent_id") or ""),
                change_classification=change_decision.classification,
                change_reason=change_decision.reason,
                execution_result={"status": "rejected", "reason": "policy_invalid"},
                fitness_result={"accepted": False, "score": None},
                certificate_result={"status": "skipped", "reason": "validation_failed"},
                mutation_payload=mutation_payload,
                rejected=True,
            )
            return {
                "status": "rejected",
                "reason": "policy_invalid",
                "agent_id": agent.get("agent_id"),
                **validation,
                "change_classification": change_decision.classification,
                "change_reason": change_decision.reason,
                "cycle_outcome_event": cycle_event,
            }

        forecast = self.fitness_evaluator.forecast(
            mutation_payload,
            agent_type=str((agent.get("meta") or {}).get("type") or "unknown"),
        )
        if not forecast.get("forecast_passed"):
            cycle_event = self._emit_cycle_outcome(
                agent_id=str(agent.get("agent_id") or ""),
                change_classification=change_decision.classification,
                change_reason=change_decision.reason,
                execution_result={"status": "rejected", "reason": "forecast_gate_failed"},
                fitness_result={"accepted": False, "score": forecast.get("forecast_score")},
                certificate_result={"status": "skipped", "reason": "forecast_gate_failed"},
                mutation_payload=mutation_payload,
                rejected=True,
            )
            return {
                "status": "rejected",
                "reason": "forecast_gate_failed",
                "agent_id": agent.get("agent_id"),
                "forecast": forecast,
                "change_classification": change_decision.classification,
                "change_reason": change_decision.reason,
                "cycle_outcome_event": cycle_event,
                "kernel_path": True,
            }

        execution_result = self.execute_in_sandbox(agent, mutation)
        fitness_result = self.evaluate_fitness(agent, mutation_payload)

        if self._execution_succeeded(execution_result) and self._fitness_accepted(fitness_result):
            certificate_result = self.sign_certificate(agent)
        elif not self._execution_succeeded(execution_result):
            certificate_result = {"status": "skipped", "reason": "execution_not_successful"}
        else:
            certificate_result = {"status": "skipped", "reason": "fitness_not_accepted"}

        cycle_event = self._emit_cycle_outcome(
            agent_id=str(agent.get("agent_id") or ""),
            change_classification=change_decision.classification,
            change_reason=change_decision.reason,
            execution_result=execution_result,
            fitness_result=fitness_result,
            certificate_result=certificate_result,
            mutation_payload=mutation_payload,
        )

        return {
            **execution_result,
            "agent_id": agent.get("agent_id"),
            "fitness": fitness_result,
            "certificate": certificate_result,
            "change_classification": change_decision.classification,
            "change_reason": change_decision.reason,
            "cycle_outcome_event": cycle_event,
            "kernel_path": True,
        }


__all__ = ["EvolutionKernel"]
