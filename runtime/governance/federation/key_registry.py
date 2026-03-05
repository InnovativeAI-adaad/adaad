# SPDX-License-Identifier: Apache-2.0
"""Trusted federation key registry loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import FrozenSet

from runtime import ROOT_DIR

_REGISTRY_PATH: Path = ROOT_DIR / "governance" / "federation_trusted_keys.json"
_CACHE: FrozenSet[str] | None = None
_REGISTRY: dict[str, str] | None = None


def _contract_error(code: str, exc: Exception | None = None):
    from .transport import FederationTransportContractError

    if exc is None:
        raise FederationTransportContractError(code)
    raise FederationTransportContractError(code) from exc


def load_trusted_key_registry(*, reload: bool = False) -> dict[str, str]:
    """Load trusted federation key registry keyed by key_id."""
    global _CACHE, _REGISTRY
    if not reload and _REGISTRY is not None:
        return _REGISTRY

    try:
        raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _contract_error("key_registry:unreadable", exc)

    entries = raw.get("trusted_keys") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        _contract_error("federation_key_registry_invalid")

    mapping: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            _contract_error("federation_key_registry_malformed")
        key_id = entry.get("key_id")
        public_key_pem = entry.get("public_key_pem")
        if not isinstance(key_id, str) or not key_id.strip() or not isinstance(public_key_pem, str) or not public_key_pem.strip():
            _contract_error("federation_key_registry_malformed")
        mapping[key_id.strip()] = public_key_pem

    _REGISTRY = mapping
    _CACHE = frozenset(mapping.keys())
    return mapping


def get_trusted_public_key(key_id: str) -> str:
    """Resolve trusted public key by key identifier."""
    normalized = str(key_id or "").strip()
    registry = load_trusted_key_registry()
    if normalized not in registry:
        _contract_error(f"federation_key_id_untrusted:{normalized}")
    return registry[normalized]
