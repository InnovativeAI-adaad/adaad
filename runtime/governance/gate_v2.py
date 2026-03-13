# SPDX-License-Identifier: Apache-2.0
"""Phase 63 — GovernanceGate v2.

Extends the existing GovernanceGate with five new diff-aware rules.
GATE-V2-EXISTING-0: all 16 existing rules continue to evaluate first, unchanged.
New rules are additive and evaluate after existing rules in canonical order.

New rules (Phase 63 scope):
  AST-SAFE-0       No exec/eval/unguarded os.system or subprocess; no syntax errors.
  AST-IMPORT-0     No new imports from Tier-0 module roots.
  AST-COMPLEX-0    cyclomatic delta <= +2 (Class A); Class B eligible up to +8 with token.
  SANDBOX-DIV-0    Post-apply test results must match sandbox exactly (gate integration).
  SEMANTIC-INT-0   No removal of error guard without compensating handler.

Constitutional invariants:
  GATE-V2-EXISTING-0  All existing rules evaluate first; new rules are additive only.
  AST-SAFE-0          Hard; no Class B path.
  AST-IMPORT-0        Hard; no Class B path.
  AST-COMPLEX-0       Class A: delta <= +2 hard; Class B: delta <= +8 with ExceptionToken.
  SANDBOX-DIV-0       Hard; no Class B path (mirrors SANDBOX-DIV-0 from Phase 60).
  SEMANTIC-INT-0      Hard; no Class B path.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from runtime.governance.exception_tokens import ExceptionTokenLedger

# ---------------------------------------------------------------------------
# Constants (AST-COMPLEX-0 thresholds — approved by GATE-V2-RULES HUMAN-0)
# ---------------------------------------------------------------------------

AST_COMPLEX_CLASS_A_CEILING: int = 2    # hard Class A limit
AST_COMPLEX_CLASS_B_CEILING: int = 8    # Class B maximum (requires ExceptionToken)

_TIER_0_MODULE_ROOTS: frozenset[str] = frozenset({
    "runtime.governance.gate",
    "runtime.governance.foundation",
    "runtime.governance",
    "security",
})

_FORBIDDEN_AST_CALLS = frozenset({
    "eval", "exec",
})

_FORBIDDEN_ATTR_CALLS = frozenset({
    ("os", "system"),
    ("subprocess", "call"),
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
})

_ERROR_GUARD_NODES = (ast.ExceptHandler, ast.Try)


# ---------------------------------------------------------------------------
# V2RuleResult — per-rule result with class_b_eligible flag
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V2RuleResult:
    rule_id: str
    passed: bool
    class_b_eligible: bool = False
    reason: str = "ok"
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "passed": self.passed,
            "class_b_eligible": self.class_b_eligible,
            "reason": self.reason,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# V2GateDecision
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V2GateDecision:
    """Extended gate decision from GovernanceGateV2."""

    approved: bool
    class_b_eligible: bool      # True iff only AST-COMPLEX-0 blocks and Class B path open
    rule_results: List[V2RuleResult]
    mutation_id: str
    capability_name: str
    exception_token_id: Optional[str]   # active token if Class B approved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "class_b_eligible": self.class_b_eligible,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "mutation_id": self.mutation_id,
            "capability_name": self.capability_name,
            "exception_token_id": self.exception_token_id,
        }


# ---------------------------------------------------------------------------
# Individual rule evaluators
# ---------------------------------------------------------------------------

def _check_ast_safe_0(after_source: str) -> V2RuleResult:
    """AST-SAFE-0: no exec/eval or unguarded os.system/subprocess calls; no syntax errors."""
    try:
        tree = ast.parse(after_source)
    except SyntaxError as e:
        return V2RuleResult(
            rule_id="AST-SAFE-0", passed=False,
            reason="syntax_error", detail=str(e),
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Direct call: eval(...) or exec(...)
            func = node.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_AST_CALLS:
                return V2RuleResult(
                    rule_id="AST-SAFE-0", passed=False,
                    reason=f"forbidden_call_{func.id}",
                    detail=f"Direct call to '{func.id}' is not permitted",
                )
            # Attribute call: os.system(...), subprocess.run(...) etc.
            if isinstance(func, ast.Attribute):
                obj = func.value
                if isinstance(obj, ast.Name):
                    pair = (obj.id, func.attr)
                    if pair in _FORBIDDEN_ATTR_CALLS:
                        return V2RuleResult(
                            rule_id="AST-SAFE-0", passed=False,
                            reason=f"forbidden_attr_call_{obj.id}_{func.attr}",
                            detail=f"Unguarded call to '{obj.id}.{func.attr}' is not permitted",
                        )
    return V2RuleResult(rule_id="AST-SAFE-0", passed=True)


def _check_ast_import_0(after_source: str) -> V2RuleResult:
    """AST-IMPORT-0: no new imports from Tier-0 module roots."""
    try:
        tree = ast.parse(after_source)
    except SyntaxError:
        # Let AST-SAFE-0 handle syntax errors; pass here
        return V2RuleResult(rule_id="AST-IMPORT-0", passed=True)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for root in _TIER_0_MODULE_ROOTS:
                    if alias.name == root or alias.name.startswith(root + "."):
                        return V2RuleResult(
                            rule_id="AST-IMPORT-0", passed=False,
                            reason="tier_0_import",
                            detail=f"Import '{alias.name}' targets Tier-0 module root '{root}'",
                        )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for root in _TIER_0_MODULE_ROOTS:
                if module == root or module.startswith(root + "."):
                    return V2RuleResult(
                        rule_id="AST-IMPORT-0", passed=False,
                        reason="tier_0_import_from",
                        detail=f"ImportFrom '{module}' targets Tier-0 module root '{root}'",
                    )
    return V2RuleResult(rule_id="AST-IMPORT-0", passed=True)


def _cyclomatic_proxy(source: str) -> int:
    """Count branch nodes as a cyclomatic complexity proxy."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (
            ast.If, ast.For, ast.While, ast.ExceptHandler,
            ast.With, ast.Assert, ast.comprehension,
        )):
            count += 1
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
    return count


def _check_ast_complex_0(
    before_source: Optional[str],
    after_source: str,
    *,
    capability_name: str,
    current_epoch_seq: int,
    exception_ledger: Optional[ExceptionTokenLedger],
) -> V2RuleResult:
    """AST-COMPLEX-0: cyclomatic delta <= +2 (Class A); Class B up to +8 with token."""
    before_complexity = _cyclomatic_proxy(before_source) if before_source else 0
    after_complexity = _cyclomatic_proxy(after_source)
    delta = after_complexity - before_complexity

    if delta <= AST_COMPLEX_CLASS_A_CEILING:
        return V2RuleResult(rule_id="AST-COMPLEX-0", passed=True,
                            detail=f"delta={delta} within Class A ceiling +{AST_COMPLEX_CLASS_A_CEILING}")

    # Delta exceeds Class A — check Class B
    if delta > AST_COMPLEX_CLASS_B_CEILING:
        return V2RuleResult(
            rule_id="AST-COMPLEX-0", passed=False,
            reason=f"complexity_delta_{delta}_exceeds_class_b_ceiling_{AST_COMPLEX_CLASS_B_CEILING}",
            detail=f"before={before_complexity} after={after_complexity} delta={delta}; hard rejection",
        )

    # Delta in (Class A ceiling, Class B ceiling] — Class B eligible
    # Check for active ExceptionToken
    has_token = (
        exception_ledger is not None
        and exception_ledger.has_active_token(capability_name, "AST-COMPLEX-0", current_epoch_seq)
    )

    if has_token:
        return V2RuleResult(
            rule_id="AST-COMPLEX-0", passed=True,
            class_b_eligible=True,
            detail=f"Class B approved via ExceptionToken; delta={delta}",
        )

    # No token — Class B eligible but not yet approved
    return V2RuleResult(
        rule_id="AST-COMPLEX-0", passed=False,
        class_b_eligible=True,
        reason=f"complexity_delta_{delta}_exceeds_class_a_requires_exception_token",
        detail=f"delta={delta}; Class B eligible — obtain ExceptionToken to proceed",
    )


def _check_sandbox_div_0(replay_diverged: bool) -> V2RuleResult:
    """SANDBOX-DIV-0: post-apply test results must match sandbox exactly."""
    if replay_diverged:
        return V2RuleResult(
            rule_id="SANDBOX-DIV-0", passed=False,
            reason="replay_divergence_detected",
            detail="Post-apply test results diverged from sandbox results; automatic rejection",
        )
    return V2RuleResult(rule_id="SANDBOX-DIV-0", passed=True)


def _check_semantic_int_0(
    before_source: Optional[str], after_source: str
) -> V2RuleResult:
    """SEMANTIC-INT-0: no removal of error guard without compensating handler."""
    if before_source is None:
        return V2RuleResult(rule_id="SEMANTIC-INT-0", passed=True)

    try:
        before_tree = ast.parse(before_source)
        after_tree = ast.parse(after_source)
    except SyntaxError:
        return V2RuleResult(rule_id="SEMANTIC-INT-0", passed=True)

    def _count_guards(tree: ast.AST) -> int:
        return sum(1 for node in ast.walk(tree) if isinstance(node, _ERROR_GUARD_NODES))

    before_guards = _count_guards(before_tree)
    after_guards = _count_guards(after_tree)

    if after_guards < before_guards:
        return V2RuleResult(
            rule_id="SEMANTIC-INT-0", passed=False,
            reason="error_guard_removed_without_compensation",
            detail=(
                f"before={before_guards} error guards, after={after_guards}; "
                "removed guard must have a compensating handler"
            ),
        )
    return V2RuleResult(rule_id="SEMANTIC-INT-0", passed=True)


# ---------------------------------------------------------------------------
# GovernanceGateV2 — additive; does NOT replace GovernanceGate
# ---------------------------------------------------------------------------

class GovernanceGateV2:
    """Phase 63 additive governance gate layer.

    Evaluates the five new rules (AST-SAFE-0, AST-IMPORT-0, AST-COMPLEX-0,
    SANDBOX-DIV-0, SEMANTIC-INT-0) after the existing GovernanceGate.

    GATE-V2-EXISTING-0: the caller is responsible for running the existing
    GovernanceGate first. GovernanceGateV2 must never be substituted for it.
    """

    def __init__(
        self,
        exception_ledger: Optional[ExceptionTokenLedger] = None,
    ) -> None:
        self._ledger = exception_ledger

    def evaluate(
        self,
        *,
        mutation_id: str,
        capability_name: str,
        after_source: str,
        before_source: Optional[str] = None,
        replay_diverged: bool = False,
        current_epoch_seq: int = 0,
    ) -> V2GateDecision:
        """Evaluate all five Phase 63 rules in canonical order.

        Returns V2GateDecision with approved=True iff all rules pass.
        class_b_eligible=True iff the only blocking rule is AST-COMPLEX-0 and
        a Class B path is available.
        """
        results: List[V2RuleResult] = []

        # Canonical evaluation order (matches rule_id alphabetical sort)
        results.append(_check_ast_complex_0(
            before_source, after_source,
            capability_name=capability_name,
            current_epoch_seq=current_epoch_seq,
            exception_ledger=self._ledger,
        ))
        results.append(_check_ast_import_0(after_source))
        results.append(_check_ast_safe_0(after_source))
        results.append(_check_sandbox_div_0(replay_diverged))
        results.append(_check_semantic_int_0(before_source, after_source))

        failed = [r for r in results if not r.passed]
        approved = len(failed) == 0

        # Determine class_b_eligible: only if AST-COMPLEX-0 is the sole failure
        # and it set class_b_eligible=True on its result
        class_b_eligible = (
            len(failed) == 1
            and failed[0].rule_id == "AST-COMPLEX-0"
            and failed[0].class_b_eligible
        )

        # Determine active exception token ID (for EpochEvidence)
        exception_token_id: Optional[str] = None
        complex_result = next((r for r in results if r.rule_id == "AST-COMPLEX-0"), None)
        if complex_result and complex_result.passed and complex_result.class_b_eligible:
            if self._ledger is not None:
                active = self._ledger.active_tokens_for(capability_name, current_epoch_seq)
                ast_tokens = [t for t in active if t.rule_id == "AST-COMPLEX-0"]
                if ast_tokens:
                    exception_token_id = ast_tokens[0].token_id

        return V2GateDecision(
            approved=approved,
            class_b_eligible=class_b_eligible,
            rule_results=results,
            mutation_id=mutation_id,
            capability_name=capability_name,
            exception_token_id=exception_token_id,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "AST_COMPLEX_CLASS_A_CEILING",
    "AST_COMPLEX_CLASS_B_CEILING",
    "GovernanceGateV2",
    "V2GateDecision",
    "V2RuleResult",
    "_check_ast_safe_0",
    "_check_ast_import_0",
    "_check_ast_complex_0",
    "_check_sandbox_div_0",
    "_check_semantic_int_0",
]
