# SPDX-License-Identifier: Apache-2.0
"""Boot environment and preflight helpers for app composition roots."""

from __future__ import annotations

import json
import os
from typing import Any

from app import APP_ROOT
from runtime.api.runtime_services import metrics
from runtime.preflight import validate_constitution_version_config

BOOT_KNOWN_ENVS: frozenset[str] = frozenset({"dev", "test", "staging", "production", "prod"})
BOOT_STRICT_ENVS: frozenset[str] = frozenset({"staging", "production", "prod"})


def governance_ci_mode_enabled() -> bool:
    return os.getenv("ADAAD_GOVERNANCE_CI_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def apply_governance_ci_mode_defaults() -> None:
    os.environ.setdefault("ADAAD_FORCE_DETERMINISTIC_PROVIDER", "1")
    os.environ.setdefault("ADAAD_DETERMINISTIC_SEED", "adaad-governance-ci")
    os.environ.setdefault("ADAAD_RESOURCE_MEMORY_MB", "2048")
    os.environ.setdefault("ADAAD_RESOURCE_CPU_SECONDS", "30")
    os.environ.setdefault("ADAAD_RESOURCE_WALL_SECONDS", "60")


def load_storage_manager_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_config: dict[str, Any] = {}
    governance_config: dict[str, Any] = {}

    profile_path = APP_ROOT.parent / "governance_runtime_profile.lock.json"
    if profile_path.exists():
        try:
            profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
            runtime_manifest = profile_payload.get("runtime_manifest", {})
            if isinstance(runtime_manifest, dict):
                storage_config = runtime_manifest.get("storage_manager", {})
                if isinstance(storage_config, dict):
                    runtime_config.update(storage_config)
        except (OSError, ValueError, TypeError):
            runtime_config = {}

    governance_path = APP_ROOT.parent / "governance" / "storage_manager.json"
    if governance_path.exists():
        try:
            governance_payload = json.loads(governance_path.read_text(encoding="utf-8"))
            if isinstance(governance_payload, dict):
                governance_config.update(governance_payload)
        except (OSError, ValueError, TypeError):
            governance_config = {}

    return governance_config, runtime_config




def validate_boot_constitution_version() -> None:
    """Fail closed if configured constitution version does not match runtime canon."""
    result = validate_constitution_version_config()
    if not result.get("ok"):
        raise SystemExit(f"CRITICAL: {result.get('reason', 'constitution_version_validation_failed')}")

def validate_boot_environment() -> None:
    """Fail closed on invalid or unsafe environment configuration at startup."""
    validate_boot_constitution_version()
    env = (os.getenv("ADAAD_ENV") or "").strip().lower()
    if not env:
        raise SystemExit(
            "CRITICAL: ADAAD_ENV is not set. Set to one of: dev, test, staging, production"
        )
    if env not in BOOT_KNOWN_ENVS:
        raise SystemExit(
            f"CRITICAL: ADAAD_ENV={env!r} is not a recognised environment. "
            f"Permitted: {sorted(BOOT_KNOWN_ENVS)}"
        )
    if env in BOOT_STRICT_ENVS and os.getenv("CRYOVANT_DEV_MODE"):
        raise SystemExit(
            f"CRITICAL: CRYOVANT_DEV_MODE is set in strict environment {env!r}. "
            "This configuration is not permitted."
        )
    if env in BOOT_STRICT_ENVS:
        has_key = os.getenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY") or any(
            v for k, v in os.environ.items() if k.startswith("ADAAD_GOVERNANCE_SESSION_KEY_")
        )
        if not has_key:
            raise SystemExit(
                "CRITICAL: missing_governance_signing_key — "
                "ADAAD_GOVERNANCE_SESSION_SIGNING_KEY must be set in strict environment."
            )
    metrics.log(
        event_type="boot_env_validated",
        payload={"env": env},
        level="INFO",
    )

