# SPDX-License-Identifier: Apache-2.0
"""Deterministic governance adapter for policy-driven privileged operations."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from runtime import metrics
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from security.ledger import journal


@dataclass(frozen=True)
class GovernanceDecision:
    allowed: bool
    decision: str
    reason: str
    input_digest: str
    policy_hash: str
    policy_version: str


class GovernancePolicyAdapter:
    """Evaluate governance policy decisions with deterministic audit evidence."""

    def __init__(self, policy_paths: Iterable[Path] | None = None) -> None:
        self._policy_paths = tuple(policy_paths) if policy_paths is not None else tuple(self._paths_from_env())
        if not self._policy_paths:
            self._policy_paths = (Path("governance/policies.rego"),)

    @staticmethod
    def _paths_from_env() -> list[Path]:
        raw = os.getenv("ADAAD_GOVERNANCE_POLICY_PATHS", "").strip()
        if not raw:
            return []
        return [Path(part.strip()) for part in raw.split(os.pathsep) if part.strip()]

    def _load_bundle(self) -> tuple[str, str, str]:
        texts: list[str] = []
        source_labels: list[str] = []
        for path in self._policy_paths:
            if not path.exists():
                raise FileNotFoundError(f"policy_bundle_missing:{path}")
            text = path.read_text(encoding="utf-8")
            texts.append(text)
            source_labels.append(str(path).replace("\\", "/"))
        policy_source = "\n\n".join(texts)
        policy_hash = sha256_prefixed_digest(policy_source.encode("utf-8"))
        policy_version = "+".join(source_labels)
        return policy_hash, policy_version, policy_source

    def _is_explicitly_disabled(self, source: str) -> bool:
        return "default allow = false" in source and "allow {" not in source

    def evaluate(self, payload: Mapping[str, Any]) -> GovernanceDecision:
        input_digest = sha256_prefixed_digest(canonical_json(dict(payload)))
        try:
            policy_hash, policy_version, full_source = self._load_bundle()
            if self._is_explicitly_disabled(full_source):
                decision = GovernanceDecision(False, "deny", "policy_disabled", input_digest, policy_hash, policy_version)
            else:
                decision = self._evaluate_baseline(payload, input_digest, policy_hash, policy_version, full_source)
        except Exception as exc:
            decision = GovernanceDecision(
                allowed=False,
                decision="deny",
                reason=f"policy_unavailable:{type(exc).__name__}",
                input_digest=input_digest,
                policy_hash="sha256:unavailable",
                policy_version="unavailable",
            )

        self._record_decision(payload, decision)
        return decision

    def _extract_set(self, source: str, variable: str, default: set[str]) -> set[str]:
        matches = re.findall(rf"{re.escape(variable)}\s*:=\s*\{{([^}}]*)\}}", source)
        if not matches:
            return set(default)
        latest = matches[-1]
        values: set[str] = set()
        for item in latest.split(","):
            stripped = item.strip().strip("\"'")
            if stripped:
                values.add(stripped)
        return values or set(default)

    def _evaluate_baseline(self, payload: Mapping[str, Any], input_digest: str, policy_hash: str, policy_version: str, policy_source: str) -> GovernanceDecision:
        operation = str(payload.get("operation", "")).strip()
        actor_tier = str(payload.get("actor_tier", "")).strip().lower()
        fail_closed = bool(payload.get("fail_closed", False))
        emergency_override = bool(payload.get("emergency_override", False))
        override_token_verified = bool(payload.get("override_token_verified", False))

        privileged_operations = self._extract_set(policy_source, "privileged_operations", {"mutation.apply", "mutation.promote", "mutation.manifest.write"})
        allowed_tiers = {value.lower() for value in self._extract_set(policy_source, "allowed_tiers", {"governance", "production"})}

        if fail_closed:
            return GovernanceDecision(False, "deny", "fail_closed", input_digest, policy_hash, policy_version)
        if operation not in privileged_operations:
            return GovernanceDecision(False, "deny", "operation_not_privileged", input_digest, policy_hash, policy_version)
        emergency_override_enabled = "input.emergency_override == true" in policy_source
        if emergency_override_enabled and emergency_override and override_token_verified:
            return GovernanceDecision(True, "allow", "emergency_override", input_digest, policy_hash, policy_version)
        if actor_tier in allowed_tiers:
            return GovernanceDecision(True, "allow", "baseline_allow", input_digest, policy_hash, policy_version)
        return GovernanceDecision(False, "deny", "insufficient_tier", input_digest, policy_hash, policy_version)

    def _record_decision(self, payload: Mapping[str, Any], decision: GovernanceDecision) -> None:
        evidence_payload = {
            "event_schema": "governance.policy_decision.v1",
            "operation": str(payload.get("operation", "")),
            "actor": str(payload.get("actor", "system")),
            "input_digest": decision.input_digest,
            "policy_hash": decision.policy_hash,
            "policy_version": decision.policy_version,
            "decision": decision.decision,
            "reason": decision.reason,
        }
        metrics.log(event_type="governance_policy_decision", payload=evidence_payload, level="INFO")
        journal.write_entry(agent_id=str(payload.get("actor", "system")), action="governance_policy_decision", payload=evidence_payload)
        journal.append_tx(tx_type="governance_policy_decision", payload=evidence_payload)


__all__ = ["GovernanceDecision", "GovernancePolicyAdapter"]
