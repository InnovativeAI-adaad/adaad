# SPDX-License-Identifier: Apache-2.0
"""
Evolution pipeline MCP tools — read-only observability endpoints.

Tools registered in mcp_config.json as 'evolution-pipeline' server:
  - fitness_landscape_summary   Current per-type win/loss state + bandit status
  - weight_state                Current scoring weights from WeightAdaptor
  - epoch_recommend             Agent recommendation for next epoch
  - bandit_state                UCB1 bandit arm state and scores
  - telemetry_health            Health indicators from epoch analytics

Constitutional invariant:
    All tools here are READ-ONLY. None may write to governed surfaces,
    invoke GovernanceGate, modify weights, or mutate any state.
    Mutation is exclusively the domain of EvolutionLoop + GovernanceGate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# State paths — read from canonical data/ locations
_LANDSCAPE_PATH = Path("data/fitness_landscape_state.json")
_WEIGHT_PATH    = Path("data/weight_adaptor_state.json")
_TELEMETRY_PATH = Path("data/epoch_telemetry.json")


# ---------------------------------------------------------------------------
# fitness_landscape_summary
# ---------------------------------------------------------------------------

def fitness_landscape_summary() -> Dict[str, Any]:
    """
    Return current FitnessLandscape state: per-type records, plateau status,
    recommended agent, and live UCB1 bandit state.

    Reads from data/fitness_landscape_state.json — does NOT instantiate
    FitnessLandscape (avoids persistence side-effects in MCP context).
    """
    if not _LANDSCAPE_PATH.exists():
        return {
            "ok": True,
            "status": "no_data",
            "detail": "No fitness landscape data yet. Run at least one governed epoch.",
        }

    try:
        state = json.loads(_LANDSCAPE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "error": "landscape_read_error", "detail": str(exc)}

    records = state.get("records", {})
    bandit  = state.get("bandit", {})
    saved_at = state.get("saved_at")

    # Compute per-type win rates inline
    types_summary = {}
    for mut_type, data in records.items():
        wins   = int(data.get("wins",   0))
        losses = int(data.get("losses", 0))
        attempts = wins + losses
        win_rate = round(wins / attempts, 4) if attempts > 0 else 0.0
        types_summary[mut_type] = {
            "wins":     wins,
            "losses":   losses,
            "attempts": attempts,
            "win_rate": win_rate,
        }

    # Compute plateau: all types with >= 3 attempts below 20% win rate
    tracked = [v for v in types_summary.values() if v["attempts"] >= 3]
    is_plateau = bool(tracked and all(v["win_rate"] < 0.20 for v in tracked))

    return {
        "ok":              True,
        "types":           types_summary,
        "is_plateau":      is_plateau,
        "bandit":          bandit,
        "saved_at":        saved_at,
        "landscape_path":  str(_LANDSCAPE_PATH),
    }


# ---------------------------------------------------------------------------
# weight_state
# ---------------------------------------------------------------------------

def weight_state() -> Dict[str, Any]:
    """
    Return current WeightAdaptor state: scoring weights, EMA accuracy,
    and last-updated timestamp.

    Reads from data/weight_adaptor_state.json.
    """
    if not _WEIGHT_PATH.exists():
        return {
            "ok":     True,
            "status": "no_data",
            "detail": "No weight adaptor state yet. Run at least one governed epoch.",
        }

    try:
        state = json.loads(_WEIGHT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "error": "weight_read_error", "detail": str(exc)}

    weights = state.get("weights", {})
    return {
        "ok":              True,
        "weights":         weights,
        "epoch_count":     state.get("epoch_count", 0),
        "prediction_accuracy": state.get("prediction_accuracy"),
        "last_updated":    state.get("last_updated"),
        "weight_path":     str(_WEIGHT_PATH),
        "bounds":          {"min": 0.05, "max": 0.70},
    }


# ---------------------------------------------------------------------------
# epoch_recommend
# ---------------------------------------------------------------------------

def epoch_recommend() -> Dict[str, Any]:
    """
    Return the recommended agent persona for the next epoch.

    Uses the live BanditSelector state from the landscape file when active,
    otherwise returns the v1 decision-tree recommendation.

    Advisory only — this recommendation is an INPUT to EvolutionLoop, not
    a governance decision.
    """
    landscape_data = fitness_landscape_summary()
    if not landscape_data.get("ok") or landscape_data.get("status") == "no_data":
        return {
            "ok":               True,
            "recommended_agent": "beast",
            "reasoning":        "no_landscape_data — conservative default",
            "bandit_active":    False,
        }

    types       = landscape_data.get("types", {})
    is_plateau  = landscape_data.get("is_plateau", False)
    bandit      = landscape_data.get("bandit", {})

    # Plateau always → dream
    if is_plateau:
        return {
            "ok":                True,
            "recommended_agent": "dream",
            "reasoning":         "plateau_detected — maximum exploration",
            "bandit_active":     bandit.get("is_active", False),
            "is_plateau":        True,
        }

    # UCB1 bandit active?
    bandit_active = bool(bandit.get("is_active", False))
    if bandit_active:
        arms = bandit.get("arms", {})
        total_pulls = int(bandit.get("total_pulls", 0))
        # Recompute UCB1 scores inline (read-only, no BanditSelector instance)
        import math
        C = math.sqrt(2)
        best_agent = None
        best_score = -1.0
        for agent, arm_data in arms.items():
            pulls = int(arm_data.get("wins", 0)) + int(arm_data.get("losses", 0))
            if pulls == 0:
                score = float("inf")
            else:
                win_rate = int(arm_data.get("wins", 0)) / pulls
                score = win_rate + C * math.sqrt(math.log(max(total_pulls, 1)) / pulls)
            if best_agent is None or score > best_score or (score == best_score and agent < best_agent):
                best_agent = agent
                best_score = score
        return {
            "ok":                True,
            "recommended_agent": best_agent or "beast",
            "reasoning":         "ucb1_bandit_active",
            "bandit_active":     True,
            "bandit_total_pulls": total_pulls,
        }

    # v1 fallback: decision tree
    if not types:
        return {
            "ok": True, "recommended_agent": "beast",
            "reasoning": "no_type_records — conservative default", "bandit_active": False,
        }
    best_type = max(types, key=lambda t: (types[t]["win_rate"], -types[t]["attempts"]))
    if best_type == "structural":
        agent = "architect"
    elif best_type in ("performance", "coverage"):
        agent = "beast"
    else:
        agent = "beast"
    return {
        "ok":                True,
        "recommended_agent": agent,
        "reasoning":         f"v1_decision_tree — best_type={best_type}",
        "bandit_active":     False,
        "best_mutation_type": best_type,
    }


# ---------------------------------------------------------------------------
# bandit_state
# ---------------------------------------------------------------------------

def bandit_state() -> Dict[str, Any]:
    """
    Return the raw UCB1 bandit arm state from the landscape file.
    Useful for monitoring exploration/exploitation balance.
    """
    landscape_data = fitness_landscape_summary()
    if not landscape_data.get("ok"):
        return landscape_data

    bandit = landscape_data.get("bandit", {})
    if not bandit:
        return {
            "ok":     True,
            "status": "no_bandit_data",
            "detail": "No bandit state recorded yet.",
        }

    return {"ok": True, **bandit}


# ---------------------------------------------------------------------------
# telemetry_health
# ---------------------------------------------------------------------------

def telemetry_health() -> Dict[str, Any]:
    """
    Return health indicators from the epoch telemetry engine.
    Reads data/epoch_telemetry.json if it exists.
    """
    if not _TELEMETRY_PATH.exists():
        return {
            "ok":     True,
            "status": "no_data",
            "detail": "No epoch telemetry data yet.",
        }

    try:
        from runtime.autonomy.epoch_telemetry import EpochTelemetry
        telemetry = EpochTelemetry.load(_TELEMETRY_PATH)
        health = telemetry.health_indicators()
        return {
            "ok":              True,
            "epoch_count":     telemetry.epoch_count(),
            "health":          health,
            "has_warnings":    any(
                v.get("status") == "warning"
                for v in health.values()
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": "telemetry_read_error", "detail": str(exc)}


__all__ = [
    "fitness_landscape_summary",
    "weight_state",
    "epoch_recommend",
    "bandit_state",
    "telemetry_health",
]
