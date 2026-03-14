# SPDX-License-Identifier: Apache-2.0
"""Phase 67 — Innovations Wiring Adapter.

Bridges the ADAADInnovationEngine substrate (Phase 420 / PR #420) into the
live ConstitutionalEvolutionLoop lifecycle.  All injections are additive and
fail-safe; no constitutional invariant is altered.

Injection points
================
Step 4  (PROPOSAL-GENERATE)   — Vision Mode forecast + Personality selection
                                 are computed and injected into proposal context
                                 before ProposalEngine.generate() is called.
Step 10 (GOVERNANCE-GATE)     — Governance Plugins run AFTER GovernanceGate
                                 approves a mutation.  Plugin failure blocks
                                 promotion (GPLUGIN-BLOCK-0).
Post-epoch                    — Self-reflection report computed whenever
                                 epoch_seq % REFLECTION_CADENCE == 0;
                                 written to state["reflection_report"].

Constitutional invariants
=========================
CEL-ORDER-0       The 14-step sequence is never altered.  Innovations wiring
                  runs _within_ existing step overrides.
CEL-WIRE-FAIL-0   All innovation hooks are wrapped in try/except; any failure
                  logs a WARNING and the step continues (non-blocking for
                  vision/personality; blocking for G-plugins per GPLUGIN-BLOCK-0).
GPLUGIN-BLOCK-0   A G-plugin failure blocks promotion identically to a
                  GovernanceGate rejection.  G-plugins are non-bypassable.
GPLUGIN-POST-0    G-plugins evaluate only AFTER GovernanceGate approves.  A
                  GovernanceGate rejection short-circuits before plugins run.
INNOV-DETERM-0    All innovation computations must be deterministic for equal
                  inputs (ADAADInnovationEngine contract).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence

from runtime.innovations import (
    ADAADInnovationEngine,
    GovernancePlugin,
    MutationPersonality,
    ReflectionReport,
    VisionProjection,
)
from runtime.personality_profiles import (
    DEFAULT_PERSONALITY_PROFILES,
    PersonalityProfileStore,
)
from runtime.seed_evolution import run_seed_evolution  # Phase 71

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency — bus imported on first use
def _bus():
    from runtime.innovations_bus import get_bus  # noqa: PLC0415
    return get_bus()

# Self-reflection fires every N epochs.  Approved by Phase 67 spec.
REFLECTION_CADENCE: int = 100

# Vision Mode: default horizon in epochs.
VISION_HORIZON: int = 100

# Default personality profiles for Architect, Dream, and Beast agents.
DEFAULT_PERSONALITIES: List[MutationPersonality] = list(DEFAULT_PERSONALITY_PROFILES)
_PROFILE_STORE = PersonalityProfileStore()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_vision_forecast(
    engine: ADAADInnovationEngine,
    state: Dict[str, Any],
    horizon: int = VISION_HORIZON,
) -> Optional[VisionProjection]:
    """Run Vision Mode using history stored in state["oracle_events"].

    Fail-safe: returns None on any error (CEL-WIRE-FAIL-0).
    """
    try:
        events: Sequence[Mapping[str, Any]] = state.get("oracle_events", [])
        projection = engine.run_vision_mode(events, horizon_epochs=horizon)
        return projection
    except Exception as exc:  # noqa: BLE001
        logger.warning("innovations_wiring: vision_forecast failed — %s", exc)
        return None


def select_agent_personality(
    engine: ADAADInnovationEngine,
    epoch_id: str,
    profiles: Optional[List[MutationPersonality]] = None,
    strategy_id: str = "",
) -> Optional[MutationPersonality]:
    """Deterministically select a personality profile for this epoch.

    Fail-safe: returns None on any error (CEL-WIRE-FAIL-0).
    Emits personality frame to innovations bus (IBUS-FAILSAFE-0).
    """
    try:
        chosen_profiles = profiles or _PROFILE_STORE.load_profiles() or DEFAULT_PERSONALITIES
        p = engine.select_personality(chosen_profiles, epoch_id=epoch_id)
        _PROFILE_STORE.record_selection(epoch_id=epoch_id, profile=p, strategy_id=strategy_id)
        try:
            from runtime.innovations_bus import emit_personality  # noqa: PLC0415
            emit_personality(p.agent_id, p.philosophy, list(p.vector), epoch_id)
        except Exception:  # noqa: BLE001
            pass
        return p
    except Exception as exc:  # noqa: BLE001
        logger.warning("innovations_wiring: personality_select failed — %s", exc)
        return None


def record_personality_impact(
    *,
    epoch_id: str,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist deterministic epoch-level personality usage impact and vector deltas."""
    try:
        active = dict(state.get("active_personality", {}))
        if not active:
            return {}
        active.setdefault("strategy_id", state.get("context", {}).get("strategy_id", ""))
        impact = _PROFILE_STORE.record_impact(
            epoch_id=epoch_id,
            active_personality=active,
            fitness_summary=state.get("fitness_summary", ()),
            mutations_succeeded=state.get("mutations_succeeded", ()),
        )
        if impact:
            state["personality_impact"] = impact
        return impact
    except Exception as exc:  # noqa: BLE001
        logger.warning("innovations_wiring: personality_impact failed — %s", exc)
        return {}


def run_gplugins(
    engine: ADAADInnovationEngine,
    mutation: Mapping[str, Any],
    plugins: List[GovernancePlugin],
) -> List[Dict[str, Any]]:
    """Evaluate G-plugins against an approved mutation.

    Returns a list of result dicts.  Fail-safe on engine errors (returns empty
    list); individual plugin failures surface as passed=False results.
    """
    try:
        results = engine.run_plugins(mutation, plugins)
        return [
            {
                "plugin_id": r.plugin_id,
                "passed": r.passed,
                "message": r.message,
            }
            for r in results
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("innovations_wiring: gplugins failed — %s", exc)
        return []


def run_self_reflection(
    engine: ADAADInnovationEngine,
    epoch_id: str,
    epoch_seq: int,
    state: Dict[str, Any],
    cadence: int = REFLECTION_CADENCE,
) -> Optional[ReflectionReport]:
    """Emit a self-reflection report every `cadence` epochs.

    Writes result into state["reflection_report"].  Fail-safe (CEL-WIRE-FAIL-0).
    """
    try:
        if cadence <= 0:
            logger.warning(
                "innovations_wiring: self_reflect invalid cadence=%s; skipping",
                cadence,
            )
            return None
        if epoch_seq % cadence != 0:
            return None
        agent_scores: Dict[str, float] = state.get("agent_scores", {})
        # Derive agent scores from fitness_summary if agent_scores not explicit
        if not agent_scores:
            for mid, score in state.get("fitness_summary", ()):
                # Infer agent from mutation_id prefix heuristic
                for agent in ("architect", "dream", "beast"):
                    if agent in mid.lower():
                        agent_scores[agent] = agent_scores.get(agent, 0.0) + score
                        break
        report = engine.self_reflect(epoch_id=epoch_id, agent_scores=agent_scores)
        state["reflection_report"] = {
            "epoch_id": report.epoch_id,
            "dominant_agent": report.dominant_agent,
            "underperforming_agent": report.underperforming_agent,
            "rebalance_hint": report.rebalance_hint,
            "cadence": cadence,
        }
        logger.info(
            "innovations_wiring: self_reflect epoch=%s dominant=%s hint=%s",
            epoch_id,
            report.dominant_agent,
            report.rebalance_hint,
        )
        try:
            from runtime.innovations_bus import emit_reflection  # noqa: PLC0415
            emit_reflection(epoch_id, report.dominant_agent, report.underperforming_agent, report.rebalance_hint)
        except Exception:  # noqa: BLE001
            pass
        return report
    except Exception as exc:  # noqa: BLE001
        logger.warning("innovations_wiring: self_reflect failed — %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "DEFAULT_PERSONALITIES",
    "REFLECTION_CADENCE",
    "VISION_HORIZON",
    "run_gplugins",
    "record_personality_impact",
    "run_self_reflection",
    "run_seed_evolution",
    "run_vision_forecast",
    "select_agent_personality",
]
