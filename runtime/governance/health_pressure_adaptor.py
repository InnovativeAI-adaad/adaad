# SPDX-License-Identifier: Apache-2.0
"""HealthPressureAdaptor — Phase 24

Translates GovernanceHealthAggregator health_score into an advisory
PressureAdjustment: a proposed delta to DEFAULT_TIER_CONFIG min_count values.

Design invariants:
- ALL output is advisory. advisory_only is structurally True; no runtime path
  may set it to False. GovernanceGate retains sole actual authority.
- Deterministic: same health_score → same PressureAdjustment → same digest.
- Constitutional floor preserved: no proposed min_count < CONSTITUTIONAL_FLOOR_MIN_REVIEWERS.
- Fail-safe: invalid/out-of-range health_score treated conservatively (clamped).
- 'low' tier is never adjusted (already at constitutional floor).
- All proposed min_count values capped at the tier's max_count.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from runtime.governance.review_pressure import (
    CONSTITUTIONAL_FLOOR_MIN_REVIEWERS,
    DEFAULT_TIER_CONFIG,
    validate_tier_config,
)

ADAPTOR_VERSION: str = "24.0"

# Health band boundaries (match GET /governance/health thresholds)
DEFAULT_AMBER_THRESHOLD: float = 0.80  # h < this → amber (elevated pressure)
DEFAULT_RED_THRESHOLD: float = 0.60    # h < this → red (critical pressure)

# Tiers that receive adjusted min_count under pressure (never 'low')
_ELEVATED_ADJUST_TIERS: tuple[str, ...] = ("standard", "critical")
_CRITICAL_ADJUST_TIERS: tuple[str, ...] = ("standard", "critical", "governance")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PressureAdjustment:
    """Advisory review-pressure adjustment derived from governance health score.

    All fields are deterministic given the same health_score and tier config.
    advisory_only is always True — structural invariant, never runtime-settable.
    """

    health_score: float           # input h, clamped to [0.0, 1.0]
    health_band: str              # "green" | "amber" | "red"
    pressure_tier: str            # "none" | "elevated" | "critical"
    proposed_tier_config: dict    # tier → {base_count, min_count, max_count}
    baseline_tier_config: dict    # DEFAULT_TIER_CONFIG snapshot (immutable reference)
    adjusted_tiers: tuple         # tier names with raised min_count
    advisory_only: bool           # always True
    adjustment_digest: str        # sha256 of canonical adjustment record
    adaptor_version: str          # "24.0"


# ---------------------------------------------------------------------------
# Digest helper
# ---------------------------------------------------------------------------


def _compute_adjustment_digest(
    *,
    health_score: float,
    pressure_tier: str,
    proposed_tier_config: dict,
) -> str:
    canonical = json.dumps(
        {
            "health_score": round(health_score, 8),
            "pressure_tier": pressure_tier,
            "proposed_tier_config": proposed_tier_config,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# HealthPressureAdaptor
# ---------------------------------------------------------------------------


class HealthPressureAdaptor:
    """Translate governance health score into advisory reviewer-count pressure.

    Parameters
    ----------
    tier_config:
        Base tier configuration (defaults to DEFAULT_TIER_CONFIG). Validated
        at construction via validate_tier_config().
    amber_threshold:
        h below this → elevated pressure. Default: 0.80 (green/amber boundary).
    red_threshold:
        h below this → critical pressure. Default: 0.60 (HEALTH_DEGRADED_THRESHOLD).
    """

    def __init__(
        self,
        *,
        tier_config: dict | None = None,
        amber_threshold: float = DEFAULT_AMBER_THRESHOLD,
        red_threshold: float = DEFAULT_RED_THRESHOLD,
    ) -> None:
        raw_config = tier_config if tier_config is not None else DEFAULT_TIER_CONFIG
        self._tier_config: dict = validate_tier_config(raw_config)
        self._amber_threshold = float(amber_threshold)
        self._red_threshold = float(red_threshold)

        if self._red_threshold >= self._amber_threshold:
            raise ValueError(
                f"red_threshold ({self._red_threshold}) must be less than "
                f"amber_threshold ({self._amber_threshold})"
            )

    def compute(self, health_score: float) -> PressureAdjustment:
        """Compute advisory PressureAdjustment for the given health_score.

        Parameters
        ----------
        health_score:
            Governance composite health score h ∈ [0.0, 1.0]. Values outside
            this range are clamped conservatively.
        """
        h = float(max(0.0, min(1.0, health_score)))

        # Classify health band and pressure tier
        if h < self._red_threshold:
            health_band = "red"
            pressure_tier = "critical"
            adjust_tiers = _CRITICAL_ADJUST_TIERS
        elif h < self._amber_threshold:
            health_band = "amber"
            pressure_tier = "elevated"
            adjust_tiers = _ELEVATED_ADJUST_TIERS
        else:
            health_band = "green"
            pressure_tier = "none"
            adjust_tiers = ()

        # Build proposed tier config
        proposed: dict[str, dict[str, int]] = {}
        adjusted_tier_names: list[str] = []

        for tier, cfg in self._tier_config.items():
            base = cfg["base_count"]
            lo = cfg["min_count"]
            hi = cfg["max_count"]

            if tier in adjust_tiers:
                # Raise min_count by 1, capped at max_count, floored at CONSTITUTIONAL_FLOOR
                proposed_min = min(hi, lo + 1)
                proposed_min = max(CONSTITUTIONAL_FLOOR_MIN_REVIEWERS, proposed_min)
                if proposed_min != lo:
                    adjusted_tier_names.append(tier)
            else:
                proposed_min = lo

            proposed[tier] = {
                "base_count": base,
                "min_count": proposed_min,
                "max_count": hi,
            }

        # Baseline snapshot (immutable copy of the validated tier config)
        baseline: dict[str, dict[str, int]] = {
            t: dict(c) for t, c in self._tier_config.items()
        }

        digest = _compute_adjustment_digest(
            health_score=h,
            pressure_tier=pressure_tier,
            proposed_tier_config=proposed,
        )

        return PressureAdjustment(
            health_score=h,
            health_band=health_band,
            pressure_tier=pressure_tier,
            proposed_tier_config=proposed,
            baseline_tier_config=baseline,
            adjusted_tiers=tuple(sorted(adjusted_tier_names)),
            advisory_only=True,  # structural invariant — never False
            adjustment_digest=digest,
            adaptor_version=ADAPTOR_VERSION,
        )


__all__ = [
    "ADAPTOR_VERSION",
    "DEFAULT_AMBER_THRESHOLD",
    "DEFAULT_RED_THRESHOLD",
    "HealthPressureAdaptor",
    "PressureAdjustment",
]
