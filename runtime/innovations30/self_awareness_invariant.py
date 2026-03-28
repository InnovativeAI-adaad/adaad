# SPDX-License-Identifier: Apache-2.0
"""Innovation #28 — Self-Awareness Invariant.
Constitutional rule SELF-AWARE-0: no mutation may reduce
the observability surface of the system's self-monitoring infrastructure.
The system cannot optimize away its own transparency.

Additions (v1.1):
    register_protected_module()  — runtime surface expansion
    protected_surface_score()    — fraction of protected surface touched
    summary()                    — aggregate violation statistics
    SHA-256 verdict digest       — tamper-detectable audit trail
"""
from __future__ import annotations
import hashlib, json, re, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Protected self-monitoring modules — mutations must not reduce their coverage
_DEFAULT_PROTECTED: frozenset[str] = frozenset([
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
    surface_score: float = 1.0          # fraction of protected surface untouched
    verdict_digest: str = ""            # SHA-256 tamper-detectable audit hash
    timestamp: float = field(default_factory=time.time)
    rule_id: str = "SELF-AWARE-0"

    def __post_init__(self) -> None:
        if not self.verdict_digest:
            payload = (
                f"{self.mutation_id}:{self.passed}:{self.rule_id}:"
                f"{sorted(self.violations)}:{self.surface_score:.4f}"
            )
            self.verdict_digest = (
                "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
            )


class SelfAwarenessInvariant:
    """Enforces SELF-AWARE-0: protect self-monitoring infrastructure."""

    def __init__(
        self,
        audit_path: Path | None = None,
        extra_protected: frozenset[str] | None = None,
    ) -> None:
        # Runtime-extensible protected surface
        self._protected: set[str] = set(_DEFAULT_PROTECTED)
        if extra_protected:
            self._protected.update(extra_protected)
        self._audit_path = Path(audit_path) if audit_path else None
        self._violation_count: int = 0
        self._evaluation_count: int = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def register_protected_module(self, path: str) -> None:
        """Expand the protected observability surface at runtime.

        Rationale: new monitoring modules added post-boot must be protected
        without requiring a code change to this file.
        """
        self._protected.add(path)

    def evaluate(
        self,
        mutation_id: str,
        diff_text: str,
        changed_files: list[str],
    ) -> SelfAwarenessVerdict:
        """Evaluate a mutation diff against SELF-AWARE-0.

        Args:
            mutation_id:   unique mutation identifier
            diff_text:     unified diff string (- lines = removed)
            changed_files: list of file paths modified by the mutation

        Returns:
            SelfAwarenessVerdict with verdict_digest for audit chain.
        """
        self._evaluation_count += 1
        violations: list[str] = []
        removed_calls: list[str] = []

        # Which protected modules are touched?
        touched_protected = [
            pm for pm in self._protected
            if any(pm in str(f) for f in changed_files)
        ]
        protected_touched = bool(touched_protected)

        # Scan removed lines for observability call deletions
        minus_lines = "\n".join(
            l[1:] for l in diff_text.splitlines()
            if l.startswith("-") and not l.startswith("---")
        )
        for pattern in OBSERVABILITY_REDUCTION_PATTERNS:
            matches = re.findall(pattern, minus_lines)
            if matches:
                removed_calls.extend(matches[:2])

        if protected_touched and removed_calls:
            violations.append(
                f"SELF-AWARE-0: Mutation removes {len(removed_calls)} observability "
                f"call(s) from protected monitoring infrastructure "
                f"({touched_protected}). "
                f"Removed patterns: {removed_calls[:3]}. "
                f"The system cannot optimize away its own transparency."
            )

        # surface_score: fraction of protected surface NOT touched
        # 1.0 = no protected modules touched; 0.0 = all protected touched
        n_protected = len(self._protected)
        n_touched = len(touched_protected)
        surface_score = (
            round(1.0 - (n_touched / n_protected), 4) if n_protected else 1.0
        )

        if violations:
            self._violation_count += 1

        verdict = SelfAwarenessVerdict(
            mutation_id=mutation_id,
            passed=len(violations) == 0,
            violations=violations,
            protected_module_touched=protected_touched,
            removed_observability_calls=removed_calls,
            surface_score=surface_score,
        )

        if self._audit_path is not None:
            self._persist(verdict)

        return verdict

    def protected_surface_score(self, changed_files: list[str]) -> float:
        """Return fraction of protected surface NOT touched by changed_files.

        1.0 = mutation touches no protected modules (ideal).
        0.0 = mutation touches every protected module (critical violation).
        """
        n_protected = len(self._protected)
        if n_protected == 0:
            return 1.0
        touched = sum(
            1 for pm in self._protected
            if any(pm in str(f) for f in changed_files)
        )
        return round(1.0 - (touched / n_protected), 4)

    def summary(self) -> dict[str, Any]:
        """Aggregate statistics for observability enforcement."""
        return {
            "rule_id": "SELF-AWARE-0",
            "protected_modules": sorted(self._protected),
            "protected_module_count": len(self._protected),
            "total_evaluations": self._evaluation_count,
            "total_violations": self._violation_count,
            "violation_rate": (
                round(self._violation_count / self._evaluation_count, 4)
                if self._evaluation_count else 0.0
            ),
            "observability_reduction_patterns": len(OBSERVABILITY_REDUCTION_PATTERNS),
        }

    # ── Internal ────────────────────────────────────────────────────────────

    def _persist(self, verdict: SelfAwarenessVerdict) -> None:
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        with self._audit_path.open("a") as f:                        # type: ignore[union-attr]
            f.write(json.dumps(asdict(verdict)) + "\n")


# Re-export for backward compat (callers doing direct frozenset import)
PROTECTED_OBSERVABILITY_MODULES = _DEFAULT_PROTECTED

__all__ = [
    "SelfAwarenessInvariant",
    "SelfAwarenessVerdict",
    "PROTECTED_OBSERVABILITY_MODULES",
    "OBSERVABILITY_REDUCTION_PATTERNS",
]
