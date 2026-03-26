# SPDX-License-Identifier: Apache-2.0
"""Extension SDK descriptor for public API/runtime extension points."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

EXTENSION_SDK_VERSION = "2026-03"
EXTENSION_MANIFEST_SCHEMA = "plugin.manifest.v1"
EXTENSION_CERTIFICATION_SCHEMA = "plugin.certification.v1"

_EXTENSION_DESCRIPTOR: dict[str, Any] = {
    "sdk_version": EXTENSION_SDK_VERSION,
    "docs": {
        "spec_path": "docs/extensions/SDK_SPEC.md",
    },
    "compatibility": {
        "api_major": "v1",
        "manifest_schema": EXTENSION_MANIFEST_SCHEMA,
        "certification_schema": EXTENSION_CERTIFICATION_SCHEMA,
        "runtime_min_version": "9.0.0",
        "runtime_max_version_exclusive": "10.0.0",
    },
    "deprecation_policy": {
        "compatibility_window_days": 180,
        "removal_window_days": 365,
        "phases": [
            "active",
            "deprecated",
            "sunset",
            "removed",
        ],
        "signals": [
            "openapi.deprecated=true",
            "X-ADAAD-Deprecation",
            "X-ADAAD-Sunset",
        ],
    },
    "extension_points": [
        {
            "id": "mutation.pre_submit",
            "surface": "runtime.governance.decision_pipeline",
            "io_contract": "mutation.proposal.v1",
            "determinism_required": True,
            "sandbox_required": True,
        },
        {
            "id": "mutation.post_decision",
            "surface": "runtime.evolution.runtime",
            "io_contract": "mutation.decision.v1",
            "determinism_required": True,
            "sandbox_required": True,
        },
        {
            "id": "evidence.bundle.enrichment",
            "surface": "runtime.evolution.evidence_bundle",
            "io_contract": "evidence.bundle.fragment.v1",
            "determinism_required": True,
            "sandbox_required": True,
        },
        {
            "id": "api.audit.augment",
            "surface": "server:/api/audit/*",
            "io_contract": "audit.response.extension.v1",
            "determinism_required": True,
            "sandbox_required": True,
        },
    ],
}


def extension_sdk_descriptor() -> dict[str, Any]:
    """Return a defensive copy of the extension SDK descriptor."""

    return deepcopy(_EXTENSION_DESCRIPTOR)
