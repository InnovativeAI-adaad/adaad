# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Graph-backed capability registry enforcing dependencies and monotonic scores.
"""

from __future__ import annotations

import fcntl
import time
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Tuple, cast

from runtime import ROOT_DIR, metrics
from runtime.governance.policy_artifact import GovernancePolicyError, load_governance_policy
from runtime.state.registry_store import CryovantRegistryStore

CAPABILITIES_PATH = ROOT_DIR / "data" / "capabilities.json"
_CONFLICT_RETRIES = 5


def _lock_path() -> Path:
    return CAPABILITIES_PATH.parent / f"{CAPABILITIES_PATH.name}.lock"


@contextmanager
def _capabilities_lock() -> Iterator[None]:
    lock_path = _lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _file_state(path: Path) -> Tuple[int | None, str]:
    if not path.exists():
        return None, sha256(b"{}").hexdigest()
    raw = path.read_bytes()
    return path.stat().st_mtime_ns, sha256(raw).hexdigest()


def _load() -> Dict[str, Dict[str, Any]]:
    backend = "json"
    try:
        backend = load_governance_policy().state_backend
    except GovernancePolicyError:
        backend = "json"
    store = CryovantRegistryStore(
        json_path=CAPABILITIES_PATH,
        sqlite_path=CAPABILITIES_PATH.with_suffix(".sqlite"),
        backend=backend,
    )
    return store.load_registry()


def _save(data: Dict[str, Dict[str, Any]]) -> None:
    backend = "json"
    try:
        backend = load_governance_policy().state_backend
    except GovernancePolicyError:
        backend = "json"
    store = CryovantRegistryStore(
        json_path=CAPABILITIES_PATH,
        sqlite_path=CAPABILITIES_PATH.with_suffix(".sqlite"),
        backend=backend,
    )
    store.save_registry(data)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _missing_dependencies(registry: Dict[str, Dict[str, Any]], requires: Iterable[str]) -> List[str]:
    return [req for req in requires if req not in registry]


def _has_identity_fields(identity: Mapping[str, Any] | None) -> bool:
    if not isinstance(identity, Mapping):
        return False
    required = ("tool_id", "version", "hash", "timestamp")
    return all(isinstance(identity.get(key), str) and str(identity.get(key)).strip() for key in required)


def register_capability(
    name: str,
    version: str,
    score: float,
    owner_element: str,
    requires: List[str] | None = None,
    evidence: Dict[str, Any] | None = None,
    identity: Dict[str, str] | None = None,
) -> Tuple[bool, str]:
    """Register or update capability while enforcing deps and monotonic score."""

    requires = requires or []

    if not _has_identity_fields(identity):
        metrics.log(
            event_type="capability_graph_rejected",
            payload={"name": name, "score": score, "reason": "missing_identity_fields"},
            level="ERROR",
            element_id=owner_element,
        )
        return False, "missing identity fields"

    for attempt in range(1, _CONFLICT_RETRIES + 1):
        previous_mtime, previous_digest = _file_state(CAPABILITIES_PATH)
        registry = _load()

        missing = _missing_dependencies(registry, requires)
        if missing:
            message = f"missing dependencies for {name}: {','.join(missing)}"
            metrics.log(
                event_type="capability_graph_rejected",
                payload={"name": name, "score": score, "reason": "missing_dependencies", "missing": missing},
                level="ERROR",
                element_id=owner_element,
            )
            return False, message

        existing = registry.get(name, {})
        try:
            existing_score = float(existing.get("score", -1))
        except (TypeError, ValueError):
            existing_score = -1

        if score < existing_score:
            message = f"score regression prevented for {name}"
            metrics.log(
                event_type="capability_graph_rejected",
                payload={"name": name, "score": score, "reason": "score_regression", "previous": existing_score},
                level="ERROR",
                element_id=owner_element,
            )
            return False, message

        registry[name] = {
            "name": name,
            "version": version,
            "score": score,
            "owner": owner_element,
            "requires": list(requires),
            "evidence": evidence or {},
            "identity": dict(identity or {}),
            "updated_at": _now(),
        }

        with _capabilities_lock():
            current_mtime, current_digest = _file_state(CAPABILITIES_PATH)
            if (current_mtime, current_digest) != (previous_mtime, previous_digest):
                metrics.log(
                    event_type="capability_graph_conflict",
                    payload={"name": name, "attempt": attempt, "outcome": "conflict_detected", "retries_remaining": _CONFLICT_RETRIES - attempt},
                    level="WARNING",
                    element_id=owner_element,
                )
                continue
            _save(registry)

        metrics.log(
            event_type="capability_graph_conflict",
            payload={"name": name, "attempt": attempt, "outcome": "commit_success", "retries_used": attempt - 1},
            level="INFO",
            element_id=owner_element,
        )
        break
    else:
        metrics.log(
            event_type="capability_graph_conflict",
            payload={"name": name, "outcome": "retry_exhausted", "attempts": _CONFLICT_RETRIES},
            level="ERROR",
            element_id=owner_element,
        )
        return False, f"conflict retries exhausted for {name}"

    metrics.log(
        event_type="capability_graph_registered",
        payload={"name": name, "version": version, "score": score, "owner": owner_element, "requires": list(requires)},
        level="INFO",
        element_id=owner_element,
    )
    return True, "ok"


def get_capabilities() -> Dict[str, Dict[str, Any]]:
    return _load()


def dispatch_capability(name: str) -> Tuple[bool, str, Dict[str, Any] | None]:
    registry = _load()
    entry = registry.get(name)
    if not entry:
        return False, "capability_not_found", None
    if not _has_identity_fields(entry.get("identity")):  # type: ignore[arg-type]
        return False, "missing identity fields", None
    return True, "ok", entry


def list_capabilities() -> List[Dict[str, Any]]:
    registry = _load()
    listing: List[Dict[str, Any]] = []
    for name in sorted(registry):
        entry = registry[name]
        raw_identity = entry.get("identity")
        identity = cast(Mapping[str, Any], raw_identity) if isinstance(raw_identity, dict) else {}
        listing.append(
            {
                "name": name,
                "version": entry.get("version"),
                "tool_id": identity.get("tool_id"),
                "identity_hash": identity.get("hash"),
                "identity_timestamp": identity.get("timestamp"),
            }
        )
    return listing


# ---------------------------------------------------------------------------
# Phase 65: CapabilityChange ledger record + CapabilityGraph.record_change()
# ---------------------------------------------------------------------------

import dataclasses as _dc
import hashlib as _hashlib


@_dc.dataclass
class CapabilityChange:
    """Ledger event for a promoted capability mutation.

    Written to the capability change log at CEL Step 12 (CAP-VERS-0).
    The ``change_id`` is deterministic: SHA-256 of node_id + proposal_hash
    + epoch_evidence_hash (INTEL-DET-0).
    """
    node_id: str
    old_version: str
    new_version: str
    epoch_evidence_hash: str
    proposal_hash: str
    timestamp: float = _dc.field(default_factory=lambda: __import__("time").time())

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("CapabilityChange.node_id must not be empty")
        if not self.new_version:
            raise ValueError("CapabilityChange.new_version must not be empty")

    @property
    def change_id(self) -> str:
        """Deterministic 16-char hex ID derived from proposal + evidence hash (INTEL-DET-0)."""
        raw = f"{self.node_id}:{self.proposal_hash}:{self.epoch_evidence_hash}"
        return _hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {
            "event": "CAPABILITY_CHANGE",
            "change_id": self.change_id,
            "node_id": self.node_id,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "epoch_evidence_hash": self.epoch_evidence_hash,
            "proposal_hash": self.proposal_hash,
            "timestamp": self.timestamp,
        }


# Module-level capability change ledger path (overridable via env var)
_CAP_CHANGE_LEDGER_PATH = Path(
    __import__("os").getenv("ADAAD_CAP_CHANGE_LEDGER", "data/capability_changes.jsonl")
)


def record_capability_change(
    change: "CapabilityChange",
    ledger_path: "Path | None" = None,
) -> str:
    """Append a CapabilityChange record to the capability change ledger.

    Hash-chained: returns the SHA-256 hex digest of the serialised record.
    Fail-safe: on IOError the exception is logged and ``change.change_id``
    is returned as a best-effort identifier (emit methods never propagate).

    Args:
        change: The CapabilityChange to record.
        ledger_path: Override ledger path (defaults to ADAAD_CAP_CHANGE_LEDGER).

    Returns:
        SHA-256 digest of the serialised record.
    """
    import json as _json
    import logging as _logging
    _log = _logging.getLogger(__name__)

    path = ledger_path or _CAP_CHANGE_LEDGER_PATH
    record = change.to_dict()
    serialised = _json.dumps(record, sort_keys=True, default=str)
    digest = _hashlib.sha256(serialised.encode()).hexdigest()
    record["record_hash"] = digest

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps(record, sort_keys=True, default=str) + "\n")
    except Exception:  # noqa: BLE001 — fail-safe
        _log.warning(
            "record_capability_change: failed to write ledger entry for %s",
            change.change_id, exc_info=True,
        )

    return digest


class CapabilityGraph:
    """Lightweight wrapper used by EvolutionLoop Phase 65 to record capability changes.

    Delegates persistence to ``record_capability_change``. All other capability
    graph operations (load, dispatch, list) remain as module-level functions.
    """

    def __init__(self, ledger_path: "Path | None" = None) -> None:
        self._ledger_path = ledger_path

    def record_change(self, change: "CapabilityChange") -> str:
        """Record a CapabilityChange to the capability change ledger (CAP-VERS-0).

        Returns the SHA-256 digest of the persisted record.
        """
        return record_capability_change(change, ledger_path=self._ledger_path)
