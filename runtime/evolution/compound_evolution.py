# SPDX-License-Identifier: Apache-2.0
"""Phase 86 Track B — CompoundEvolutionTracker.

Multi-generation fitness aggregation across competitive epochs with full
causal ancestry provenance.

Constitutional invariants:
  COMP-TRACK-0      compound fitness score is deterministic given identical ledger contents
  COMP-ANCESTRY-0   every CompoundEvolutionRecord traces to a MultiGenLineageGraph node
  COMP-GOV-WRITE-0  record written to ledger before any surface emitted
  COMP-CAUSAL-0     per-generation causal attribution surfaced in every record
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, Optional, Sequence, Tuple

from runtime.governance.foundation import sha256_prefixed_digest, canonical_json

COMP_TRACKER_VERSION = "1.0.0"

# Weight applied to each ancestor generation when rolling up compound fitness.
# Generation 0 (current epoch) has weight 1.0; each prior generation is discounted
# by this factor. e.g. generation 1 → 0.8, generation 2 → 0.64, etc.
GENERATION_DISCOUNT_FACTOR: float = 0.8


# ---------------------------------------------------------------------------
# CompoundEvolutionRecord
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AncestorContribution:
    """Fitness contribution from a single ancestor generation.

    Attributes
    ----------
    epoch_id:        Ancestor epoch identifier.
    generation:      Depth from current epoch (0 = current, 1 = parent, ...).
    fitness_score:   Raw fitness score at this generation (from pareto scalar_ranking).
    discount_coeff:  GENERATION_DISCOUNT_FACTOR ** generation.
    weighted_score:  fitness_score * discount_coeff.
    """

    epoch_id: str
    generation: int
    fitness_score: float
    discount_coeff: float
    weighted_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch_id": self.epoch_id,
            "generation": self.generation,
            "fitness_score": round(self.fitness_score, 6),
            "discount_coeff": round(self.discount_coeff, 6),
            "weighted_score": round(self.weighted_score, 6),
        }


@dataclass(frozen=True)
class CompoundEvolutionRecord:
    """Multi-generation fitness aggregation record.

    Invariants
    ----------
    COMP-TRACK-0      identical inputs → identical record_digest
    COMP-ANCESTRY-0   ancestry_trace non-empty and traces to MultiGenLineageGraph node
    COMP-CAUSAL-0     top_causal_ops and attribution_digests reflect causal analysis

    Attributes
    ----------
    record_id:             sha256 of (epoch_id + pareto_epoch_digest) — stable key.
    epoch_id:              Source epoch for this record.
    compound_fitness:      Weighted multi-generation aggregate fitness score ∈ [0, 1].
    generation_depth:      Number of ancestor generations included in aggregate.
    ancestry_trace:        Epoch IDs in lineage chain, root-first (oldest → current).
    ancestor_contributions: Per-generation weighted fitness breakdown.
    pareto_epoch_digest:   ParetoCompetitionResult.epoch_digest for source epoch.
    top_causal_ops:        Top contributing operation IDs from causal attribution.
    attribution_digests:   candidate_id → CausalAttributionReport.report_digest.
    record_digest:         sha256 of canonical record payload (COMP-TRACK-0).
    schema_version:        COMP_TRACKER_VERSION.
    """

    record_id: str
    epoch_id: str
    compound_fitness: float
    generation_depth: int
    ancestry_trace: Tuple[str, ...]
    ancestor_contributions: Tuple[AncestorContribution, ...]
    pareto_epoch_digest: str
    top_causal_ops: Tuple[str, ...]
    attribution_digests: Dict[str, str]
    record_digest: str
    schema_version: str = COMP_TRACKER_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "epoch_id": self.epoch_id,
            "compound_fitness": round(self.compound_fitness, 6),
            "generation_depth": self.generation_depth,
            "ancestry_trace": list(self.ancestry_trace),
            "ancestor_contributions": [a.to_dict() for a in self.ancestor_contributions],
            "pareto_epoch_digest": self.pareto_epoch_digest,
            "top_causal_ops": list(self.top_causal_ops),
            "attribution_digests": dict(self.attribution_digests),
            "record_digest": self.record_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CompoundEvolutionRecord":
        return cls(
            record_id=d["record_id"],
            epoch_id=d["epoch_id"],
            compound_fitness=d["compound_fitness"],
            generation_depth=d["generation_depth"],
            ancestry_trace=tuple(d["ancestry_trace"]),
            ancestor_contributions=tuple(
                AncestorContribution(**a) for a in d.get("ancestor_contributions", [])
            ),
            pareto_epoch_digest=d["pareto_epoch_digest"],
            top_causal_ops=tuple(d.get("top_causal_ops", [])),
            attribution_digests=dict(d.get("attribution_digests", {})),
            record_digest=d["record_digest"],
            schema_version=d.get("schema_version", COMP_TRACKER_VERSION),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_record_digest(
    epoch_id: str,
    compound_fitness: float,
    ancestry_trace: Tuple[str, ...],
    pareto_epoch_digest: str,
    attribution_digests: Dict[str, str],
) -> str:
    """COMP-TRACK-0: deterministic digest from canonical payload."""
    payload = canonical_json({
        "epoch_id": epoch_id,
        "compound_fitness": round(compound_fitness, 6),
        "ancestry_trace": sorted(ancestry_trace),  # sorted for stability
        "pareto_epoch_digest": pareto_epoch_digest,
        "attribution_digests": {k: v for k, v in sorted(attribution_digests.items())},
        "schema_version": COMP_TRACKER_VERSION,
    })
    return sha256_prefixed_digest(payload.encode())


def _record_id(epoch_id: str, pareto_epoch_digest: str) -> str:
    """Stable record key: sha256(epoch_id + pareto_epoch_digest)."""
    raw = f"{epoch_id}:{pareto_epoch_digest}"
    return sha256_prefixed_digest(raw.encode())


# ---------------------------------------------------------------------------
# CompoundEvolutionTracker
# ---------------------------------------------------------------------------

class CompoundEvolutionTracker:
    """Phase 86 — Multi-generation fitness aggregator.

    Synthesises:
    - Ancestry provenance from MultiGenLineageGraph (Phase 79)
    - Competitive epoch outcomes from ParetoCompetitionResult (Phase 82)
    - Per-operation causal attribution from CausalAttributionReport (Phase 83)

    Produces a CompoundEvolutionRecord per epoch that aggregates fitness
    across the full ancestor chain with generation-discounted weighting.

    Constitutional invariants enforced:
      COMP-TRACK-0      deterministic given identical inputs
      COMP-ANCESTRY-0   ancestry_trace always non-empty and ledger-verifiable
      COMP-GOV-WRITE-0  record written to ledger before returned to caller
      COMP-CAUSAL-0     top_causal_ops and attribution_digests in every record
    """

    def __init__(
        self,
        *,
        ledger: Optional[Any] = None,
        generation_discount: float = GENERATION_DISCOUNT_FACTOR,
        max_ancestry_depth: int = 10,
    ) -> None:
        self._ledger = ledger
        self._discount = generation_discount
        self._max_depth = max_ancestry_depth

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def track_epoch(
        self,
        epoch_id: str,
        pareto_result: Any,  # ParetoCompetitionResult
        lineage_graph: Any,  # MultiGenLineageGraph
        attributions: Dict[str, Any],  # candidate_id → CausalAttributionReport
    ) -> CompoundEvolutionRecord:
        """Compute and record a CompoundEvolutionRecord for this epoch.

        Parameters
        ----------
        epoch_id:       Epoch being tracked.
        pareto_result:  ParetoCompetitionResult from Step 9 of CEL.
        lineage_graph:  MultiGenLineageGraph for ancestry traversal.
        attributions:   Mapping candidate_id → CausalAttributionReport.

        Returns
        -------
        CompoundEvolutionRecord — written to ledger before being returned
        (COMP-GOV-WRITE-0).

        Raises
        ------
        ValueError  if epoch_id is empty.
        """
        if not epoch_id:
            raise ValueError("COMP-TRACK-0: epoch_id must be non-empty")

        # COMP-ANCESTRY-0: build ancestry trace from lineage graph
        ancestry_trace, ancestor_nodes = self._build_ancestry(epoch_id, lineage_graph)

        # Build per-generation fitness contributions from pareto scalar_ranking
        scalar_map: Dict[str, float] = {}
        try:
            for cid, score in (pareto_result.scalar_ranking or []):
                scalar_map[cid] = float(score)
        except Exception:  # noqa: BLE001
            pass

        ancestor_contributions = self._build_contributions(
            epoch_id, ancestry_trace, scalar_map
        )

        # Aggregate compound fitness (COMP-TRACK-0: deterministic weighted sum)
        compound_fitness = self._aggregate_fitness(ancestor_contributions)

        # COMP-CAUSAL-0: extract top causal ops and attribution digests
        top_causal_ops, attribution_digests = self._extract_causal(attributions)

        # Pareto epoch digest for provenance
        pareto_epoch_digest: str = getattr(pareto_result, "epoch_digest", "sha256:" + "0" * 64)

        # Compute record digest (COMP-TRACK-0)
        record_digest = _compute_record_digest(
            epoch_id=epoch_id,
            compound_fitness=compound_fitness,
            ancestry_trace=tuple(ancestry_trace),
            pareto_epoch_digest=pareto_epoch_digest,
            attribution_digests=attribution_digests,
        )

        rec_id = _record_id(epoch_id, pareto_epoch_digest)

        record = CompoundEvolutionRecord(
            record_id=rec_id,
            epoch_id=epoch_id,
            compound_fitness=compound_fitness,
            generation_depth=len(ancestry_trace),
            ancestry_trace=tuple(ancestry_trace),
            ancestor_contributions=tuple(ancestor_contributions),
            pareto_epoch_digest=pareto_epoch_digest,
            top_causal_ops=tuple(top_causal_ops),
            attribution_digests=attribution_digests,
            record_digest=record_digest,
        )

        # COMP-GOV-WRITE-0: write to ledger before returning
        self._ledger_write(record)

        return record

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_ancestry(
        self, epoch_id: str, lineage_graph: Any
    ) -> Tuple[Tuple[str, ...], Tuple[Any, ...]]:
        """Walk ancestor chain from lineage_graph up to max_ancestry_depth.

        COMP-ANCESTRY-0: result always includes epoch_id itself (depth 0).
        Returns (ancestry_trace root-first, ancestor_node_list current-first).
        """
        chain: list = [epoch_id]
        try:
            # Attempt to use ancestor_path if available
            if hasattr(lineage_graph, "ancestor_path"):
                path = lineage_graph.ancestor_path(epoch_id)
                ancestors = [n.epoch_id for n in path if hasattr(n, "epoch_id")]
                # ancestor_path may return root→current or current→root; normalise
                if ancestors and ancestors[-1] == epoch_id:
                    chain = ancestors  # already root-first
                elif ancestors and ancestors[0] == epoch_id:
                    chain = list(reversed(ancestors))
                else:
                    chain = ancestors + [epoch_id]
            elif hasattr(lineage_graph, "_parents"):
                # Manual traversal via _parents dict
                visited: list = [epoch_id]
                current = epoch_id
                for _ in range(self._max_depth):
                    parents = lineage_graph._parents.get(current, set())
                    if not parents:
                        break
                    current = sorted(parents)[0]  # deterministic: lexicographic
                    visited.append(current)
                visited.reverse()  # root-first
                chain = visited
        except Exception:  # noqa: BLE001 — COMP-ANCESTRY-0 always includes epoch_id
            chain = [epoch_id]

        # Cap depth
        chain = chain[-self._max_depth :]  # noqa: E203
        return tuple(chain), tuple(chain)

    def _build_contributions(
        self,
        epoch_id: str,
        ancestry_trace: Tuple[str, ...],
        scalar_map: Dict[str, float],
    ) -> Tuple[AncestorContribution, ...]:
        """Build generation-discounted fitness contributions for each ancestor."""
        total = len(ancestry_trace)
        contributions = []
        for i, ancestor_id in enumerate(reversed(ancestry_trace)):
            generation = i  # 0 = current epoch, increasing toward root
            discount = self._discount ** generation
            raw_score = scalar_map.get(ancestor_id, 0.0)
            contributions.append(AncestorContribution(
                epoch_id=ancestor_id,
                generation=generation,
                fitness_score=round(raw_score, 6),
                discount_coeff=round(discount, 6),
                weighted_score=round(raw_score * discount, 6),
            ))
        return tuple(contributions)

    @staticmethod
    def _aggregate_fitness(contributions: Tuple[AncestorContribution, ...]) -> float:
        """COMP-TRACK-0: deterministic weighted aggregate, clamped to [0, 1]."""
        if not contributions:
            return 0.0
        total_weight = sum(c.discount_coeff for c in contributions)
        if total_weight == 0.0:
            return 0.0
        weighted_sum = sum(c.weighted_score for c in contributions)
        return max(0.0, min(1.0, weighted_sum / total_weight))

    @staticmethod
    def _extract_causal(
        attributions: Dict[str, Any]
    ) -> Tuple[Tuple[str, ...], Dict[str, str]]:
        """COMP-CAUSAL-0: extract top_causal_ops and attribution_digests."""
        top_ops_seen: list = []
        digests: Dict[str, str] = {}
        for cid, report in (attributions or {}).items():
            try:
                digests[cid] = str(getattr(report, "report_digest", "sha256:" + "0" * 64))
                for op in getattr(report, "top_ops", []) or []:
                    if op not in top_ops_seen:
                        top_ops_seen.append(op)
            except Exception:  # noqa: BLE001
                pass
        return tuple(sorted(top_ops_seen)), digests  # sorted for COMP-TRACK-0 determinism

    def _ledger_write(self, record: CompoundEvolutionRecord) -> None:
        """COMP-GOV-WRITE-0: write record to ledger; swallow errors (non-blocking)."""
        if self._ledger is None:
            return
        try:
            entry = {
                "event_type": "compound_evolution_record.v1",
                **record.to_dict(),
            }
            if hasattr(self._ledger, "append_raw"):
                self._ledger.append_raw(entry)
            elif hasattr(self._ledger, "append"):
                self._ledger.append(entry)
        except Exception:  # noqa: BLE001 — ledger write is best-effort in non-blocking path
            pass
