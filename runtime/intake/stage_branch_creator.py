# SPDX-License-Identifier: Apache-2.0
"""Branch naming helpers for intake staging branches."""

from __future__ import annotations

import re


def _sanitize(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._/-]+", "-", value.strip())
    normalized = normalized.strip("-/")
    return normalized or "unknown"


def build_stage_branch_name(source_ref: str, intake_id: str, *, prefix: str = "stage/intake") -> str:
    safe_source = _sanitize(source_ref).replace("/", "-")
    safe_intake = _sanitize(intake_id).replace("/", "-")
    return f"{prefix}/{safe_source}/{safe_intake}"
