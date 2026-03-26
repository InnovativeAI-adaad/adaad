# SPDX-License-Identifier: Apache-2.0
"""Tenant-scoped filesystem and payload helpers for ledger isolation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

_SCOPE_PATTERN = re.compile(r"^[a-zA-Z0-9._:-]+$")


def _normalize_scope_value(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or not _SCOPE_PATTERN.fullmatch(normalized):
        raise ValueError(f"invalid_{field_name}")
    return normalized


def normalize_tenant_scope(tenant_context: Mapping[str, str]) -> tuple[str, str]:
    tenant_id = _normalize_scope_value(tenant_context.get("tenant_id", ""), field_name="tenant_id")
    workspace_id = _normalize_scope_value(tenant_context.get("workspace_id", ""), field_name="workspace_id")
    return tenant_id, workspace_id


def tenant_partition_path(base_path: Path, tenant_context: Mapping[str, str] | None) -> Path:
    """Resolve tenant-partitioned ledger path when context is provided."""
    if not tenant_context:
        return base_path
    tenant_id, workspace_id = normalize_tenant_scope(tenant_context)
    return base_path.parent / "tenants" / tenant_id / workspace_id / base_path.name


def payload_in_tenant_scope(entry: Mapping[str, Any], tenant_context: Mapping[str, str]) -> bool:
    tenant_id, workspace_id = normalize_tenant_scope(tenant_context)
    payload = entry.get("payload") if isinstance(entry.get("payload"), Mapping) else {}
    entry_tenant_id = str(payload.get("tenant_id") or entry.get("tenant_id") or "").strip()
    entry_workspace_id = str(payload.get("workspace_id") or entry.get("workspace_id") or "").strip()
    return entry_tenant_id == tenant_id and entry_workspace_id == workspace_id
