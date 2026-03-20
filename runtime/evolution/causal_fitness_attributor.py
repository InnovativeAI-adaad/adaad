# SPDX-License-Identifier: Apache-2.0
"""Phase 83 — CausalFitnessAttributor.

Shapley-value-approximation engine that attributes fitness gain/loss to
individual mutation operations.

Answers: "Of the total fitness score for this mutation, which AST operations
(or field deltas) actually caused the improvement?"

Architecture
────────────
1. MutationAblator decomposes the candidate into MutationOperations.
2. For each Shapley-approximation subset, FitnessOrchestrator scores
   the ablated context.
3. CausalFitnessAttributor aggregates subset scores into per-operation
   attribution values using marginal contribution estimation.
4. CausalAttributionReport is written to the ledger for downstream use
   by Phase 86 (OperatorCoevolution) and Phase 87 (RoleSpecialization).

Constitutional Invariants
─────────────────────────
  CFAE-0       Attribution is advisory. Never overrides GovernanceGate.
  CFAE-DET-0   Identical inputs → identical attribution scores.
  CFAE-BOUND-0 All attribution scores bounded in [-1.0, 1.0].
  CFAE-LEDGER-0 CausalAttributionReport written to LineageLedgerV2 when
               a ledger is injected. Writing never blocks attribution.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from runtime.evolution.mutation_ablator import MutationAblator, MutationOperation

log = logging.getLogger(__name__)

CFAE_VERSION: str = "83.0"


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationAttribution:
    """Causal attribution score for one MutationOperation.

    Attributes
    ----------
    op_id:              Source MutationOperation.op_id.
    op_key:             Source MutationOperation.op_key.
    op_type:            Source MutationOperation.op_type.
    attribution_score:  Estimated marginal fitness contribution [-1.0, 1.0].
                        Positive = contributed gain; negative = contributed loss.
    confidence:         [0.0, 1.0] — higher when more subsets were sampled.
    tag:                "CAUSAL-HIGH" | "CAUSAL-MED" | "CAUSAL-LOW" | "CAUSAL-NEGATIVE".
    """

    op_id: str
    op_key: str
    op_type: str
    attribution_score: float
    confidence: float
    tag: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_id": self.op_id,
            "op_key": self.op_key,
            "op_type": self.op_type,
            "attribution_score": round(self.attribution_score, 6),
            "confidence": round(self.confidence, 4),
            "tag": self.tag,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OperationAttribution":
        return cls(**d)


@dataclass(frozen=True)
class CausalAttributionReport:
    """Full causal attribution report for one mutation candidate.

    Attributes
    ----------
    candidate_id:       Source candidate.
    baseline_score:     Full-candidate FitnessOrchestrator score (no ablation).
    attributions:       Per-operation attribution list, sorted by score desc.
    top_ops:            op_ids of CAUSAL-HIGH operations (top contributors).
    negative_ops:       op_ids of CAUSAL-NEGATIVE operations (detractors).
    total_ops_analysed: Number of operations decomposed.
    subsets_evaluated:  Number of ablation subsets scored.
    report_digest:      SHA-256 of canonical report payload.
    schema_version:     CFAE version tag.
    """

    candidate_id: str
    baseline_score: float
    attributions: Tuple[OperationAttribution, ...]
    top_ops: Tuple[str, ...]
    negative_ops: Tuple[str, ...]
    total_ops_analysed: int
    subsets_evaluated: int
    report_digest: str
    schema_version: str = CFAE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "baseline_score": round(self.baseline_score, 6),
            "attributions": [a.to_dict() for a in self.attributions],
            "top_ops": list(self.top_ops),
            "negative_ops": list(self.negative_ops),
            "total_ops_analysed": self.total_ops_analysed,
            "subsets_evaluated": self.subsets_evaluated,
            "report_digest": self.report_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CausalAttributionReport":
        return cls(
            candidate_id=d["candidate_id"],
            baseline_score=d["baseline_score"],
            attributions=tuple(OperationAttribution.from_dict(a) for a in d["attributions"]),
            top_ops=tuple(d["top_ops"]),
            negative_ops=tuple(d["negative_ops"]),
            total_ops_analysed=d["total_ops_analysed"],
            subsets_evaluated=d["subsets_evaluated"],
            report_digest=d["report_digest"],
            schema_version=d.get("schema_version", CFAE_VERSION),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HIGH_THRESHOLD = 0.15
_NEGATIVE_THRESHOLD = -0.05


def _tag(score: float) -> str:
    if score >= _HIGH_THRESHOLD:
        return "CAUSAL-HIGH"
    if score >= 0.05:
        return "CAUSAL-MED"
    if score >= 0.0:
        return "CAUSAL-LOW"
    return "CAUSAL-NEGATIVE"


def _report_digest(candidate_id: str, attributions: Sequence[OperationAttribution]) -> str:
    payload = json.dumps(
        {
            "candidate_id": candidate_id,
            "attributions": sorted(
                [{"op_id": a.op_id, "score": round(a.attribution_score, 6)} for a in attributions],
                key=lambda x: x["op_id"],
            ),
        },
        sort_keys=True, separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    """CFAE-BOUND-0: clamp attribution to [-1.0, 1.0]."""
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# CausalFitnessAttributor
# ---------------------------------------------------------------------------


class CausalFitnessAttributor:
    """Phase 83 causal fitness attribution engine.

    Uses MutationAblator for decomposition and FitnessOrchestrator for
    subset scoring. Estimates per-operation Shapley marginal contributions.

    CFAE-0: results are advisory. GovernanceGate is never invoked or modified.
    CFAE-DET-0: deterministic for identical inputs (no randomness).
    """

    def __init__(
        self,
        *,
        fitness_orchestrator: Optional[Any] = None,
        ledger: Optional[Any] = None,
        max_ops: int = 20,
    ) -> None:
        if fitness_orchestrator is None:
            from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
            fitness_orchestrator = FitnessOrchestrator()
        self._orchestrator = fitness_orchestrator
        self._ledger = ledger
        self._ablator = MutationAblator(max_ops=max_ops)

    def attribute(
        self,
        candidate_id: str,
        base_fitness_context: Dict[str, Any],
        *,
        python_content: Optional[str] = None,
        before_source: Optional[str] = None,
        candidate_fields: Optional[Dict[str, Any]] = None,
    ) -> CausalAttributionReport:
        """Compute causal attribution for a mutation candidate.

        Parameters
        ----------
        candidate_id:          Unique candidate identifier.
        base_fitness_context:  Full fitness context dict for FitnessOrchestrator.
        python_content:        After-mutation Python source (preferred).
        before_source:         Before-mutation Python source (for AST diff).
        candidate_fields:      MutationCandidate field dict (fallback).

        Returns
        -------
        CausalAttributionReport with per-operation scores and tags.

        CFAE-0: advisory only.
        CFAE-DET-0: deterministic for identical inputs.
        CFAE-BOUND-0: all scores in [-1.0, 1.0].
        """
        # Step 1 — Baseline score (full candidate)
        baseline_result = self._orchestrator.score(base_fitness_context)
        baseline_score = float(baseline_result.total_score)

        # Step 2 — Decompose into operations
        ops, subsets = self._ablator.decompose(
            candidate_id,
            python_content=python_content,
            before_source=before_source,
            candidate_fields=candidate_fields,
        )

        if not ops:
            return self._trivial_report(candidate_id, baseline_score)

        # Step 3 — Score all ablation subsets
        ablated_contexts = self._ablator.generate_ablated_contexts(
            base_fitness_context, ops, subsets
        )
        subset_scores: Dict[Tuple[str, ...], float] = {}
        for subset_fs, ctx in ablated_contexts:
            key = tuple(sorted(subset_fs))
            result = self._orchestrator.score(ctx)
            subset_scores[key] = float(result.total_score)

        log.debug(
            "CFAE: candidate=%s ops=%d subsets_scored=%d baseline=%.4f",
            candidate_id, len(ops), len(subset_scores), baseline_score,
        )

        # Step 4 — Compute marginal contributions (Shapley approximation)
        attributions = self._compute_attributions(ops, subset_scores, baseline_score)

        # Step 5 — Build report
        top_ops = tuple(
            a.op_id for a in attributions if a.tag == "CAUSAL-HIGH"
        )
        negative_ops = tuple(
            a.op_id for a in attributions if a.tag == "CAUSAL-NEGATIVE"
        )
        digest = _report_digest(candidate_id, attributions)
        report = CausalAttributionReport(
            candidate_id=candidate_id,
            baseline_score=baseline_score,
            attributions=tuple(attributions),
            top_ops=top_ops,
            negative_ops=negative_ops,
            total_ops_analysed=len(ops),
            subsets_evaluated=len(subset_scores),
            report_digest=digest,
        )

        # Step 6 — Write to ledger (CFAE-LEDGER-0, non-blocking)
        if self._ledger is not None:
            self._write_ledger(report)

        return report

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _compute_attributions(
        self,
        ops: List[MutationOperation],
        subset_scores: Dict[Tuple[str, ...], float],
        baseline_score: float,
    ) -> List[OperationAttribution]:
        """Estimate marginal contribution for each operation.

        For each op_id, marginal contribution = average over all subsets
        containing that op_id of:
            score(subset) - score(subset minus op_id)

        When the leave-one-out subset exists: uses it.
        When only single-op subsets exist: uses (single_score - 0.5) as proxy.
        CFAE-DET-0: deterministic; CFAE-BOUND-0: clamped to [-1.0, 1.0].
        """
        attributions: List[OperationAttribution] = []
        op_ids = [o.op_id for o in ops]

        for op in ops:
            marginals: List[float] = []

            # Collect all subsets containing this op_id
            containing = [
                k for k in subset_scores if op.op_id in k
            ]
            for key in containing:
                # Subset without this op
                without_key = tuple(sorted(oid for oid in key if oid != op.op_id))
                score_with = subset_scores[key]
                score_without = subset_scores.get(without_key, 0.5)
                marginals.append(score_with - score_without)

            if not marginals:
                # No subset data — fallback: use single-op score vs neutral baseline
                single_key = (op.op_id,)
                single_score = subset_scores.get(single_key, 0.5)
                marginals = [single_score - 0.5]

            raw_attribution = sum(marginals) / len(marginals)
            bounded = _clamp(raw_attribution)
            confidence = min(1.0, len(marginals) / max(1, len(op_ids)))

            attributions.append(OperationAttribution(
                op_id=op.op_id,
                op_key=op.op_key,
                op_type=op.op_type,
                attribution_score=bounded,
                confidence=confidence,
                tag=_tag(bounded),
            ))

        # Sort: highest attribution first (deterministic: secondary sort by op_id)
        return sorted(attributions, key=lambda a: (-a.attribution_score, a.op_id))

    def _trivial_report(
        self, candidate_id: str, baseline_score: float
    ) -> CausalAttributionReport:
        """Return a minimal report when no ops can be extracted."""
        return CausalAttributionReport(
            candidate_id=candidate_id,
            baseline_score=baseline_score,
            attributions=(),
            top_ops=(),
            negative_ops=(),
            total_ops_analysed=0,
            subsets_evaluated=0,
            report_digest=_report_digest(candidate_id, []),
        )

    def _write_ledger(self, report: CausalAttributionReport) -> None:
        """CFAE-LEDGER-0: write report to ledger (non-blocking)."""
        try:
            self._ledger.append_event(
                "CausalAttributionReport",
                {
                    "candidate_id": report.candidate_id,
                    "baseline_score": report.baseline_score,
                    "total_ops": report.total_ops_analysed,
                    "top_ops": list(report.top_ops),
                    "negative_ops": list(report.negative_ops),
                    "report_digest": report.report_digest,
                    "schema_version": CFAE_VERSION,
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("CFAE-LEDGER-0: ledger write failed (non-blocking): %s", exc)
