# SPDX-License-Identifier: Apache-2.0
"""INNOV-09 — Aesthetic Fitness Signal (AFIT).

Phase 93 introduces a fitness dimension measuring code readability, naming
quality, and structural clarity — the first autonomous evolution system to
treat code aesthetics as a first-class, constitutionally-bounded fitness
signal.

Rationale
─────────
Technical debt is measurable. A system that optimises only for test coverage
and performance will systematically accumulate cognitive complexity that makes
future mutations harder and audit trails less readable. AFIT captures five
orthogonal readability dimensions from AST analysis and produces a composite
aesthetic score that feeds into FitnessEngineV2 at 5% weight initially —
rising as EpistemicDecay reduces confidence in other signals.

Five Sub-Signals
────────────────
  1. function_length_score   — avg function body length; shorter is cleaner
  2. name_entropy_score      — variable/arg name informativeness (entropy proxy)
  3. nesting_depth_score     — avg max nesting depth per function; shallower is better
  4. comment_ratio_score     — comment density relative to cyclomatic complexity
  5. cyclomatic_score        — inverse of avg cyclomatic complexity per function

Constitutional Invariants
─────────────────────────
  AFIT-0        AestheticFitnessScorer.score() MUST never raise an unhandled
                exception. Any parse or runtime failure MUST return a fallback
                AestheticFitnessReport with score=0.5 and fallback_used=True.

  AFIT-DETERM-0 Identical source string → identical AestheticFitnessReport.
                No datetime.now(), random, or uuid4() anywhere in the scoring
                path.

  AFIT-BOUND-0  All sub-scores MUST be in [0.0, 1.0] before composite
                weighting. Composite score MUST be in [0.0, 1.0].

  AFIT-WEIGHT-0 The aesthetic_fitness weight in FitnessConfig MUST be in
                [0.05, 0.30]. Below 0.05 is noise; above 0.30 over-weights
                style over correctness.

AFIT Version: 93.0
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Sequence

AFIT_VERSION: str = "93.0"

# ---------------------------------------------------------------------------
# Normalisation constants
# ---------------------------------------------------------------------------
_MAX_FUNC_LINES:      int   = 60    # functions longer than this score 0
_IDEAL_FUNC_LINES:    int   = 15    # functions this long score 1.0
_MAX_NESTING:         int   = 6     # nesting beyond this scores 0
_MAX_CYCLOMATIC:      int   = 20    # cyclomatic beyond this scores 0
_MIN_NAME_LEN:        int   = 3     # names shorter than this are "low entropy"
_COMMENT_IDEAL_RATIO: float = 0.15  # 15 comment lines per 100 code lines

# Sub-signal weights (must sum to 1.0)
_W_FUNC_LENGTH:   float = 0.25
_W_NAME_ENTROPY:  float = 0.25
_W_NESTING:       float = 0.20
_W_COMMENT_RATIO: float = 0.15
_W_CYCLOMATIC:    float = 0.15
_FALLBACK_SCORE:  float = 0.5


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AestheticSubScores:
    """Breakdown of the five aesthetic sub-signals, each in [0.0, 1.0]."""
    function_length_score: float   # 1.0 = short, readable functions
    name_entropy_score:    float   # 1.0 = informative identifiers
    nesting_depth_score:   float   # 1.0 = shallow, well-structured code
    comment_ratio_score:   float   # 1.0 = well-commented relative to complexity
    cyclomatic_score:      float   # 1.0 = low complexity per function

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class AestheticFitnessReport:
    """Complete output of AestheticFitnessScorer.score().

    score          — composite aesthetic fitness in [0.0, 1.0]
    sub_scores     — breakdown of each dimension
    function_count — number of function defs analysed (0 → graceful fallback)
    fallback_used  — True when source could not be parsed (AFIT-0 guarantee)
    algorithm_version — AFIT_VERSION for replay verification
    """
    score:             float
    sub_scores:        AestheticSubScores
    function_count:    int
    fallback_used:     bool
    algorithm_version: str = AFIT_VERSION

    def as_dict(self) -> Dict[str, object]:
        return {
            "score": round(self.score, 4),
            "sub_scores": self.sub_scores.as_dict(),
            "function_count": self.function_count,
            "fallback_used": self.fallback_used,
            "algorithm_version": self.algorithm_version,
        }


# ---------------------------------------------------------------------------
# Internal AST helpers
# ---------------------------------------------------------------------------

def _clamp01(value: float) -> float:
    """Clamp float to [0.0, 1.0] — AFIT-BOUND-0."""
    return max(0.0, min(1.0, float(value)))


def _collect_functions(tree: ast.AST) -> List[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return all FunctionDef and AsyncFunctionDef nodes (depth-first)."""
    return [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _function_body_lines(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Approximate body length as (end_lineno - lineno) for the function node."""
    try:
        return max(1, (func.end_lineno or func.lineno) - func.lineno)
    except AttributeError:
        return 1


def _max_nesting_depth(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Compute maximum nesting depth within a function body.

    Nesting is incremented for: For, While, If, With, Try, ExceptHandler.
    """
    _NESTING_NODES = (
        ast.For, ast.While, ast.If, ast.With,
        ast.Try, ast.ExceptHandler,
        # Python 3.11+
        *([ast.TryStar] if hasattr(ast, "TryStar") else []),
    )

    max_depth: int = 0

    def _walk(node: ast.AST, depth: int) -> None:
        nonlocal max_depth
        if depth > max_depth:
            max_depth = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _NESTING_NODES):
                _walk(child, depth + 1)
            else:
                _walk(child, depth)

    _walk(func, 0)
    return max_depth


def _cyclomatic_complexity(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """McCabe cyclomatic complexity = decision-point count + 1."""
    _BRANCH_NODES = (
        ast.If, ast.For, ast.While, ast.ExceptHandler,
        ast.With, ast.Assert, ast.comprehension,
    )
    branches = sum(
        1 for node in ast.walk(func) if isinstance(node, _BRANCH_NODES)
    )
    # BoolOp (and/or) adds branches
    bool_ops = sum(
        len(node.values) - 1
        for node in ast.walk(func)
        if isinstance(node, ast.BoolOp)
    )
    return 1 + branches + bool_ops


def _collect_identifiers(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> List[str]:
    """Collect all user-defined identifiers within a function.

    Includes argument names and local Name references (writes).
    Excludes dunder names and single-character loop variables in their
    primary assignment site — those are evaluated by length threshold instead.
    """
    names: List[str] = []

    # argument names
    for arg in func.args.args + func.args.posonlyargs + func.args.kwonlyargs:
        names.append(arg.arg)
    if func.args.vararg:
        names.append(func.args.vararg.arg)
    if func.args.kwarg:
        names.append(func.args.kwarg.arg)

    # assignment targets (Name nodes in Store context)
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)

    # filter dunders
    return [n for n in names if not (n.startswith("__") and n.endswith("__"))]


def _name_entropy_score(identifiers: Sequence[str]) -> float:
    """Score identifier quality.

    Strategy: fraction of identifiers meeting the minimum length threshold
    (_MIN_NAME_LEN).  Short names (i, j, x, ok, …) are treated as low
    information unless there are none to judge.

    Returns 1.0 when all names are informative, 0.0 when all are trivial.
    Neutral 0.5 when there are no identifiers.
    """
    if not identifiers:
        return _FALLBACK_SCORE
    informative = sum(1 for n in identifiers if len(n) >= _MIN_NAME_LEN)
    return _clamp01(informative / len(identifiers))


def _comment_density(source: str) -> float:
    """Return fraction of non-empty lines that are comments (#-lines)."""
    lines = source.splitlines()
    non_empty = [ln.strip() for ln in lines if ln.strip()]
    if not non_empty:
        return 0.0
    comment_lines = sum(1 for ln in non_empty if ln.startswith("#"))
    return comment_lines / len(non_empty)


# ---------------------------------------------------------------------------
# Scoring functions for each sub-signal
# ---------------------------------------------------------------------------

def _score_function_length(funcs: List) -> float:
    """Lower average function length → higher score.

    Score formula: linear interpolation.
      avg <= _IDEAL_FUNC_LINES  → 1.0
      avg >= _MAX_FUNC_LINES    → 0.0
    """
    if not funcs:
        return _FALLBACK_SCORE
    avg_len = sum(_function_body_lines(f) for f in funcs) / len(funcs)
    if avg_len <= _IDEAL_FUNC_LINES:
        return 1.0
    if avg_len >= _MAX_FUNC_LINES:
        return 0.0
    ratio = (avg_len - _IDEAL_FUNC_LINES) / (_MAX_FUNC_LINES - _IDEAL_FUNC_LINES)
    return _clamp01(1.0 - ratio)


def _score_name_entropy(funcs: List) -> float:
    """Aggregate identifier quality across all functions."""
    if not funcs:
        return _FALLBACK_SCORE
    all_ids: List[str] = []
    for f in funcs:
        all_ids.extend(_collect_identifiers(f))
    return _name_entropy_score(all_ids)


def _score_nesting_depth(funcs: List) -> float:
    """Lower average max-nesting-depth → higher score.

    Score formula:
      avg depth == 0  → 1.0
      avg depth >= _MAX_NESTING → 0.0
      linear between.
    """
    if not funcs:
        return _FALLBACK_SCORE
    avg_depth = sum(_max_nesting_depth(f) for f in funcs) / len(funcs)
    if avg_depth <= 0:
        return 1.0
    if avg_depth >= _MAX_NESTING:
        return 0.0
    return _clamp01(1.0 - avg_depth / _MAX_NESTING)


def _score_comment_ratio(source: str, funcs: List) -> float:
    """Score comment density relative to median cyclomatic complexity.

    Heavily complex code benefits more from comments; simple code needs fewer.
    We compare actual comment density to an expected density scaled by
    complexity and score the proximity to ideal.
    """
    density = _comment_density(source)
    if not funcs:
        # No functions → score by raw density proximity to ideal
        diff = abs(density - _COMMENT_IDEAL_RATIO)
        return _clamp01(1.0 - diff / _COMMENT_IDEAL_RATIO)

    avg_cc = sum(_cyclomatic_complexity(f) for f in funcs) / len(funcs)
    # Adjust ideal ratio: higher complexity expects more comments
    adjusted_ideal = _COMMENT_IDEAL_RATIO * (1.0 + math.log1p(avg_cc) / 5.0)
    if density >= adjusted_ideal:
        return 1.0
    diff_ratio = (adjusted_ideal - density) / max(adjusted_ideal, 1e-9)
    return _clamp01(1.0 - diff_ratio)


def _score_cyclomatic(funcs: List) -> float:
    """Lower average cyclomatic complexity → higher score.

    Score formula:
      avg CC <= 1   → 1.0
      avg CC >= _MAX_CYCLOMATIC → 0.0
      linear between.
    """
    if not funcs:
        return _FALLBACK_SCORE
    avg_cc = sum(_cyclomatic_complexity(f) for f in funcs) / len(funcs)
    if avg_cc <= 1.0:
        return 1.0
    if avg_cc >= _MAX_CYCLOMATIC:
        return 0.0
    return _clamp01(1.0 - (avg_cc - 1.0) / (_MAX_CYCLOMATIC - 1.0))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class AestheticFitnessScorer:
    """Scores source code on five aesthetic quality dimensions.

    Usage::

        scorer = AestheticFitnessScorer()
        report = scorer.score(source_code)
        fitness = report.score  # [0.0, 1.0]

    AFIT-0: score() never raises. Any failure returns a fallback report
            with score=0.5 and fallback_used=True.
    AFIT-DETERM-0: identical source → identical report.
    """

    def __init__(self) -> None:
        self._version = AFIT_VERSION

    @property
    def version(self) -> str:
        return self._version

    def score(self, source: Optional[str]) -> AestheticFitnessReport:
        """Compute AestheticFitnessReport for *source*.

        Args:
            source: Python source code string, or None / empty.

        Returns:
            AestheticFitnessReport — always valid (AFIT-0).
        """
        try:
            return self._score_impl(source or "")
        except Exception:  # noqa: BLE001
            # AFIT-0: never raise; return neutral fallback
            return self._fallback_report()

    def _score_impl(self, source: str) -> AestheticFitnessReport:
        if not source.strip():
            return self._fallback_report()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return self._fallback_report()

        funcs = _collect_functions(tree)

        func_len_score    = _score_function_length(funcs)
        name_score        = _score_name_entropy(funcs)
        nesting_score     = _score_nesting_depth(funcs)
        comment_score     = _score_comment_ratio(source, funcs)
        cyclomatic_score  = _score_cyclomatic(funcs)

        composite = (
            _W_FUNC_LENGTH   * func_len_score
            + _W_NAME_ENTROPY  * name_score
            + _W_NESTING       * nesting_score
            + _W_COMMENT_RATIO * comment_score
            + _W_CYCLOMATIC    * cyclomatic_score
        )

        sub = AestheticSubScores(
            function_length_score = _clamp01(func_len_score),
            name_entropy_score    = _clamp01(name_score),
            nesting_depth_score   = _clamp01(nesting_score),
            comment_ratio_score   = _clamp01(comment_score),
            cyclomatic_score      = _clamp01(cyclomatic_score),
        )

        return AestheticFitnessReport(
            score             = _clamp01(composite),
            sub_scores        = sub,
            function_count    = len(funcs),
            fallback_used     = False,
            algorithm_version = AFIT_VERSION,
        )

    @staticmethod
    def _fallback_report() -> AestheticFitnessReport:
        """AFIT-0 fallback — score=0.5, all sub-scores=0.5."""
        sub = AestheticSubScores(
            function_length_score = _FALLBACK_SCORE,
            name_entropy_score    = _FALLBACK_SCORE,
            nesting_depth_score   = _FALLBACK_SCORE,
            comment_ratio_score   = _FALLBACK_SCORE,
            cyclomatic_score      = _FALLBACK_SCORE,
        )
        return AestheticFitnessReport(
            score             = _FALLBACK_SCORE,
            sub_scores        = sub,
            function_count    = 0,
            fallback_used     = True,
            algorithm_version = AFIT_VERSION,
        )


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "AFIT_VERSION",
    "AestheticFitnessScorer",
    "AestheticFitnessReport",
    "AestheticSubScores",
    # Normalisation constants (useful for tests and integration)
    "_MAX_FUNC_LINES",
    "_IDEAL_FUNC_LINES",
    "_MAX_NESTING",
    "_MAX_CYCLOMATIC",
    "_FALLBACK_SCORE",
    # Sub-signal weights
    "_W_FUNC_LENGTH",
    "_W_NAME_ENTROPY",
    "_W_NESTING",
    "_W_COMMENT_RATIO",
    "_W_CYCLOMATIC",
]
