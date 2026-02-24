# SPDX-License-Identifier: Apache-2.0
"""Evolution runtime wrapper integrating governor, epochs, and replay checks."""

from __future__ import annotations

import os
from typing import Any, Dict

from app.agents.mutation_request import MutationRequest
from runtime.evolution.baseline import BaselineStore
from runtime.evolution.epoch import EpochManager
from runtime.evolution.fitness_regression import RegressionSeverity, emit_fitness_regression_signal
from runtime.evolution.governor import EvolutionGovernor
from runtime.evolution.entropy_forecast import EntropyBudgetForecaster
from runtime.evolution.lineage_v2 import LineageIntegrityError, LineageLedgerV2
from runtime.evolution.metrics_schema import EvolutionMetricsEmitter
from runtime.evolution.replay import ReplayEngine
from runtime.evolution.replay_mode import ReplayMode, normalize_replay_mode
from runtime.evolution.replay_verifier import ReplayVerifier
from runtime.evolution.checkpoint_registry import CheckpointRegistry
from runtime.evolution.checkpoint_verifier import CheckpointVerifier, CheckpointVerificationError, verify_checkpoint_chain
from runtime import constitution
from runtime.governance.foundation import RuntimeDeterminismProvider, require_replay_safe_provider
from runtime.governance.federation.coherence_validator import FederationCoherenceValidator, RECOMMENDATION_HALT


class EvolutionRuntime:
    def __init__(self, *, provider: RuntimeDeterminismProvider | None = None) -> None:
        self.ledger = LineageLedgerV2()
        self.governor = EvolutionGovernor(ledger=self.ledger, provider=provider)
        self.epoch_manager = EpochManager(self.governor, self.ledger, provider=self.governor.provider)
        self.replay_mode = ReplayMode.OFF
        self.replay_engine = ReplayEngine(self.ledger)
        self.replay_verifier = ReplayVerifier(self.ledger, self.replay_engine)
        self.baseline_store = BaselineStore()
        self.checkpoint_registry = CheckpointRegistry(
            self.ledger,
            provider=self.governor.provider,
            replay_mode=self.replay_mode.value,
            recovery_tier=self.governor.recovery_tier.value,
        )
        self.metrics_emitter = EvolutionMetricsEmitter(self.ledger)
        self.coherence_validator = FederationCoherenceValidator()

        self.current_epoch_id = ""
        self.epoch_metadata: Dict[str, Any] = {}
        self.epoch_mutation_count = 0
        self.epoch_start_ts = ""
        self.epoch_digest: str | None = None
        self.baseline_id = ""
        self.baseline_hash = ""
        self.epoch_cumulative_entropy_bits = 0
        self._continuity_verified_epoch_id = ""
        self.fitness_regression_signal = {}

    @property
    def fail_closed(self) -> bool:
        return self.governor.fail_closed

    def set_replay_mode(self, replay_mode: str | bool | ReplayMode) -> None:
        self.replay_mode = normalize_replay_mode(replay_mode)
        self.epoch_manager.replay_mode = self.replay_mode.value
        self.governor.replay_mode = self.replay_mode.value
        # Keep epoch manager aligned when tests or callers swap governor.provider directly.
        self.epoch_manager.provider = self.governor.provider
        require_replay_safe_provider(
            self.governor.provider,
            replay_mode=self.replay_mode.value,
            recovery_tier=self.governor.recovery_tier.value,
        )
        require_replay_safe_provider(
            self.epoch_manager.provider,
            replay_mode=self.replay_mode.value,
            recovery_tier=self.governor.recovery_tier.value,
        )
        self.checkpoint_registry = CheckpointRegistry(
            self.ledger,
            provider=self.governor.provider,
            replay_mode=self.replay_mode.value,
            recovery_tier=self.governor.recovery_tier.value,
        )
        self.metrics_emitter = EvolutionMetricsEmitter(self.ledger)

    def boot(self) -> Dict[str, Any]:
        coherence_report = self.coherence_validator.validate()
        self.ledger.append_event(
            "FederationCoherenceEvent",
            {
                "epoch_id": self.current_epoch_id or "boot",
                "report": coherence_report.to_dict(),
                "recommendation": coherence_report.recommendation,
                "report_hash": coherence_report.report_hash,
            },
        )
        if coherence_report.recommendation == RECOMMENDATION_HALT:
            self._enter_fail_closed_replay(epoch_id=self.current_epoch_id or "boot", reason="federation_split_brain")
            raise RuntimeError("federation_split_brain")

        lineage_check = constitution.VALIDATOR_REGISTRY["lineage_continuity"](
            MutationRequest(
                agent_id="runtime_bootstrap",
                generation_ts="boot",
                intent="lineage_verification",
                ops=[],
                signature="cryovant-static-bootstrap",
                nonce="boot-0",
            )
        )
        fail_closed_reasons = {"lineage_violation_detected"}
        if not bool(lineage_check.get("ok")) and str(lineage_check.get("reason") or "") in fail_closed_reasons:
            self._enter_fail_closed_replay(epoch_id=self.current_epoch_id or "boot", reason="lineage_continuity_failed")
            raise RuntimeError("lineage_continuity_failed")

        epoch = self.epoch_manager.load_or_create()
        self._sync_from_epoch(epoch.to_dict())
        self.epoch_digest = self.ledger.get_epoch_digest(epoch.epoch_id)
        return epoch.to_dict()

    def before_mutation_cycle(self) -> Dict[str, Any]:
        if self.epoch_manager.should_rotate():
            reason = self.epoch_manager.rotation_reason()
            self.before_epoch_rotation(reason)
            rotated = self.after_epoch_rotation(reason)
            self._sync_from_epoch(rotated)
            return {"epoch_id": rotated["epoch_id"]}

        state = self.epoch_manager.get_active()
        epoch_id = state.epoch_id
        mutation_count = int(state.mutation_count)

        entropy_forecast = self.entropy_forecaster.forecast(
            epoch_id=epoch_id,
            mutation_count=mutation_count,
            epoch_entropy_bits=self.epoch_cumulative_entropy_bits,
            per_mutation_ceiling_bits=int(os.getenv("ADAAD_MAX_MUTATION_ENTROPY_BITS", "128") or 128),
            per_epoch_ceiling_bits=int(os.getenv("ADAAD_MAX_EPOCH_ENTROPY_BITS", "4096") or 4096),
        )
        self.ledger.append_event("EntropyForecastEvent", entropy_forecast)

        entropy_advisory = str(entropy_forecast.get("advisory") or "clear")
        entropy_action = "continue"
        if entropy_advisory == "warn":
            self.epoch_metadata["forecast_mutation_entropy_ceiling_bits"] = int(
                entropy_forecast.get("recommended_per_mutation_ceiling_bits") or 0
            )
            entropy_action = "adjust_ceiling"
        elif entropy_advisory == "block":
            return {
                "epoch_id": epoch_id,
                "blocked": True,
                "reason": "entropy_forecast_block",
                "entropy_forecast": entropy_forecast,
            }

        threat_scan = self.threat_monitor.scan(
            epoch_id=epoch_id,
            mutation_count=mutation_count,
            events=self.ledger.read_epoch(epoch_id),
        )
        self.ledger.append_event("ThreatScanEvent", threat_scan)

        recommendation = str(threat_scan.get("recommendation") or "continue")
        if recommendation == "halt":
            self._enter_fail_closed_replay(epoch_id=epoch_id, reason="threat_scan_halt")
            return {
                "epoch_id": epoch_id,
                "blocked": True,
                "reason": "threat_scan_halt",
                "entropy_forecast": entropy_forecast,
                "threat_scan": threat_scan,
            }
        if recommendation == "escalate":
            self.epoch_metadata["threat_scan_escalated"] = True
            return {
                "epoch_id": epoch_id,
                "escalated": True,
                "reason": "threat_scan_escalate",
                "entropy_action": entropy_action,
                "entropy_forecast": entropy_forecast,
                "threat_scan": threat_scan,
            }

        state = self.epoch_manager.increment_mutation_count()
        payload = state.to_dict()
        self._sync_from_epoch(payload)
        return {
            "epoch_id": payload["epoch_id"],
            "entropy_action": entropy_action,
            "entropy_forecast": entropy_forecast,
            "threat_scan": threat_scan,
        }

    def after_mutation_cycle(self, result: Dict[str, Any]) -> Dict[str, Any]:
        state = self.epoch_manager.get_active()
        epoch_id = state.epoch_id
        cycle_id = str(result.get("cycle_id") or result.get("mutation_id") or f"cycle-{state.mutation_count:06d}")
        cycle_metrics = self.metrics_emitter.emit_cycle_metrics(epoch_id=epoch_id, cycle_id=cycle_id, result=result)
        regression_signal = emit_fitness_regression_signal(self.metrics_emitter._read_history())
        self.fitness_regression_signal = regression_signal.to_dict()
        self.governor.apply_fitness_regression_signal(epoch_id=epoch_id, signal=regression_signal)
        if regression_signal.severity == RegressionSeverity.SEVERE:
            self.governor.escalate_governance_debt(epoch_id=epoch_id, signal=regression_signal)
            self.epoch_manager.trigger_force_end("severe_fitness_regression")

        expected = self.ledger.get_epoch_digest(epoch_id) or "sha256:0"
        try:
            actual = self.replay_engine.compute_incremental_digest(epoch_id)
        except LineageIntegrityError as exc:
            self.epoch_manager.trigger_force_end()
            self._enter_fail_closed_replay(epoch_id=epoch_id, reason="lineage_integrity_error")
            current = self.epoch_manager.get_active().to_dict()
            self._sync_from_epoch(current)
            return {
                "epoch": current,
                "metrics": cycle_metrics,
                "fitness_regression": self.fitness_regression_signal,
                "replay": {
                    "epoch_id": epoch_id,
                    "replay_passed": False,
                    "epoch_digest": expected,
                    "replay_digest": "unavailable",
                    "expected": expected,
                    "replay_score": 0.0,
                    "cause_buckets": {
                        "digest_mismatch": True,
                        "baseline_mismatch": True,
                        "time_input_variance": False,
                        "external_dependency_variance": False,
                    },
                    "decision": "fail_closed",
                    "error": str(exc),
                },
            }
        verification = self._build_replay_verification(
            epoch_id=epoch_id,
            expected_digest=expected,
            actual_digest=actual,
            baseline_digest=expected,
            baseline_source="lineage_epoch_digest",
            baseline_match=True,
        )
        passed = verification["passed"]

        replay_result = {
            "epoch_id": epoch_id,
            "replay_passed": passed,
            "epoch_digest": expected,
            "replay_digest": actual,
            "expected": expected,
            "replay_score": verification["replay_score"],
            "cause_buckets": verification["cause_buckets"],
            "decision": verification["decision"],
        }
        self.epoch_digest = expected

        self.ledger.append_event(
            "ReplayVerificationEvent",
            {
                "epoch_id": epoch_id,
                "epoch_digest": expected,
                "replay_digest": actual,
                "replay_passed": passed,
                "replay_score": verification["replay_score"],
                "cause_buckets": verification["cause_buckets"],
                "decision": verification["decision"],
            },
        )

        if not passed:
            self.epoch_manager.trigger_force_end()
            self.governor.enter_fail_closed("replay_divergence", epoch_id)

        current = self.epoch_manager.get_active().to_dict()
        self._sync_from_epoch(current)
        return {"epoch": current, "replay": replay_result, "metrics": cycle_metrics, "fitness_regression": self.fitness_regression_signal}

    def before_epoch_rotation(self, reason: str) -> Dict[str, Any]:
        current = self.epoch_manager.get_active()
        return {"epoch_id": current.epoch_id, "reason": reason}

    def after_epoch_rotation(self, reason: str) -> Dict[str, Any]:
        state = self.epoch_manager.rotate_epoch(reason)
        payload = state.to_dict()
        self.epoch_digest = self.ledger.get_epoch_digest(payload["epoch_id"])
        self._continuity_verified_epoch_id = ""
        self.fitness_regression_signal = {}
        self._sync_from_epoch(payload)
        return payload

    def _verify_epoch_checkpoint_continuity(self, epoch_id: str) -> Dict[str, Any]:
        if self._continuity_verified_epoch_id == epoch_id:
            return {
                "ok": True,
                "epoch_id": epoch_id,
                "reason": "cached",
            }
        try:
            continuity = CheckpointVerifier.verify_epoch_checkpoint_continuity(self.ledger, epoch_id)
        except CheckpointVerificationError as exc:
            raise RuntimeError(f"epoch_checkpoint_continuity_failed:{exc}") from exc
        self._continuity_verified_epoch_id = epoch_id
        return continuity

    def verify_epoch(self, epoch_id: str, expected: str | None = None) -> Dict[str, Any]:
        try:
            replay = self.replay_engine.replay_epoch(epoch_id)
        except LineageIntegrityError as exc:
            self._enter_fail_closed_replay(epoch_id=epoch_id, reason="lineage_integrity_error")
            return {
                "epoch_id": epoch_id,
                "baseline_epoch": epoch_id,
                "baseline_source": "lineage_epoch_digest",
                "baseline_id": self.baseline_id,
                "baseline_hash": self.baseline_hash,
                "baseline_match": False,
                "expected_digest": expected or "sha256:0",
                "actual_digest": "unavailable",
                "passed": False,
                "decision": "fail_closed",
                "trusted": False,
                "digest_match": False,
                "digest": "unavailable",
                "expected": expected or "sha256:0",
                "replay_score": 0.0,
                "cause_buckets": {
                    "digest_mismatch": True,
                    "baseline_mismatch": True,
                    "time_input_variance": False,
                    "external_dependency_variance": False,
                },
                "integrity_error": str(exc),
                "checkpoint": None,
                "checkpoint_verification": {"ok": False, "reason": "lineage_integrity_error"},
            }
        actual_digest = replay["digest"]
        ledger_baseline = self.ledger.get_epoch_digest(epoch_id) or "sha256:0"
        expected_digest = expected or ledger_baseline
        baseline_source = "provided_expected_digest" if expected is not None else "lineage_epoch_digest"

        baseline_record = self.baseline_store.find_for_epoch(epoch_id)
        record_baseline_id = str((baseline_record or {}).get("baseline_id") or "")
        record_baseline_hash = str((baseline_record or {}).get("baseline_hash") or "")
        referenced_baseline_id = self.baseline_id if epoch_id == self.current_epoch_id else record_baseline_id
        referenced_baseline_hash = self.baseline_hash if epoch_id == self.current_epoch_id else record_baseline_hash
        baseline_match = bool(
            baseline_record
            and referenced_baseline_id == record_baseline_id
            and referenced_baseline_hash == record_baseline_hash
        )

        verification = self._build_replay_verification(
            epoch_id=epoch_id,
            expected_digest=expected_digest,
            actual_digest=actual_digest,
            baseline_digest=ledger_baseline,
            baseline_source=baseline_source,
            baseline_match=baseline_match,
        )
        passed = verification["passed"]
        decision = verification["decision"]
        self.ledger.append_event(
            "ReplayVerificationEvent",
            {
                "epoch_id": epoch_id,
                "epoch_digest": expected_digest,
                "replay_digest": actual_digest,
                "replay_passed": passed,
                "expected": expected_digest,
                "decision": decision,
                "baseline_id": referenced_baseline_id,
                "baseline_hash": referenced_baseline_hash,
                "baseline_match": baseline_match,
                "trusted": verification["trusted"],
                "replay_score": verification["replay_score"],
                "cause_buckets": verification["cause_buckets"],
            },
        )
        checkpoint = self.checkpoint_registry.create_checkpoint(epoch_id)
        self._verify_epoch_checkpoint_continuity(epoch_id)
        checkpoint_verification = verify_checkpoint_chain(self.ledger, epoch_id)
        return {
            "epoch_id": epoch_id,
            "baseline_epoch": epoch_id,
            "baseline_source": baseline_source,
            "baseline_id": referenced_baseline_id,
            "baseline_hash": referenced_baseline_hash,
            "baseline_match": baseline_match,
            "expected_digest": expected_digest,
            "actual_digest": actual_digest,
            "passed": passed,
            "decision": decision,
            "trusted": verification["trusted"],
            "digest_match": verification["digest_match"],
            "digest": actual_digest,
            "expected": expected_digest,
            "replay_score": verification["replay_score"],
            "cause_buckets": verification["cause_buckets"],
            "checkpoint": checkpoint,
            "checkpoint_verification": checkpoint_verification,
        }

    def _build_replay_verification(
        self,
        *,
        epoch_id: str,
        expected_digest: str,
        actual_digest: str,
        baseline_digest: str | None = None,
        baseline_source: str = "lineage_epoch_digest",
        baseline_match: bool = True,
    ) -> Dict[str, Any]:
        digest_match = expected_digest == actual_digest
        baseline_value = baseline_digest or expected_digest
        trusted = digest_match and baseline_match
        cause_buckets = {
            "digest_mismatch": not digest_match,
            "baseline_mismatch": baseline_value != expected_digest or not baseline_match,
            "time_input_variance": False,
            "external_dependency_variance": False,
        }
        score = 1.0
        if cause_buckets["digest_mismatch"]:
            score -= 0.6
        if cause_buckets["baseline_mismatch"]:
            score -= 0.2
        if cause_buckets["time_input_variance"]:
            score -= 0.1
        if cause_buckets["external_dependency_variance"]:
            score -= 0.1
        replay_score = round(max(0.0, min(1.0, score)), 4)
        return {
            "epoch_id": epoch_id,
            "passed": trusted,
            "decision": "match" if trusted else "diverge",
            "baseline_source": baseline_source,
            "replay_score": replay_score,
            "cause_buckets": cause_buckets,
            "trusted": trusted,
            "digest_match": digest_match,
        }

    def replay_preflight(self, mode: str | ReplayMode, *, epoch_id: str | None = None) -> Dict[str, Any]:
        replay_mode = normalize_replay_mode(mode)
        if replay_mode is ReplayMode.OFF:
            return {
                "mode": replay_mode.value,
                "verify_target": "none",
                "has_divergence": False,
                "decision": "skip",
                "results": [],
            }

        if epoch_id:
            results = [self.verify_epoch(epoch_id)]
            verify_target = "single_epoch"
        else:
            results = [self.verify_epoch(each_epoch_id) for each_epoch_id in self.ledger.list_epoch_ids()]
            verify_target = "all_epochs"

        has_divergence = any(not result["passed"] for result in results)
        federation_drift_detected = any(bool(result.get("federation_drift_detected")) for result in results)
        if (has_divergence or federation_drift_detected) and replay_mode.fail_closed:
            reason = "federation_drift_detected" if federation_drift_detected else "replay_divergence"
            self.governor.enter_fail_closed(reason, self.current_epoch_id or "unknown")
            decision = "fail_closed"
        else:
            decision = "continue"
        return {
            "mode": replay_mode.value,
            "verify_target": verify_target,
            "has_divergence": has_divergence,
            "federation_drift_detected": federation_drift_detected,
            "decision": decision,
            "results": results,
        }

    def verify_all_epochs(self) -> bool:
        ok = True
        for epoch_id in self.ledger.list_epoch_ids():
            result = self.verify_epoch(epoch_id)
            ok = ok and result["passed"]
        if not ok:
            self.governor.enter_fail_closed("replay_divergence", self.current_epoch_id or "unknown")
        return ok

    def _sync_from_epoch(self, payload: Dict[str, Any]) -> None:
        self.current_epoch_id = str(payload.get("epoch_id") or "")
        self.epoch_metadata = dict(payload.get("metadata") or {})
        self.epoch_mutation_count = int(payload.get("mutation_count") or 0)
        self.epoch_start_ts = str(payload.get("start_ts") or "")
        self.baseline_id = str(payload.get("baseline_id") or "")
        self.baseline_hash = str(payload.get("baseline_hash") or "")
        self.epoch_cumulative_entropy_bits = int(payload.get("cumulative_entropy_bits") or 0)


    def _enter_fail_closed_replay(self, *, epoch_id: str, reason: str) -> None:
        try:
            self.governor.enter_fail_closed(reason, epoch_id)
        except LineageIntegrityError:
            self.governor.fail_closed = True
            self.governor.fail_closed_reason = reason


__all__ = ["EvolutionRuntime"]
