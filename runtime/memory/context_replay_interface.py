# SPDX-License-Identifier: Apache-2.0
"""
ContextReplayInterface — reads craft patterns from the SoulboundLedger and
injects distilled context digests into the AIMutationProposer proposal cycle.

Purpose:
    Closes the Phase 9 loop: craft patterns extracted from past epochs
    (SoulboundLedger) are replayed as context enrichments that guide the
    AI mutation agents toward high-signal mutation categories.

    The replay mechanism is deliberately lightweight:
    - It reads the N most recent ``craft_pattern`` entries from the ledger.
    - Filters out entries with ``signal_quality_flag: low_velocity`` (CF-3).
    - Derives a ``context_digest`` summarising dominant patterns and elite stats.
    - Injects this digest into ``CodebaseContext.explore_ratio`` and as a
      supplemental annotation into the proposal user message via a sidecar dict.

Architecture:
    ContextReplayInterface is purely a READ layer over SoulboundLedger.
    It writes one journal event (``context_replay_injected.v1``) per successful
    replay and one ``craft_replay_skipped.v1`` when no valid entries are available.

Injection contract:
    The returned ``ReplayInjection`` carries:
        context_digest  — SHA-256 of the canonical replay payload
        dominant_pattern — most frequent dominant pattern across window
        mean_elite_score — mean elite_count-weighted score across window
        adjusted_explore_ratio — proposed explore_ratio for next epoch
        signal_quality_ok — False if all window entries had low_velocity flag

    The caller (typically EvolutionLoop or AIMutationProposer wiring) is
    responsible for actually applying the injection — the interface never
    modifies shared state directly.

Constitutional invariants:
    - GovernanceGate retains sole mutation approval authority. Replay injections
      are advisory context only; they cannot alter mutation approval outcomes.
    - No ledger write occurs here — replay is read-only.
    - Deterministic: given identical ledger state, identical injection is returned.
    - Signal quality gate: low_velocity entries are excluded; if all entries in
      the window are low_velocity, replay is skipped with ``signal_quality_ok=False``.
    - soulbound_privacy_invariant (Constitution v0.5.0): replay entries must not
      expose raw payload content — only context_digest and aggregate statistics
      are propagated to the proposal layer.

Android/Pydroid3 compatibility:
    - Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.governance.foundation import canonical_json
from runtime.memory.soulbound_ledger import SoulboundLedger

# Journal — graceful no-op fallback
try:
    from security.ledger.journal import append_tx as _journal_append_tx
except ImportError:  # pragma: no cover
    def _journal_append_tx(tx_type: str, payload: Dict[str, Any], **kw: Any) -> Dict[str, Any]:  # type: ignore[misc]
        return {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPLAY_WINDOW_SIZE: int   = 5       # Number of recent entries to consider
MIN_VALID_ENTRIES: int    = 1       # Minimum non-low-velocity entries to emit injection
EXPLORE_RATIO_BOOST: float = 0.10  # Added to explore_ratio when dominant pattern = experimental
EXPLOIT_RATIO_FLOOR: float = 0.20  # Minimum explore_ratio from replay (constitutional floor)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReplayInjection:
    """Context injection derived from SoulboundLedger craft_pattern entries."""
    epoch_id:               str
    context_digest:         str          # SHA-256 of canonical replay payload
    dominant_pattern:       Optional[str]
    mean_elite_score:       float        # Mean of (elite_count / accepted_count) across window
    adjusted_explore_ratio: float        # Proposed explore_ratio for next epoch
    signal_quality_ok:      bool         # False iff all window entries had low_velocity flag
    valid_entry_count:      int
    window_size:            int
    skipped:                bool = False
    skip_reason:            Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "epoch_id":               self.epoch_id,
            "context_digest":         self.context_digest,
            "dominant_pattern":       self.dominant_pattern,
            "mean_elite_score":       round(self.mean_elite_score, 4),
            "adjusted_explore_ratio": round(self.adjusted_explore_ratio, 4),
            "signal_quality_ok":      self.signal_quality_ok,
            "valid_entry_count":      self.valid_entry_count,
            "window_size":            self.window_size,
            "skipped":                self.skipped,
            "skip_reason":            self.skip_reason,
        }


# ---------------------------------------------------------------------------
# ContextReplayInterface
# ---------------------------------------------------------------------------

class ContextReplayInterface:
    """Reads craft patterns from SoulboundLedger and produces ReplayInjections.

    Usage::

        replay = ContextReplayInterface(ledger=ledger)
        injection = replay.build_injection(epoch_id="epoch-043")
        if not injection.skipped and injection.signal_quality_ok:
            context.explore_ratio = injection.adjusted_explore_ratio

    Args:
        ledger:       SoulboundLedger instance (read-only usage).
        audit_writer: Optional override for journal writes.
        window_size:  Number of recent entries to read (default: REPLAY_WINDOW_SIZE).
        min_valid:    Minimum valid (non-low-velocity) entries to emit (default: MIN_VALID_ENTRIES).
    """

    def __init__(
        self,
        ledger: SoulboundLedger,
        audit_writer: Optional[Any] = None,
        window_size: int = REPLAY_WINDOW_SIZE,
        min_valid: int = MIN_VALID_ENTRIES,
    ) -> None:
        self._ledger       = ledger
        self._audit        = audit_writer or _journal_append_tx
        self._window_size  = window_size
        self._min_valid    = min_valid

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_injection(self, *, epoch_id: str) -> ReplayInjection:
        """Build a ReplayInjection from recent craft_pattern ledger entries.

        Returns a skipped injection if:
        - No craft_pattern entries exist in the ledger.
        - All entries in the window have signal_quality_flag = 'low_velocity'.
        - Valid entry count < min_valid.

        Emits ``context_replay_injected.v1`` on success,
        ``craft_replay_skipped.v1`` on skip.
        """
        # --- Read recent craft_pattern entries from ledger ---
        all_entries = self._read_craft_pattern_entries()

        if not all_entries:
            return self._skipped(epoch_id, "no_craft_pattern_entries_in_ledger")

        # --- Window: take the N most recent ---
        window = all_entries[-self._window_size:]

        # --- Filter: exclude low_velocity entries (CF-3 guard) ---
        valid_entries = [
            e for e in window
            if e.get("signal_quality_flag") != "low_velocity"
        ]

        if len(valid_entries) < self._min_valid:
            return self._skipped(
                epoch_id,
                f"valid_entries_{len(valid_entries)}_below_minimum_{self._min_valid}",
            )

        # --- Derive dominant_pattern across valid entries ---
        pattern_counts: Dict[str, int] = {}
        for e in valid_entries:
            dp = e.get("dominant_pattern")
            if dp:
                pattern_counts[dp] = pattern_counts.get(dp, 0) + 1
        dominant_pattern = (
            max(pattern_counts, key=pattern_counts.__getitem__)
            if pattern_counts else None
        )

        # --- Compute mean elite score (elite_count / accepted_count per entry) ---
        elite_ratios = []
        for e in valid_entries:
            accepted_count = int(e.get("accepted_count", 0) or 0)
            # Sum elite_count across all agent_stats in entry
            agent_stats = e.get("agent_stats", []) or []
            total_elite = sum(int(s.get("elite_count", 0)) for s in agent_stats)
            ratio = (total_elite / accepted_count) if accepted_count > 0 else 0.0
            elite_ratios.append(min(1.0, ratio))
        mean_elite_score = sum(elite_ratios) / len(elite_ratios) if elite_ratios else 0.0

        # --- Compute adjusted_explore_ratio ---
        base_ratio = 0.50
        if dominant_pattern == "experimental":
            base_ratio += EXPLORE_RATIO_BOOST
        elif dominant_pattern in ("structural", "performance"):
            base_ratio -= EXPLORE_RATIO_BOOST
        # Clamp: [EXPLOIT_RATIO_FLOOR, 1.0]
        adjusted_explore_ratio = max(EXPLOIT_RATIO_FLOOR, min(1.0, base_ratio))

        # --- Build context_digest (soulbound_privacy_invariant: no raw payload) ---
        digest_payload = {
            "epoch_id":            epoch_id,
            "dominant_pattern":    dominant_pattern,
            "mean_elite_score":    round(mean_elite_score, 4),
            "valid_entry_count":   len(valid_entries),
            "window_size":         len(window),
            "pattern_counts":      pattern_counts,
        }
        context_digest = hashlib.sha256(
            canonical_json(digest_payload).encode("utf-8")
        ).hexdigest()

        injection = ReplayInjection(
            epoch_id               = epoch_id,
            context_digest         = context_digest,
            dominant_pattern       = dominant_pattern,
            mean_elite_score       = round(mean_elite_score, 4),
            adjusted_explore_ratio = adjusted_explore_ratio,
            signal_quality_ok      = True,
            valid_entry_count      = len(valid_entries),
            window_size            = len(window),
        )

        self._emit_injected(injection)
        return injection

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_craft_pattern_entries(self) -> List[Dict[str, Any]]:
        """Read all craft_pattern entries from the ledger store."""
        try:
            raw_entries = self._ledger._all_entries()  # noqa: SLF001
            return [
                e.get("context_payload", {})
                for e in raw_entries
                if e.get("context_type") == "craft_pattern"
                and isinstance(e.get("context_payload"), dict)
            ]
        except Exception:  # noqa: BLE001
            return []

    def _skipped(self, epoch_id: str, reason: str) -> ReplayInjection:
        injection = ReplayInjection(
            epoch_id               = epoch_id,
            context_digest         = "",
            dominant_pattern       = None,
            mean_elite_score       = 0.0,
            adjusted_explore_ratio = 0.50,
            signal_quality_ok      = False,
            valid_entry_count      = 0,
            window_size            = 0,
            skipped                = True,
            skip_reason            = reason,
        )
        self._emit("craft_replay_skipped.v1", {"epoch_id": epoch_id, "reason": reason})
        return injection

    def _emit(self, tx_type: str, payload: Dict[str, Any]) -> None:
        try:
            self._audit(tx_type, payload)
        except Exception:  # noqa: BLE001
            pass

    def _emit_injected(self, injection: ReplayInjection) -> None:
        self._emit(
            "context_replay_injected.v1",
            {
                "epoch_id":               injection.epoch_id,
                "context_digest":         injection.context_digest,
                "dominant_pattern":       injection.dominant_pattern,
                "mean_elite_score":       injection.mean_elite_score,
                "adjusted_explore_ratio": injection.adjusted_explore_ratio,
                "valid_entry_count":      injection.valid_entry_count,
                "window_size":            injection.window_size,
            },
        )


__all__ = [
    "REPLAY_WINDOW_SIZE",
    "MIN_VALID_ENTRIES",
    "EXPLORE_RATIO_BOOST",
    "EXPLOIT_RATIO_FLOOR",
    "ReplayInjection",
    "ContextReplayInterface",
]
