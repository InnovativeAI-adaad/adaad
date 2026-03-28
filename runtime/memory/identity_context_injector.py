# SPDX-License-Identifier: Apache-2.0
"""
IdentityContextInjector — Phase 94 · INNOV-10 MMEM
===================================================

Pre-proposal context enrichment: consults the IdentityLedger and injects
identity_consistency_score + violated_statements into CodebaseContext before
Phase 1 (proposal generation) executes in run_epoch().

Contract (MMEM-WIRE-0):
  - Called as Phase 0d in EvolutionLoop.run_epoch()
  - Failure MUST NOT block the epoch — degraded mode returns score=1.0
  - inject() is idempotent: calling twice on the same context is safe
  - inject() MUST NOT append to the IdentityLedger (MMEM-READONLY-0 by proxy)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class InjectionResult:
    """Returned by IdentityContextInjector.inject()."""
    mutation_id: str
    consistency_score: float
    violated_statements: list = field(default_factory=list)
    fallback_used: bool = False
    notes: str = ""


# ---------------------------------------------------------------------------
# IdentityContextInjector
# ---------------------------------------------------------------------------

class IdentityContextInjector:
    """Consults IdentityLedger and enriches CodebaseContext pre-proposal."""

    def __init__(self, ledger: Any) -> None:
        self._ledger = ledger

    def inject(
        self,
        context: Any,
        epoch_id: str = "unknown",
        mutation_id: Optional[str] = None,
    ) -> InjectionResult:
        """Consult IdentityLedger and inject result into context.

        MMEM-WIRE-0: never raises — degrades gracefully.
        """
        try:
            return self._inject_impl(context, epoch_id, mutation_id)
        except Exception as exc:  # noqa: BLE001
            # MMEM-WIRE-0: degrade, never block
            mid = mutation_id or "unknown"
            try:
                context.identity_consistency_score = 1.0
                context.identity_violated_statements = []
            except Exception:  # noqa: BLE001
                pass
            return InjectionResult(
                mutation_id=mid,
                consistency_score=1.0,
                fallback_used=True,
                notes=f"MMEM-WIRE-0 degraded: {exc!r}",
            )

    def _inject_impl(
        self,
        context: Any,
        epoch_id: str,
        mutation_id: Optional[str],
    ) -> InjectionResult:
        """Inner implementation.

        Steps:
          1. Derive mutation_intent from context
          2. Derive diff_summary from context
          3. Call self._ledger.check()
          4. Write result fields onto context
          5. Return InjectionResult
        """
        mid = mutation_id or getattr(context, "mutation_id", None) or epoch_id
        intent = self._build_intent(context)
        diff = self._build_diff(context)

        result = self._ledger.check(mid, intent, diff)

        context.identity_consistency_score = result.consistency_score
        context.identity_violated_statements = result.violated_statements

        return InjectionResult(
            mutation_id=mid,
            consistency_score=result.consistency_score,
            violated_statements=result.violated_statements,
            fallback_used=result.fallback_used,
            notes=result.notes,
        )

    def _build_intent(self, context: Any) -> str:
        """Derive a mutation_intent string from CodebaseContext."""
        parts = []
        fp = getattr(context, "file_path", None)
        desc = getattr(context, "description", None)
        mtype = getattr(context, "mutation_type", None)
        if fp:
            parts.append(f"file: {fp}")
        if mtype:
            parts.append(f"type: {mtype}")
        if desc:
            parts.append(str(desc))
        return " | ".join(parts) if parts else "unknown mutation"

    def _build_diff(self, context: Any) -> str:
        """Derive a diff_summary string from CodebaseContext."""
        before = getattr(context, "before_source", "") or ""
        after = getattr(context, "after_source", "") or ""
        if not before and not after:
            return ""
        return f"before_len={len(before)} after_len={len(after)}"


__all__ = [
    "IdentityContextInjector",
    "InjectionResult",
]
