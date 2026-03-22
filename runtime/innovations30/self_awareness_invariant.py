# SPDX-License-Identifier: Apache-2.0
"""Innovation #28 — Self-Awareness Invariant.
Constitutional rule SELF-AWARE-0: no mutation may reduce
the observability surface of the system's self-monitoring infrastructure.
The system cannot optimize away its own transparency.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any

# Protected self-monitoring modules — mutations must not reduce their coverage
PROTECTED_OBSERVABILITY_MODULES: frozenset[str] = frozenset([
    "runtime/metrics.py",
    "runtime/invariants.py",
    "security/ledger/journal.py",
    "runtime/governance/health_aggregator.py",
    "runtime/preflight.py",
    "runtime/constitution.py",
])

# Patterns that reduce observability
OBSERVABILITY_REDUCTION_PATTERNS: list[str] = [
    r"metrics\.log\(",              # removing metric emissions
    r"journal\.append",             # removing ledger writes
    r"verify_journal_integrity",    # removing integrity checks
    r"verify_all\(",                # removing invariant checks
    r"boot_sanity_check",           # removing boot validation
    r"log\.warning\(",              # removing warning logs
    r"log\.error\(",                # removing error logs
]

@dataclass
class SelfAwarenessVerdict:
    mutation_id: str
    passed: bool
    violations: list[str]
    protected_module_touched: bool
    removed_observability_calls: list[str]
    rule_id: str = "SELF-AWARE-0"


class SelfAwarenessInvariant:
    """Enforces SELF-AWARE-0: protect self-monitoring infrastructure."""

    def evaluate(self, mutation_id: str, diff_text: str,
                  changed_files: list[str]) -> SelfAwarenessVerdict:
        violations = []
        removed_calls = []

        # Check if protected modules are being reduced
        protected_touched = any(
            any(pm in str(f) for pm in PROTECTED_OBSERVABILITY_MODULES)
            for f in changed_files
        )

        # Check for removed observability calls (lines starting with -)
        minus_lines = "\n".join(
            l[1:] for l in diff_text.splitlines()
            if l.startswith("-") and not l.startswith("---")
        )

        for pattern in OBSERVABILITY_REDUCTION_PATTERNS:
            matches = re.findall(pattern, minus_lines)
            if matches:
                removed_calls.extend(matches[:2])  # record up to 2 examples

        if protected_touched and removed_calls:
            violations.append(
                f"SELF-AWARE-0: Mutation removes {len(removed_calls)} observability "
                f"call(s) from protected monitoring infrastructure. "
                f"Removed: {removed_calls[:3]}. "
                f"The system cannot optimize away its own transparency."
            )

        return SelfAwarenessVerdict(
            mutation_id=mutation_id,
            passed=len(violations) == 0,
            violations=violations,
            protected_module_touched=protected_touched,
            removed_observability_calls=removed_calls,
        )


__all__ = ["SelfAwarenessInvariant", "SelfAwarenessVerdict",
           "PROTECTED_OBSERVABILITY_MODULES", "OBSERVABILITY_REDUCTION_PATTERNS"]
