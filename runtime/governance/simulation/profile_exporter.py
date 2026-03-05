# SPDX-License-Identifier: Apache-2.0
"""Governance Profile Exporter — ADAAD-8 / PR-13 (Milestone)

Exports a completed simulation run as a self-contained GovernanceProfile
artifact. Profiles are deterministic: identical ledger slice + identical
SimulationPolicy + epoch-bound scoring versions → identical profile.

The 'simulation: true' field is always present in every exported profile
and is enforced by the schema (schemas/governance_profile.v1.json).

Design:
- GovernanceProfile is a frozen dataclass — fields cannot be mutated.
- export_profile() accepts a SimulationRunResult and returns a GovernanceProfile.
- serialize_profile() returns the canonical JSON-serialisable dict.
- validate_profile_schema() validates the dict against governance_profile.v1.json.
- profile_digest() computes a deterministic SHA-256 of the serialised profile.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.governance.simulation.constraint_interpreter import SimulationPolicy
from runtime.governance.simulation.epoch_simulator import SimulationRunResult


# ---------------------------------------------------------------------------
# Schema path
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "governance_profile.v1.json"

GOVERNANCE_PROFILE_SCHEMA_VERSION = "governance_profile.v1"


# ---------------------------------------------------------------------------
# GovernanceProfile
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GovernanceProfile:
    """A self-contained, deterministic governance simulation export artifact.

    Fields:
        simulation: Always True — schema-enforced.
        schema_version: 'governance_profile.v1'
        generated_at: ISO-8601 timestamp (epoch-sourced for determinism).
        epoch_range: {start, end} epoch IDs.
        simulation_policy: Serialised SimulationPolicy dict.
        summary: Aggregate metrics from the simulation run.
        epoch_results: Per-epoch result dicts.
        scoring_versions: Scoring algorithm versions used during replay.
        profile_digest: SHA-256 of the serialised profile (self-referential, set post-construction).
    """
    simulation: bool
    schema_version: str
    generated_at: str
    epoch_range: Dict[str, Optional[str]]
    simulation_policy: Dict[str, Any]
    summary: Dict[str, Any]
    epoch_results: List[Dict[str, Any]]
    scoring_versions: Dict[str, str]
    profile_digest: str

    def __post_init__(self) -> None:
        if not self.simulation:
            raise ValueError(
                "GovernanceProfile.simulation must be True. "
                "Only simulation runs may be exported as GovernanceProfiles."
            )

    def to_dict(self) -> Dict[str, Any]:
        """Return the canonical JSON-serialisable dict."""
        return {
            "schema_version": self.schema_version,
            "simulation": self.simulation,
            "generated_at": self.generated_at,
            "epoch_range": dict(self.epoch_range),
            "simulation_policy": dict(self.simulation_policy),
            "summary": dict(self.summary),
            "epoch_results": list(self.epoch_results),
            "scoring_versions": dict(self.scoring_versions),
            "profile_digest": self.profile_digest,
        }


# ---------------------------------------------------------------------------
# Determinism helpers
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(obj).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

def export_profile(
    run_result: SimulationRunResult,
    policy: SimulationPolicy,
    *,
    generated_at: str = "deterministic",
) -> GovernanceProfile:
    """Export a SimulationRunResult as a GovernanceProfile artifact.

    Args:
        run_result: A completed SimulationRunResult from EpochReplaySimulator.
        policy: The SimulationPolicy used to produce the run_result.
        generated_at: ISO-8601 timestamp string. Defaults to 'deterministic'
            for fully deterministic test contexts; production callers should
            pass a real timestamp.

    Returns:
        GovernanceProfile — frozen, with profile_digest computed.

    Raises:
        ValueError: If run_result.simulation is not True or policy.simulation
            is not True.
    """
    if not run_result.simulation:
        raise ValueError("Cannot export a non-simulation run as a GovernanceProfile.")
    if not policy.simulation:
        raise ValueError("Cannot export a profile from a non-simulation policy.")

    epoch_results_dicts = [r.to_dict() for r in run_result.epoch_results]

    # Epoch range from results
    epoch_ids = [r.epoch_id for r in run_result.epoch_results]
    epoch_range: Dict[str, Optional[str]] = {
        "start": epoch_ids[0] if epoch_ids else None,
        "end": epoch_ids[-1] if epoch_ids else None,
    }

    # Collect unique scoring versions used
    scoring_versions: Dict[str, str] = {}
    for r in run_result.epoch_results:
        v = r.scoring_algorithm_version
        if v and v != "unknown":
            scoring_versions[f"epoch_{r.epoch_id}"] = v
    # Summary version (most common)
    all_versions = [r.scoring_algorithm_version for r in run_result.epoch_results if r.scoring_algorithm_version != "unknown"]
    scoring_versions["fitness"] = all_versions[0] if all_versions else "unknown"

    summary = {
        "epochs_evaluated": run_result.epoch_count,
        "velocity_impact_pct": run_result.velocity_impact_pct,
        "mutations_gated": run_result.total_mutations_blocked,
        "total_mutations_actual": run_result.total_mutations_actual,
        "total_mutations_simulated": run_result.total_mutations_simulated,
        "drift_risk_delta_mean": run_result.drift_risk_delta_mean,
        "governance_health_score_mean": run_result.governance_health_score_mean,
        "policy_digest": run_result.policy_digest,
        "run_digest": run_result.run_digest,
    }

    # Build pre-digest payload (profile_digest is computed over the full body)
    pre_digest_payload = {
        "schema_version": GOVERNANCE_PROFILE_SCHEMA_VERSION,
        "simulation": True,
        "generated_at": generated_at,
        "epoch_range": epoch_range,
        "simulation_policy": policy.to_dict(),
        "summary": summary,
        "epoch_results": epoch_results_dicts,
        "scoring_versions": scoring_versions,
    }
    profile_digest = _sha256_digest(pre_digest_payload)

    return GovernanceProfile(
        simulation=True,
        schema_version=GOVERNANCE_PROFILE_SCHEMA_VERSION,
        generated_at=generated_at,
        epoch_range=epoch_range,
        simulation_policy=policy.to_dict(),
        summary=summary,
        epoch_results=epoch_results_dicts,
        scoring_versions=scoring_versions,
        profile_digest=profile_digest,
    )


def validate_profile_schema(profile_dict: Dict[str, Any]) -> bool:
    """Validate a profile dict against the governance_profile.v1.json schema.

    Returns True if valid. Raises ValueError with schema validation details
    if invalid. Requires the 'jsonschema' package; if not available, performs
    structural field validation only.

    simulation: true is always required and validated.
    """
    # Structural validation — always performed
    required_fields = [
        "schema_version", "simulation", "generated_at", "epoch_range",
        "simulation_policy", "summary", "epoch_results", "scoring_versions",
        "profile_digest",
    ]
    missing = [f for f in required_fields if f not in profile_dict]
    if missing:
        raise ValueError(f"GovernanceProfile missing required fields: {missing}")

    if not profile_dict.get("simulation"):
        raise ValueError("GovernanceProfile.simulation must be true.")

    if profile_dict.get("schema_version") != GOVERNANCE_PROFILE_SCHEMA_VERSION:
        raise ValueError(
            f"GovernanceProfile.schema_version must be '{GOVERNANCE_PROFILE_SCHEMA_VERSION}', "
            f"got {profile_dict.get('schema_version')!r}"
        )

    if not isinstance(profile_dict.get("epoch_results"), list):
        raise ValueError("GovernanceProfile.epoch_results must be a list.")

    if not isinstance(profile_dict.get("simulation_policy"), dict):
        raise ValueError("GovernanceProfile.simulation_policy must be a dict.")

    sim_policy = profile_dict["simulation_policy"]
    if not sim_policy.get("simulation"):
        raise ValueError("GovernanceProfile.simulation_policy.simulation must be true.")

    # JSON schema validation (best-effort if jsonschema available)
    try:
        import jsonschema
        if _SCHEMA_PATH.exists():
            schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(instance=profile_dict, schema=schema)
    except ImportError:
        pass  # jsonschema not available; structural checks above are sufficient
    except Exception as exc:
        raise ValueError(f"GovernanceProfile JSON schema validation failed: {exc}") from exc

    return True


def profile_digest(profile: GovernanceProfile) -> str:
    """Return the deterministic SHA-256 digest of the profile's canonical form."""
    return profile.profile_digest


__all__ = [
    "GovernanceProfile",
    "GOVERNANCE_PROFILE_SCHEMA_VERSION",
    "export_profile",
    "validate_profile_schema",
    "profile_digest",
]
