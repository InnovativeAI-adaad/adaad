# SPDX-License-Identifier: Apache-2.0
"""Innovation #24 — Semantic Version Promises.
Machine-verifiable semver contracts enforced at governance.
"""
from __future__ import annotations
import ast, re
from dataclasses import dataclass
from typing import Any

SemVerImpact = str  # "patch" | "minor" | "major"

@dataclass
class SemVerVerdict:
    mutation_id: str
    declared_impact: SemVerImpact
    detected_impact: SemVerImpact
    contract_honored: bool
    violations: list[str]

    @property
    def verdict(self) -> str:
        return "PASS" if self.contract_honored else "FAIL"


IMPACT_RANK = {"patch": 0, "minor": 1, "major": 2}


class SemanticVersionEnforcer:
    """Verifies that declared version impact matches actual code change."""

    # Patterns indicating API-breaking changes
    BREAKING_PATTERNS = [
        r'def [a-z]\w+\(.*\) ->',    # function signature changes
        r'class \w+:',                # class definition changes
        r'__all__\s*=',              # exported names changes
        r'from \w+ import',           # import changes
    ]

    # Patterns indicating new functionality (minor)
    FEATURE_PATTERNS = [
        r'def [a-z]\w+\(',           # new function
        r'class \w+\(',              # new class
        r'@property',                # new property
    ]

    def verify(self, mutation_id: str, declared_impact: SemVerImpact,
                diff_text: str) -> SemVerVerdict:
        detected = self._detect_impact(diff_text)
        detected_rank = IMPACT_RANK.get(detected, 0)
        declared_rank = IMPACT_RANK.get(declared_impact, 0)

        violations = []
        if detected_rank > declared_rank:
            violations.append(
                f"Declared '{declared_impact}' but detected '{detected}'. "
                f"Actual change is more impactful than stated."
            )
        contract_honored = len(violations) == 0

        return SemVerVerdict(
            mutation_id=mutation_id,
            declared_impact=declared_impact,
            detected_impact=detected,
            contract_honored=contract_honored,
            violations=violations,
        )

    def _detect_impact(self, diff_text: str) -> SemVerImpact:
        plus_lines = "\n".join(l[1:] for l in diff_text.splitlines()
                                if l.startswith("+") and not l.startswith("+++"))
        minus_lines = "\n".join(l[1:] for l in diff_text.splitlines()
                                 if l.startswith("-") and not l.startswith("---"))

        # Breaking: signatures removed from public API
        for pattern in self.BREAKING_PATTERNS:
            if re.search(pattern, minus_lines) and "__all__" in minus_lines:
                return "major"
            if re.search(pattern, minus_lines) and re.search(r'def \w+\(', minus_lines):
                return "major"

        # Feature: new public functions/classes added
        for pattern in self.FEATURE_PATTERNS:
            if re.search(pattern, plus_lines):
                return "minor"

        return "patch"


__all__ = ["SemanticVersionEnforcer", "SemVerVerdict", "SemVerImpact",
           "IMPACT_RANK"]
