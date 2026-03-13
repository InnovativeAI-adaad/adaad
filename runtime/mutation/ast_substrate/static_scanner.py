# SPDX-License-Identifier: Apache-2.0
"""
runtime.mutation.ast_substrate.static_scanner
=============================================
StaticSafetyScanner — gates ASTDiffPatch before sandbox execution.

Four constitutional rules are evaluated in order.  A patch must pass ALL
rules before it may enter SandboxTournament.  Any failure is final and
carries a structured ScanResult with the violating rule name and reason.

Rules
-----
ImportBoundaryRule     No new imports of governance.* or Tier-0 module paths
                       in after_source that were not present in before_source.
NonDeterminismRule     Forbidden non-deterministic calls: datetime.now(),
                       datetime.utcnow(), random.*, uuid4() without provider.
ComplexityCeilingRule  after_source cyclomatic proxy (branch node count) must
                       not exceed before_source count + COMPLEXITY_DELTA_MAX.
PatchSizeRule          Redundant post-parse enforcement of PATCH-SIZE-0
                       (max_ast_nodes delta, max_files).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from runtime.mutation.ast_substrate.ast_diff_patch import ASTDiffPatch, MAX_AST_NODES, MAX_FILES


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPLEXITY_DELTA_MAX: int = 2  # Class A ceiling; Class B may exceed with token

_FORBIDDEN_ND_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bdatetime\.now\b"),
    re.compile(r"\bdatetime\.utcnow\b"),
    re.compile(r"\brandom\.(random|randint|choice|choices|sample|shuffle|seed)\b"),
    re.compile(r"\buuid\.uuid4\b"),
    re.compile(r"\buuid4\(\)"),
    re.compile(r"\btime\.time\b"),
]

_GOVERNANCE_PREFIXES: Tuple[str, ...] = (
    "runtime.governance",
    "runtime.ledger",
)

_BRANCH_NODE_TYPES = (
    ast.If, ast.For, ast.While, ast.ExceptHandler,
    ast.With, ast.AsyncFor, ast.AsyncWith, ast.Assert,
)

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class RuleViolation:
    rule_name: str
    reason: str

    def to_dict(self) -> dict:
        return {"rule_name": self.rule_name, "reason": self.reason}


@dataclass
class ScanResult:
    """Outcome of a full StaticSafetyScanner pass.

    Attributes
    ----------
    passed          True only when all four rules pass.
    violations      List of RuleViolation objects (empty on full pass).
    rules_checked   Number of rules evaluated.
    patch_hash      patch_hash of the evaluated ASTDiffPatch.
    """
    passed: bool
    violations: List[RuleViolation] = field(default_factory=list)
    rules_checked: int = 0
    patch_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "rules_checked": self.rules_checked,
            "patch_hash": self.patch_hash,
        }


# ---------------------------------------------------------------------------
# Individual rule implementations
# ---------------------------------------------------------------------------

class ImportBoundaryRule:
    """Block new governance/ledger imports introduced by the patch."""

    name = "ImportBoundaryRule"

    def check(self, patch: ASTDiffPatch) -> Optional[RuleViolation]:
        before_imports = _collect_imports(patch.before_source)
        after_imports = _collect_imports(patch.after_source)
        new_imports = after_imports - before_imports
        forbidden = {
            imp for imp in new_imports
            if any(imp.startswith(p) for p in _GOVERNANCE_PREFIXES)
        }
        if forbidden:
            return RuleViolation(
                rule_name=self.name,
                reason=f"New governance/ledger imports introduced: {sorted(forbidden)}",
            )
        return None


class NonDeterminismRule:
    """Block non-deterministic calls introduced in after_source."""

    name = "NonDeterminismRule"

    def check(self, patch: ASTDiffPatch) -> Optional[RuleViolation]:
        # Only flag patterns present in after but not in before
        before_matches = _nd_matches(patch.before_source)
        after_matches = _nd_matches(patch.after_source)
        new_nd = after_matches - before_matches
        if new_nd:
            return RuleViolation(
                rule_name=self.name,
                reason=(
                    f"Non-deterministic call(s) introduced: {sorted(new_nd)}. "
                    f"Use RuntimeDeterminismProvider instead."
                ),
            )
        return None


class ComplexityCeilingRule:
    """Block patches that raise cyclomatic proxy beyond COMPLEXITY_DELTA_MAX."""

    name = "ComplexityCeilingRule"

    def check(self, patch: ASTDiffPatch) -> Optional[RuleViolation]:
        before_complexity = _branch_count(patch.before_source)
        after_complexity = _branch_count(patch.after_source)
        delta = after_complexity - before_complexity
        if delta > COMPLEXITY_DELTA_MAX:
            return RuleViolation(
                rule_name=self.name,
                reason=(
                    f"Complexity delta={delta} exceeds ceiling={COMPLEXITY_DELTA_MAX} "
                    f"(Class A). Classify as Class B with exception token to proceed."
                ),
            )
        return None


class PatchSizeRule:
    """Redundant enforcement of PATCH-SIZE-0 at scan time."""

    name = "PatchSizeRule"

    def check(self, patch: ASTDiffPatch) -> Optional[RuleViolation]:
        total_files = 1 + len(patch.auxiliary_files)
        if total_files > MAX_FILES:
            return RuleViolation(
                rule_name=self.name,
                reason=f"PATCH-SIZE-0: {total_files} files > max={MAX_FILES}",
            )
        if abs(patch.delta_node_count) > MAX_AST_NODES:
            return RuleViolation(
                rule_name=self.name,
                reason=(
                    f"PATCH-SIZE-0: |delta_nodes|={abs(patch.delta_node_count)} "
                    f"> max={MAX_AST_NODES}"
                ),
            )
        return None


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class StaticSafetyScanner:
    """Runs all four rules in order; short-circuits on first violation.

    Usage
    -----
    scanner = StaticSafetyScanner()
    result = scanner.scan(patch)
    if not result.passed:
        handle_violation(result.violations[0])
    """

    _RULES = [
        ImportBoundaryRule(),
        NonDeterminismRule(),
        ComplexityCeilingRule(),
        PatchSizeRule(),
    ]

    def scan(self, patch: ASTDiffPatch, fail_fast: bool = True) -> ScanResult:
        """Scan *patch* against all rules.

        Parameters
        ----------
        patch:      The ASTDiffPatch to evaluate.
        fail_fast:  If True (default), stop at first violation.
                    If False, collect all violations.
        """
        violations: List[RuleViolation] = []
        checked = 0

        for rule in self._RULES:
            checked += 1
            try:
                violation = rule.check(patch)
            except SyntaxError as exc:
                violation = RuleViolation(
                    rule_name=rule.name,
                    reason=f"SyntaxError during rule evaluation: {exc}",
                )
            if violation:
                violations.append(violation)
                if fail_fast:
                    break

        return ScanResult(
            passed=len(violations) == 0,
            violations=violations,
            rules_checked=checked,
            patch_hash=patch.patch_hash,
        )

    @property
    def rule_names(self) -> List[str]:
        return [r.name for r in self._RULES]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_imports(source: str) -> Set[str]:
    """Return all imported module names from *source*."""
    imports: Set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _nd_matches(source: str) -> Set[str]:
    """Return set of forbidden non-deterministic pattern tokens found in source."""
    matches: Set[str] = set()
    for pattern in _FORBIDDEN_ND_PATTERNS:
        for m in pattern.finditer(source):
            matches.add(m.group(0))
    return matches


def _branch_count(source: str) -> int:
    """Cyclomatic proxy: count branch-contributing AST nodes."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    return sum(1 for node in ast.walk(tree) if isinstance(node, _BRANCH_NODE_TYPES))
