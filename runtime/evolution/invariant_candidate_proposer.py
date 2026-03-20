# SPDX-License-Identifier: Apache-2.0
"""Phase 81 — InvariantCandidateProposer.

Converts FailureCluster objects from FailurePatternMiner into structured
InvariantCandidate proposals formatted for constitutional ratification.

Constitutional Invariants
─────────────────────────
  CSDL-CANDIDATE-0  Every InvariantCandidate has a stable deterministic ID
                    derived from its source cluster_id. Re-running the proposer
                    on identical clusters produces identical candidate IDs.
  CSDL-CANDIDATE-ADVISORY-0  Candidates are advisory drafts only. They are
                    never written to constitution.yaml without HUMAN-0
                    ratification via InvariantRatificationGate.
  CSDL-CANDIDATE-DEDUP-0  Proposing the same cluster twice produces the same
                    candidate ID — duplicate proposals are idempotent.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from runtime.evolution.failure_pattern_miner import FailureCluster

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANDIDATE_VERSION: str = "81.0"
_CONSTITUTION_RULE_TEMPLATE: Dict[str, Any] = {
    "name": "",           # filled by proposer
    "enabled": False,     # CSDL-CANDIDATE-ADVISORY-0: disabled until ratified
    "severity": "advisory",
    "tier_overrides": {},
    "reason": "",         # filled by proposer
    "validator": "",      # filled by proposer
}

# Severity escalation heuristic: high-frequency clusters suggest stronger rule
_SEVERITY_BY_FREQUENCY = [
    (50, "blocking"),
    (20, "warning"),
    (0,  "advisory"),
]


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvariantCandidate:
    """Draft constitutional invariant derived from a FailureCluster.

    Attributes
    ----------
    candidate_id:       Deterministic ID: "CSDL-CAND-{cluster_id[:8]}".
    source_cluster_id:  Originating FailureCluster.cluster_id.
    invariant_id:       Proposed invariant name e.g. "AUTO-DISCOVERED-0".
    name:               Short slug for constitution.yaml "name" field.
    reason:             Human-readable explanation for the rule.
    validator:          Proposed validator function name (stub — not yet wired).
    severity:           "blocking" | "warning" | "advisory".
    source_frequency:   Frequency of source cluster (provenance signal).
    constitution_entry: Dict ready for insertion into constitution.yaml rules[].
    evidence_digest:    SHA-256 of the canonical candidate payload.
    schema_version:     Version of this candidate schema.
    """

    candidate_id: str
    source_cluster_id: str
    invariant_id: str
    name: str
    reason: str
    validator: str
    severity: str
    source_frequency: int
    constitution_entry: Dict[str, Any]
    evidence_digest: str
    schema_version: str = CANDIDATE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_cluster_id": self.source_cluster_id,
            "invariant_id": self.invariant_id,
            "name": self.name,
            "reason": self.reason,
            "validator": self.validator,
            "severity": self.severity,
            "source_frequency": self.source_frequency,
            "constitution_entry": self.constitution_entry,
            "evidence_digest": self.evidence_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "InvariantCandidate":
        return cls(
            candidate_id=d["candidate_id"],
            source_cluster_id=d["source_cluster_id"],
            invariant_id=d["invariant_id"],
            name=d["name"],
            reason=d["reason"],
            validator=d["validator"],
            severity=d["severity"],
            source_frequency=d["source_frequency"],
            constitution_entry=d["constitution_entry"],
            evidence_digest=d["evidence_digest"],
            schema_version=d.get("schema_version", CANDIDATE_VERSION),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate_id(cluster_id: str) -> str:
    """CSDL-CANDIDATE-0 / CSDL-CANDIDATE-DEDUP-0: deterministic from cluster_id."""
    return "CSDL-CAND-" + cluster_id[5:13]  # strip "csdl-" prefix, take 8 hex chars


def _severity_for_frequency(freq: int) -> str:
    for threshold, sev in _SEVERITY_BY_FREQUENCY:
        if freq >= threshold:
            return sev
    return "advisory"


def _invariant_name(failed_rules: Sequence[str], cluster_id: str) -> str:
    """Generate a short, stable invariant slug from failed rules."""
    if not failed_rules:
        return f"auto_discovered_{cluster_id[:8]}"
    # Take first rule, strip spaces, append cluster suffix for uniqueness
    first = failed_rules[0].replace(" ", "_").replace("-", "_").lower()
    suffix = cluster_id[5:9]
    return f"auto_{first}_{suffix}_0"


def _invariant_id(failed_rules: Sequence[str], cluster_id: str) -> str:
    """UPPERCASE invariant ID for documentation references."""
    slug = _invariant_name(failed_rules, cluster_id)
    return slug.upper().replace("_0", "-0")


def _reason_text(cluster: FailureCluster) -> str:
    """Generate a human-readable reason string from cluster data."""
    rule_list = ", ".join(cluster.failed_rules) if cluster.failed_rules else "unknown rules"
    return (
        f"Phase 81 CSDL auto-discovered invariant: {cluster.frequency} gate rejections "
        f"share the failure pattern [{rule_list}]. "
        f"Candidate severity based on frequency. "
        f"Source cluster: {cluster.cluster_id}. "
        f"ADVISORY until HUMAN-0 ratification via InvariantRatificationGate."
    )


def _evidence_digest(candidate: Dict[str, Any]) -> str:
    payload = json.dumps(
        {k: v for k, v in candidate.items() if k != "evidence_digest"},
        sort_keys=True, separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# InvariantCandidateProposer
# ---------------------------------------------------------------------------


class InvariantCandidateProposer:
    """Phase 81 invariant candidate proposer.

    Converts FailureCluster objects into InvariantCandidate proposals.
    All proposals are ADVISORY and DISABLED until ratified by HUMAN-0.

    LLM Enhancement (optional)
    --------------------------
    When an LLMProviderClient is injected, the proposer requests an
    improved natural-language reason string from the LLM for each candidate.
    The LLM is instructed to return only JSON with a single "reason" key.
    If the LLM call fails, the deterministic fallback reason is used —
    proposals are never blocked by LLM unavailability.

    Determinism guarantee (CSDL-CANDIDATE-0):
    Without LLM enhancement, propose() is fully deterministic. With LLM
    enhancement, the reason field may vary — but candidate_id, invariant_id,
    name, severity, and constitution_entry structure are always deterministic.
    """

    def __init__(
        self,
        *,
        llm_client: Optional[Any] = None,
        use_llm_enhancement: bool = False,
    ) -> None:
        self._llm = llm_client
        self._use_llm = use_llm_enhancement and llm_client is not None

    def propose(
        self, clusters: Sequence[FailureCluster]
    ) -> List[InvariantCandidate]:
        """Convert FailureCluster list into InvariantCandidate list.

        CSDL-CANDIDATE-0: deterministic (no LLM) or deterministic-structure (LLM).
        CSDL-CANDIDATE-ADVISORY-0: all candidates are disabled in constitution_entry.
        CSDL-CANDIDATE-DEDUP-0: same cluster → same candidate_id.
        """
        candidates: List[InvariantCandidate] = []
        for cluster in clusters:
            candidate = self._propose_one(cluster)
            candidates.append(candidate)
            log.info(
                "CSDL: proposed invariant candidate %s (freq=%d, severity=%s)",
                candidate.candidate_id, cluster.frequency, candidate.severity,
            )
        return candidates

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _propose_one(self, cluster: FailureCluster) -> InvariantCandidate:
        cand_id = _candidate_id(cluster.cluster_id)
        sev = _severity_for_frequency(cluster.frequency)
        name = _invariant_name(cluster.failed_rules, cluster.cluster_id)
        inv_id = _invariant_id(cluster.failed_rules, cluster.cluster_id)
        validator = f"csdl_auto_{cluster.cluster_id[5:13]}"

        # Deterministic fallback reason
        reason = _reason_text(cluster)

        # Optional LLM enhancement — fail-safe
        if self._use_llm:
            reason = self._enhance_reason(cluster, reason)

        constitution_entry: Dict[str, Any] = {
            "name": name,
            "enabled": False,  # CSDL-CANDIDATE-ADVISORY-0
            "severity": sev,
            "tier_overrides": {},
            "reason": reason,
            "validator": validator,
        }

        # Build partial dict for digest computation
        partial: Dict[str, Any] = {
            "candidate_id": cand_id,
            "source_cluster_id": cluster.cluster_id,
            "invariant_id": inv_id,
            "name": name,
            "reason": reason,
            "validator": validator,
            "severity": sev,
            "source_frequency": cluster.frequency,
            "constitution_entry": constitution_entry,
        }
        digest = _evidence_digest(partial)

        return InvariantCandidate(
            candidate_id=cand_id,
            source_cluster_id=cluster.cluster_id,
            invariant_id=inv_id,
            name=name,
            reason=reason,
            validator=validator,
            severity=sev,
            source_frequency=cluster.frequency,
            constitution_entry=constitution_entry,
            evidence_digest=digest,
        )

    def _enhance_reason(self, cluster: FailureCluster, fallback: str) -> str:
        """Request improved reason text from LLM. Returns fallback on any failure."""
        try:
            system = (
                "You are a constitutional governance assistant for the ADAAD autonomous "
                "code evolution system. Respond ONLY with a valid JSON object containing "
                "exactly one key: 'reason'. The value must be a single sentence "
                "(max 200 characters) explaining why the given gate rejection pattern "
                "warrants a constitutional invariant. Be precise and technical."
            )
            user = json.dumps({
                "failed_rules": list(cluster.failed_rules),
                "reason_codes": list(cluster.reason_codes),
                "frequency": cluster.frequency,
                "gate_mode_distribution": cluster.gate_mode_counts,
            })
            result = self._llm.request_json(system_prompt=system, user_prompt=user)
            if result.ok and isinstance(result.payload, dict):
                enhanced = str(result.payload.get("reason") or "").strip()
                if enhanced and len(enhanced) <= 500:
                    return enhanced
        except Exception as exc:  # noqa: BLE001
            log.warning("CSDL: LLM reason enhancement failed (using fallback): %s", exc)
        return fallback
