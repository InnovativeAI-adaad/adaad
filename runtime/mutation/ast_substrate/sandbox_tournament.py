"""
runtime.mutation.ast_substrate.sandbox_tournament
==================================================
SandboxTournament — ephemeral multi-candidate mutation competition.

Design
------
Each tournament round receives 1–N ASTDiffPatch candidates.  Candidates
are evaluated in an ephemeral clone of the target module, isolated from
live state.  MUTATION_SANDBOX_ONLY=true is enforced: no writes to the
live codebase during a tournament.

Scoring model (Phase 60 baseline — extended by FitnessEngine v2 in Phase 62)
----------------------------------------------------------------------------
syntax_valid    1.0 if after_source parses cleanly, else 0.0
size_penalty    max(0, 1.0 - abs(delta_nodes) / MAX_AST_NODES)
complexity_ok   1.0 if scanner passes ComplexityCeilingRule, else 0.5
scanner_pass    1.0 if all 4 scanner rules pass, else 0.0

composite = 0.40*syntax_valid + 0.25*size_penalty + 0.20*complexity_ok + 0.15*scanner_pass

Invariants
----------
SANDBOX-DIV-0  All applicator calls use sandbox_only=True.
MUTATION_SANDBOX_ONLY is set to "true" for the duration of the tournament.
"""

from __future__ import annotations

import ast
import os
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from runtime.mutation.ast_substrate.ast_diff_patch import ASTDiffPatch, MAX_AST_NODES
from runtime.mutation.ast_substrate.patch_applicator import PatchApplicator
from runtime.mutation.ast_substrate.static_scanner import StaticSafetyScanner


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CandidateScore:
    """Score record for a single tournament candidate.

    Attributes
    ----------
    patch_hash      ASTDiffPatch.patch_hash.
    rank            Tournament rank (1 = winner).
    composite       Weighted composite score [0.0, 1.0].
    syntax_valid    1.0 if after_source parses; else 0.0.
    size_penalty    Normalised inverse of abs(delta_nodes).
    complexity_ok   1.0 if ComplexityCeilingRule passes.
    scanner_pass    1.0 if all scanner rules pass.
    scan_result     Detailed ScanResult from StaticSafetyScanner.
    apply_result    Detailed ApplyResult from PatchApplicator.
    disqualified    True if candidate was rejected before scoring.
    disqualify_reason  Reason string if disqualified.
    """
    patch_hash: str
    rank: int = 0
    composite: float = 0.0
    syntax_valid: float = 0.0
    size_penalty: float = 0.0
    complexity_ok: float = 0.0
    scanner_pass: float = 0.0
    scan_result: Optional[object] = None
    apply_result: Optional[object] = None
    disqualified: bool = False
    disqualify_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "patch_hash": self.patch_hash,
            "rank": self.rank,
            "composite": self.composite,
            "syntax_valid": self.syntax_valid,
            "size_penalty": self.size_penalty,
            "complexity_ok": self.complexity_ok,
            "scanner_pass": self.scanner_pass,
            "disqualified": self.disqualified,
            "disqualify_reason": self.disqualify_reason,
            "scan_result": self.scan_result.to_dict() if self.scan_result else None,
            "apply_result": self.apply_result.to_dict() if self.apply_result else None,
        }


@dataclass
class TournamentResult:
    """Full tournament outcome.

    Attributes
    ----------
    winner          Best-scoring CandidateScore, or None if all disqualified.
    scores          All candidate scores sorted descending by composite.
    candidates_run  Total candidates evaluated.
    sandbox_only    Always True — MUTATION_SANDBOX_ONLY enforced.
    tournament_hash SHA-256 of all patch_hashes in entry order.
    """
    winner: Optional[CandidateScore]
    scores: List[CandidateScore] = field(default_factory=list)
    candidates_run: int = 0
    sandbox_only: bool = True
    tournament_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "winner": self.winner.to_dict() if self.winner else None,
            "scores": [s.to_dict() for s in self.scores],
            "candidates_run": self.candidates_run,
            "sandbox_only": self.sandbox_only,
            "tournament_hash": self.tournament_hash,
        }


# ---------------------------------------------------------------------------
# Tournament
# ---------------------------------------------------------------------------

class SandboxTournament:
    """Runs an ephemeral sandbox competition between ASTDiffPatch candidates.

    Always operates with MUTATION_SANDBOX_ONLY=true; never writes live files.

    Usage
    -----
    tournament = SandboxTournament()
    result = tournament.run(candidates)
    winning_patch = candidates[result.scores[0].rank - 1]  # rank is 1-based
    """

    # Scoring weights
    _W_SYNTAX    = 0.40
    _W_SIZE      = 0.25
    _W_COMPLEXITY= 0.20
    _W_SCANNER   = 0.15

    def __init__(self) -> None:
        self._scanner = StaticSafetyScanner()
        # Always force sandbox_only=True (SANDBOX-DIV-0)
        self._applicator = PatchApplicator(sandbox_only=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, candidates: List[ASTDiffPatch]) -> TournamentResult:
        """Evaluate all *candidates*; return ranked TournamentResult."""
        if not candidates:
            return TournamentResult(winner=None, candidates_run=0, sandbox_only=True)

        # Enforce MUTATION_SANDBOX_ONLY for the duration
        prev_env = os.environ.get("MUTATION_SANDBOX_ONLY")
        os.environ["MUTATION_SANDBOX_ONLY"] = "true"

        try:
            scores = [self._evaluate(patch) for patch in candidates]
        finally:
            if prev_env is None:
                os.environ.pop("MUTATION_SANDBOX_ONLY", None)
            else:
                os.environ["MUTATION_SANDBOX_ONLY"] = prev_env

        # Sort: disqualified last, then by composite descending
        scores.sort(key=lambda s: (s.disqualified, -s.composite))

        # Assign ranks
        for i, score in enumerate(scores):
            score.rank = i + 1

        winner = None if scores[0].disqualified else scores[0]

        import hashlib, json
        t_hash = hashlib.sha256(
            json.dumps([s.patch_hash for s in scores]).encode()
        ).hexdigest()

        return TournamentResult(
            winner=winner,
            scores=scores,
            candidates_run=len(candidates),
            sandbox_only=True,
            tournament_hash=t_hash,
        )

    def run_single(self, patch: ASTDiffPatch) -> CandidateScore:
        """Evaluate a single patch — convenience wrapper."""
        result = self.run([patch])
        return result.scores[0]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _evaluate(self, patch: ASTDiffPatch) -> CandidateScore:
        score = CandidateScore(patch_hash=patch.patch_hash)

        # Syntax validity
        try:
            ast.parse(patch.after_source)
            score.syntax_valid = 1.0
        except SyntaxError:
            score.syntax_valid = 0.0
            score.disqualified = True
            score.disqualify_reason = "SyntaxError in after_source"
            score.composite = 0.0
            return score

        # Static scanner (all 4 rules, collect all violations)
        scan = self._scanner.scan(patch, fail_fast=False)
        score.scan_result = scan
        score.scanner_pass = 1.0 if scan.passed else 0.0

        # ComplexityCeiling specifically
        ceiling_violated = any(
            v.rule_name == "ComplexityCeilingRule" for v in scan.violations
        )
        score.complexity_ok = 0.0 if ceiling_violated else 1.0

        # PatchSize — disqualify if violated
        size_violated = any(
            v.rule_name == "PatchSizeRule" for v in scan.violations
        )
        if size_violated:
            score.disqualified = True
            score.disqualify_reason = "PatchSizeRule violation"
            score.composite = 0.0
            return score

        # Size penalty (normalised inverse delta)
        score.size_penalty = max(0.0, 1.0 - abs(patch.delta_node_count) / max(MAX_AST_NODES, 1))

        # Sandbox apply (dry-run only — SANDBOX-DIV-0)
        apply_result = self._applicator.apply(patch, base_dir="")
        score.apply_result = apply_result

        if not apply_result.success and apply_result.divergence:
            score.disqualified = True
            score.disqualify_reason = f"SANDBOX-DIV-0: {apply_result.error}"
            score.composite = 0.0
            return score

        # Composite
        score.composite = _clamp(
            self._W_SYNTAX    * score.syntax_valid
            + self._W_SIZE    * score.size_penalty
            + self._W_COMPLEXITY * score.complexity_ok
            + self._W_SCANNER * score.scanner_pass
        )
        return score


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))
