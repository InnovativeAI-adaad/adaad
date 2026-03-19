# SPDX-License-Identifier: Apache-2.0
"""Boot-time validation and environment shaping helpers."""

from __future__ import annotations

import os
from pathlib import Path


def read_adaad_version(repo_root: Path) -> str:
    """Read the repository VERSION file with deterministic fallback."""

    try:
        return (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


def governance_ci_mode_enabled() -> bool:
    return os.getenv("ADAAD_GOVERNANCE_CI_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def apply_governance_ci_mode_defaults() -> None:
    os.environ.setdefault("ADAAD_FORCE_DETERMINISTIC_PROVIDER", "1")
    os.environ.setdefault("ADAAD_DETERMINISTIC_SEED", "adaad-governance-ci")
    os.environ.setdefault("ADAAD_RESOURCE_MEMORY_MB", "2048")
    os.environ.setdefault("ADAAD_RESOURCE_CPU_SECONDS", "30")
    os.environ.setdefault("ADAAD_RESOURCE_WALL_SECONDS", "60")


def replay_env_flags() -> dict[str, str]:
    keys = [key for key in os.environ if key.startswith("ADAAD_") or key.startswith("CRYOVANT_")]
    if "PYTHONPATH" in os.environ:
        keys.append("PYTHONPATH")
    return {key: os.environ.get(key, "") for key in sorted(set(keys))}
