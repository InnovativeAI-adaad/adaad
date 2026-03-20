# SPDX-License-Identifier: Apache-2.0
"""Phase 83 — MutationAblator.

Decomposes a MutationCandidate into its constituent logical operations
and produces subsets for ablation-based causal fitness attribution.

Each "operation" is an independently meaningful unit of change:
  - For candidates with python_content: AST-level structural operations
    extracted by diffing before/after source trees.
  - For candidates without source: named field dimensions from
    MutationCandidate (expected_gain, risk_score, complexity, coverage_delta).

Constitutional Invariants
─────────────────────────
  CFAE-0      Causal attribution is advisory. Results never override
              GovernanceGate decisions or block mutation promotion.
  CFAE-DET-0  Ablation subsets are generated deterministically. Identical
              MutationCandidate inputs produce identical op sets and subsets.
  CFAE-BOUND-0 Attribution scores are bounded in [-1.0, 1.0]. Positive =
              op contributed gain; negative = op contributed loss.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

ABLATOR_VERSION: str = "83.0"


# ---------------------------------------------------------------------------
# MutationOperation — atomic unit of change
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MutationOperation:
    """One atomic, independently meaningful mutation operation.

    Attributes
    ----------
    op_id:       Deterministic ID: SHA-256[:12] of (candidate_id + op_key).
    op_key:      Stable string key identifying the operation type + location.
    op_type:     Category: "ast_node_add" | "ast_node_remove" | "ast_node_modify"
                 | "field_delta" | "import_change" | "complexity_change".
    description: Human-readable description of the operation.
    weight:      Relative importance estimate [0.0, 1.0] for Shapley sampling.
    metadata:    Arbitrary structured metadata for downstream consumers.
    """

    op_id: str
    op_key: str
    op_type: str
    description: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_id": self.op_id,
            "op_key": self.op_key,
            "op_type": self.op_type,
            "description": self.description,
            "weight": self.weight,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MutationOperation":
        return cls(
            op_id=d["op_id"],
            op_key=d["op_key"],
            op_type=d["op_type"],
            description=d["description"],
            weight=d.get("weight", 1.0),
            metadata=d.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _op_id(candidate_id: str, op_key: str) -> str:
    """CFAE-DET-0: deterministic op_id from candidate_id + op_key."""
    payload = f"{candidate_id}|{op_key}"
    return "op-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def _ast_node_type(node: ast.AST) -> str:
    return type(node).__name__


def _extract_ast_ops(
    candidate_id: str,
    before_source: str,
    after_source: str,
) -> List[MutationOperation]:
    """Extract AST-level operations by diffing before/after source trees.

    CFAE-DET-0: deterministic — ast.walk order is stable for identical sources.
    Falls back to empty list on parse error (graceful degradation).
    """
    ops: List[MutationOperation] = []
    try:
        before_tree = ast.parse(before_source) if before_source.strip() else None
        after_tree = ast.parse(after_source) if after_source.strip() else None
    except SyntaxError:
        return []

    # Count node types before and after
    def _node_counts(tree: Optional[ast.AST]) -> Dict[str, int]:
        if tree is None:
            return {}
        counts: Dict[str, int] = {}
        for node in ast.walk(tree):
            t = _ast_node_type(node)
            counts[t] = counts.get(t, 0) + 1
        return counts

    before_counts = _node_counts(before_tree)
    after_counts = _node_counts(after_tree)

    all_types = sorted(set(list(before_counts.keys()) + list(after_counts.keys())))
    for node_type in all_types:
        b = before_counts.get(node_type, 0)
        a = after_counts.get(node_type, 0)
        delta = a - b
        if delta == 0:
            continue
        op_type = "ast_node_add" if delta > 0 else "ast_node_remove"
        op_key = f"ast_{node_type}_delta_{delta:+d}"
        weight = min(1.0, abs(delta) / 10.0)  # normalise weight
        ops.append(MutationOperation(
            op_id=_op_id(candidate_id, op_key),
            op_key=op_key,
            op_type=op_type,
            description=f"{node_type}: {delta:+d} nodes",
            weight=weight,
            metadata={"node_type": node_type, "before": b, "after": a, "delta": delta},
        ))

    # Import surface delta as a named op
    before_imports = sum(
        before_counts.get(t, 0) for t in ("Import", "ImportFrom")
    )
    after_imports = sum(
        after_counts.get(t, 0) for t in ("Import", "ImportFrom")
    )
    import_delta = after_imports - before_imports
    if import_delta != 0:
        op_key = f"import_surface_delta_{import_delta:+d}"
        ops.append(MutationOperation(
            op_id=_op_id(candidate_id, op_key),
            op_key=op_key,
            op_type="import_change",
            description=f"Import surface: {import_delta:+d}",
            weight=0.5,
            metadata={"import_delta": import_delta},
        ))

    return sorted(ops, key=lambda o: o.op_key)  # CFAE-DET-0: sorted for determinism


def _extract_field_ops(
    candidate_id: str,
    candidate_dict: Dict[str, Any],
) -> List[MutationOperation]:
    """Extract field-level operations from MutationCandidate numeric fields.

    Used when python_content is unavailable. Each significant field delta
    becomes a named MutationOperation. CFAE-DET-0: sorted output.
    """
    ops: List[MutationOperation] = []
    tracked_fields = [
        ("expected_gain", "fitness"),
        ("risk_score", "risk"),
        ("complexity", "complexity"),
        ("coverage_delta", "coverage"),
        ("strategic_horizon", "strategy"),
        ("forecast_roi", "roi"),
    ]
    for field_name, category in tracked_fields:
        val = candidate_dict.get(field_name)
        if val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if abs(fval) < 1e-6:
            continue
        op_key = f"field_{field_name}_{fval:.4f}"
        ops.append(MutationOperation(
            op_id=_op_id(candidate_id, op_key),
            op_key=op_key,
            op_type="field_delta",
            description=f"{field_name}={fval:.4f}",
            weight=min(1.0, abs(fval)),
            metadata={"field": field_name, "value": fval, "category": category},
        ))
    return sorted(ops, key=lambda o: o.op_key)


# ---------------------------------------------------------------------------
# MutationAblator
# ---------------------------------------------------------------------------


class MutationAblator:
    """Phase 83 mutation decomposition and ablation subset generator.

    Decomposes a MutationCandidate into MutationOperation objects and
    generates subsets for Shapley-approximation causal attribution.

    Shapley approximation strategy (CFAE-DET-0):
    Rather than 2^n full enumeration, uses a deterministic sampling
    strategy: all single-op subsets + all (n-1)-op subsets ("leave-one-out").
    This gives exact Shapley values for n ≤ 6 and a stable approximation
    for larger sets. Order of subsets is always sorted for determinism.

    Usage
    -----
    ablator = MutationAblator()
    ops, subsets = ablator.decompose(candidate)
    # For each subset, re-score with FitnessOrchestrator to get attribution.
    """

    def __init__(self, max_ops: int = 20) -> None:
        """
        Parameters
        ----------
        max_ops : Maximum number of operations to extract (caps ablation cost).
        """
        self._max_ops = max_ops

    def decompose(
        self,
        candidate_id: str,
        *,
        python_content: Optional[str] = None,
        before_source: Optional[str] = None,
        candidate_fields: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[MutationOperation], List[FrozenSet[str]]]:
        """Decompose a mutation into operations and Shapley-approximation subsets.

        Parameters
        ----------
        candidate_id:     Unique candidate identifier.
        python_content:   After-mutation Python source (preferred).
        before_source:    Before-mutation Python source (for AST diff).
        candidate_fields: MutationCandidate field dict (fallback when no source).

        Returns
        -------
        (ops, subsets) where:
          ops     — List[MutationOperation] extracted from the candidate.
          subsets — List[FrozenSet[str]] of op_id sets for ablation scoring.
                    Each subset represents "score the candidate with only
                    these operations applied."
        """
        ops = self._extract_ops(
            candidate_id,
            python_content=python_content,
            before_source=before_source,
            candidate_fields=candidate_fields,
        )
        ops = ops[: self._max_ops]  # cap
        subsets = self._generate_subsets(ops)
        log.debug(
            "CFAE: decomposed candidate %s into %d ops, %d subsets",
            candidate_id, len(ops), len(subsets),
        )
        return ops, subsets

    def generate_ablated_contexts(
        self,
        base_context: Dict[str, Any],
        ops: List[MutationOperation],
        subsets: List[FrozenSet[str]],
    ) -> List[Tuple[FrozenSet[str], Dict[str, Any]]]:
        """Generate fitness contexts for each ablation subset.

        Each context is the base_context with objective dimensions modified
        proportionally to the included operations' weights.

        Returns list of (subset, modified_context) pairs for re-scoring.
        CFAE-DET-0: returned in deterministic subset order.
        """
        if not ops:
            return [(frozenset(), dict(base_context))]

        total_weight = sum(o.weight for o in ops) or 1.0
        op_weight_map = {o.op_id: o.weight for o in ops}

        result: List[Tuple[FrozenSet[str], Dict[str, Any]]] = []
        for subset in subsets:
            included_weight = sum(op_weight_map.get(oid, 0.0) for oid in subset)
            fraction = included_weight / total_weight

            # Scale each fitness dimension by the included fraction
            ctx = dict(base_context)
            for key in (
                "correctness_score", "efficiency_score",
                "policy_compliance_score", "goal_alignment_score",
                "simulated_market_score",
            ):
                original = float(ctx.get(key, 0.5))
                # Interpolate between 0.5 (neutral baseline) and original
                ctx[key] = 0.5 + (original - 0.5) * fraction
            result.append((subset, ctx))
        return result

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _extract_ops(
        self,
        candidate_id: str,
        *,
        python_content: Optional[str],
        before_source: Optional[str],
        candidate_fields: Optional[Dict[str, Any]],
    ) -> List[MutationOperation]:
        # Prefer AST-level ops when source is available
        if python_content and python_content.strip():
            before = before_source or ""
            ast_ops = _extract_ast_ops(candidate_id, before, python_content)
            if ast_ops:
                return ast_ops

        # Fall back to field-level ops
        if candidate_fields:
            return _extract_field_ops(candidate_id, candidate_fields)

        # No information available — return single synthetic op
        op_key = f"opaque_{candidate_id}"
        return [MutationOperation(
            op_id=_op_id(candidate_id, op_key),
            op_key=op_key,
            op_type="field_delta",
            description="Opaque mutation (no source or fields available)",
            weight=1.0,
            metadata={"opaque": True},
        )]

    def _generate_subsets(
        self, ops: List[MutationOperation]
    ) -> List[FrozenSet[str]]:
        """Generate Shapley-approximation subsets.

        CFAE-DET-0: subsets are generated in deterministic sorted order.

        Strategy:
          n ≤ 8:  all 2^n subsets (exact Shapley)
          n > 8:  single-op + leave-one-out + full set (O(n) approximation)
        """
        if not ops:
            return [frozenset()]

        ids = tuple(sorted(o.op_id for o in ops))  # sorted for determinism
        n = len(ids)

        if n <= 8:
            # Exact: all subsets
            subsets: List[FrozenSet[str]] = []
            for mask in range(1, 1 << n):
                subset = frozenset(ids[i] for i in range(n) if mask & (1 << i))
                subsets.append(subset)
            return sorted(subsets, key=lambda s: (len(s), sorted(s)))

        # Approximation for large n
        subsets = []
        # All single-op subsets (marginal contributions)
        for oid in ids:
            subsets.append(frozenset([oid]))
        # All leave-one-out subsets (sensitivity)
        for i, oid in enumerate(ids):
            loo = frozenset(oid2 for oid2 in ids if oid2 != oid)
            subsets.append(loo)
        # Full set
        subsets.append(frozenset(ids))
        # Deduplicate while preserving deterministic order
        seen: set = set()
        result: List[FrozenSet[str]] = []
        for s in sorted(subsets, key=lambda s: (len(s), sorted(s))):
            key = tuple(sorted(s))
            if key not in seen:
                seen.add(key)
                result.append(s)
        return result
