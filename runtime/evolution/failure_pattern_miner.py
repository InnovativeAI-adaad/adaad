# SPDX-License-Identifier: Apache-2.0
"""Phase 81 — FailurePatternMiner.

Mines the GateDecisionLedger for recurring rejection patterns and produces
structured FailureCluster objects that drive invariant candidate generation.

Constitutional Invariants
─────────────────────────
  CSDL-CLUSTER-0   Cluster membership is deterministic given identical input
                   records. Identical rejection corpora → identical clusters.
  CSDL-IMMUTABLE-0 Mining is strictly read-only. The gate decision ledger is
                   never written to by this module.
  CSDL-MIN-FREQ-0  A FailureCluster is only emitted when its frequency meets
                   or exceeds MIN_CLUSTER_FREQUENCY. Rare noise is suppressed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_CLUSTER_FREQUENCY: int = 3      # CSDL-MIN-FREQ-0: ignore clusters below this count
MAX_CLUSTERS_PER_MINE: int = 20     # cap on emitted clusters per mining run
SIMILARITY_THRESHOLD: float = 0.60  # Jaccard threshold for rule-set grouping
CLUSTER_VERSION: str = "81.0"


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RejectionRecord:
    """Normalised view of a single gate rejection entry.

    Extracted from raw GateDecisionLedger JSONL records.
    """

    mutation_id: str
    failed_rules: Tuple[str, ...]     # sorted for determinism (CSDL-CLUSTER-0)
    reason_codes: Tuple[str, ...]     # sorted for determinism
    gate_mode: str
    trust_mode: str
    sequence: int

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> Optional["RejectionRecord"]:
        """Build from a raw ledger record dict. Returns None if not a rejection."""
        if raw.get("approved", True):
            return None
        failed = tuple(sorted(str(r) for r in (raw.get("failed_rules") or [])))
        reasons = tuple(sorted(str(r) for r in (raw.get("reason_codes") or [])))
        return cls(
            mutation_id=str(raw.get("mutation_id") or ""),
            failed_rules=failed,
            reason_codes=reasons,
            gate_mode=str(raw.get("gate_mode") or "serial"),
            trust_mode=str(raw.get("trust_mode") or "standard"),
            sequence=int(raw.get("sequence") or 0),
        )

    def rule_set_key(self) -> str:
        """Deterministic string key for the failed-rule combination."""
        return "|".join(self.failed_rules) if self.failed_rules else "_empty_"


@dataclass(frozen=True)
class FailureCluster:
    """A recurring pattern of gate rejections.

    Attributes
    ----------
    cluster_id:         Deterministic SHA-256 of the cluster's rule_set_key.
    rule_set_key:       Canonical pipe-delimited sorted failed-rule combination.
    failed_rules:       Sorted tuple of rule names in this cluster.
    reason_codes:       Union of all reason_codes seen in member records.
    frequency:          How many rejections match this cluster.
    example_mutation_ids: Up to 5 mutation_ids from member records (for context).
    gate_mode_counts:   Distribution of gate_modes in this cluster.
    trust_mode_counts:  Distribution of trust_modes in this cluster.
    cluster_digest:     SHA-256 of (cluster_id + str(frequency)) for ledger anchoring.
    schema_version:     Miner version for replay compatibility.
    """

    cluster_id: str
    rule_set_key: str
    failed_rules: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    frequency: int
    example_mutation_ids: Tuple[str, ...]
    gate_mode_counts: Dict[str, int]
    trust_mode_counts: Dict[str, int]
    cluster_digest: str
    schema_version: str = CLUSTER_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "rule_set_key": self.rule_set_key,
            "failed_rules": list(self.failed_rules),
            "reason_codes": list(self.reason_codes),
            "frequency": self.frequency,
            "example_mutation_ids": list(self.example_mutation_ids),
            "gate_mode_counts": dict(self.gate_mode_counts),
            "trust_mode_counts": dict(self.trust_mode_counts),
            "cluster_digest": self.cluster_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FailureCluster":
        return cls(
            cluster_id=d["cluster_id"],
            rule_set_key=d["rule_set_key"],
            failed_rules=tuple(d["failed_rules"]),
            reason_codes=tuple(d["reason_codes"]),
            frequency=d["frequency"],
            example_mutation_ids=tuple(d["example_mutation_ids"]),
            gate_mode_counts=d["gate_mode_counts"],
            trust_mode_counts=d["trust_mode_counts"],
            cluster_digest=d["cluster_digest"],
            schema_version=d.get("schema_version", CLUSTER_VERSION),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cluster_id(rule_set_key: str) -> str:
    """Deterministic cluster ID from rule_set_key (CSDL-CLUSTER-0)."""
    return "csdl-" + hashlib.sha256(rule_set_key.encode()).hexdigest()[:16]


def _cluster_digest(cluster_id: str, frequency: int) -> str:
    payload = json.dumps({"cluster_id": cluster_id, "frequency": frequency},
                         sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _jaccard(a: frozenset, b: frozenset) -> float:
    """Jaccard similarity between two frozensets."""
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


# ---------------------------------------------------------------------------
# FailurePatternMiner
# ---------------------------------------------------------------------------


class FailurePatternMiner:
    """Phase 81 gate rejection pattern miner.

    Reads rejection records from a GateDecisionLedger JSONL file and groups
    them into FailureCluster objects by failed-rule combination similarity.

    Determinism guarantee (CSDL-CLUSTER-0):
    Given identical input records, mine() always returns identical clusters
    in identical order. All grouping uses only sorted, deterministic keys.

    Usage
    -----
    miner = FailurePatternMiner(ledger_path=Path("security/ledger/gate_decision_audit.jsonl"))
    clusters = miner.mine()
    """

    def __init__(
        self,
        *,
        ledger_path: Optional[Path] = None,
        min_frequency: int = MIN_CLUSTER_FREQUENCY,
        max_clusters: int = MAX_CLUSTERS_PER_MINE,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ) -> None:
        self._ledger_path = ledger_path
        self._min_freq = min_frequency
        self._max_clusters = max_clusters
        self._sim_threshold = similarity_threshold

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def mine(
        self,
        records: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[FailureCluster]:
        """Mine rejection patterns from ledger records.

        Parameters
        ----------
        records : optional pre-loaded raw record list. If None, reads from
                  self._ledger_path. Providing records directly enables
                  hermetic testing without filesystem dependency.

        Returns
        -------
        Sorted list of FailureCluster objects, highest frequency first.
        Empty list if no rejections meet MIN_CLUSTER_FREQUENCY threshold.

        Invariants enforced: CSDL-CLUSTER-0, CSDL-IMMUTABLE-0, CSDL-MIN-FREQ-0.
        """
        if records is None:
            records = self._load_records()

        rejections = self._extract_rejections(records)
        if not rejections:
            log.info("CSDL: no rejection records found — nothing to mine")
            return []

        raw_clusters = self._group_by_rule_set(rejections)
        merged = self._merge_similar(raw_clusters)
        filtered = [c for c in merged if c.frequency >= self._min_freq]
        sorted_clusters = sorted(
            filtered,
            key=lambda c: (-c.frequency, c.cluster_id),  # deterministic sort
        )
        result = sorted_clusters[: self._max_clusters]
        log.info(
            "CSDL: mined %d clusters from %d rejections (min_freq=%d)",
            len(result), len(rejections), self._min_freq,
        )
        return result

    def mine_summary(
        self, records: Optional[Sequence[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Return a summary dict of the mining run for governance artifacts."""
        clusters = self.mine(records)
        total_records = len(self._load_records() if records is None else records)
        rejections = [r for r in (records or self._load_records())
                      if not (r.get("approved", True))]
        return {
            "schema_version": CLUSTER_VERSION,
            "total_records_analysed": total_records,
            "total_rejections": len(rejections),
            "clusters_found": len(clusters),
            "top_clusters": [c.to_dict() for c in clusters[:5]],
            "min_cluster_frequency": self._min_freq,
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load_records(self) -> List[Dict[str, Any]]:
        """CSDL-IMMUTABLE-0: read-only ledger access."""
        if self._ledger_path is None or not Path(self._ledger_path).exists():
            return []
        records: List[Dict[str, Any]] = []
        try:
            with open(self._ledger_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except OSError as exc:
            log.warning("CSDL: could not read ledger %s: %s", self._ledger_path, exc)
        return records

    def _extract_rejections(
        self, records: Sequence[Dict[str, Any]]
    ) -> List[RejectionRecord]:
        """Extract and normalise rejection records."""
        result: List[RejectionRecord] = []
        for raw in records:
            rec = RejectionRecord.from_raw(raw)
            if rec is not None:
                result.append(rec)
        # Sort by sequence for determinism (CSDL-CLUSTER-0)
        return sorted(result, key=lambda r: r.sequence)

    def _group_by_rule_set(
        self, rejections: List[RejectionRecord]
    ) -> List[FailureCluster]:
        """Group rejections by exact failed-rule set key."""
        groups: Dict[str, List[RejectionRecord]] = defaultdict(list)
        for rec in rejections:
            groups[rec.rule_set_key()].append(rec)

        clusters: List[FailureCluster] = []
        for rule_set_key, members in sorted(groups.items()):  # sorted for determinism
            all_reasons: frozenset = frozenset(
                r for rec in members for r in rec.reason_codes
            )
            gate_counts: Counter = Counter(r.gate_mode for r in members)
            trust_counts: Counter = Counter(r.trust_mode for r in members)
            failed_rules = tuple(sorted(rule_set_key.split("|"))) if rule_set_key != "_empty_" else ()
            cid = _cluster_id(rule_set_key)
            freq = len(members)
            clusters.append(
                FailureCluster(
                    cluster_id=cid,
                    rule_set_key=rule_set_key,
                    failed_rules=failed_rules,
                    reason_codes=tuple(sorted(all_reasons)),
                    frequency=freq,
                    example_mutation_ids=tuple(m.mutation_id for m in members[:5]),
                    gate_mode_counts=dict(gate_counts),
                    trust_mode_counts=dict(trust_counts),
                    cluster_digest=_cluster_digest(cid, freq),
                )
            )
        return clusters

    def _merge_similar(
        self, clusters: List[FailureCluster]
    ) -> List[FailureCluster]:
        """Merge clusters whose failed-rule sets have Jaccard similarity ≥ threshold.

        Produces a stable merge: lower-frequency clusters merge into higher-freq ones.
        CSDL-CLUSTER-0: merge decisions are deterministic — clusters sorted before
        comparison so identical inputs always produce identical merges.
        """
        if not clusters:
            return []

        # Sort by frequency desc then cluster_id asc for deterministic merge order
        ordered = sorted(clusters, key=lambda c: (-c.frequency, c.cluster_id))
        merged: List[FailureCluster] = []
        absorbed: set[str] = set()

        for i, base in enumerate(ordered):
            if base.cluster_id in absorbed:
                continue
            base_set = frozenset(base.failed_rules)
            absorbed_members = [base]

            for j, candidate in enumerate(ordered):
                if j <= i or candidate.cluster_id in absorbed:
                    continue
                cand_set = frozenset(candidate.failed_rules)
                if _jaccard(base_set, cand_set) >= self._sim_threshold:
                    absorbed_members.append(candidate)
                    absorbed.add(candidate.cluster_id)

            if len(absorbed_members) == 1:
                merged.append(base)
            else:
                # Merge: union rules, sum frequencies
                all_rules = frozenset(r for c in absorbed_members for r in c.failed_rules)
                all_reasons = frozenset(r for c in absorbed_members for r in c.reason_codes)
                total_freq = sum(c.frequency for c in absorbed_members)
                merged_gate: Counter = Counter()
                merged_trust: Counter = Counter()
                for c in absorbed_members:
                    merged_gate.update(c.gate_mode_counts)
                    merged_trust.update(c.trust_mode_counts)
                merged_examples = tuple(
                    mid
                    for c in absorbed_members
                    for mid in c.example_mutation_ids
                )[:5]
                merged_rules = tuple(sorted(all_rules))
                new_key = "|".join(merged_rules) or "_merged_"
                cid = _cluster_id(new_key)
                merged.append(
                    FailureCluster(
                        cluster_id=cid,
                        rule_set_key=new_key,
                        failed_rules=merged_rules,
                        reason_codes=tuple(sorted(all_reasons)),
                        frequency=total_freq,
                        example_mutation_ids=merged_examples,
                        gate_mode_counts=dict(merged_gate),
                        trust_mode_counts=dict(merged_trust),
                        cluster_digest=_cluster_digest(cid, total_freq),
                    )
                )
        return merged
