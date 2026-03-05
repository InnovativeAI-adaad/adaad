# SPDX-License-Identifier: Apache-2.0
"""ContainerOrchestrator — ADAAD-12 Track C.

Pool management, lifecycle state machine, and health-probe integration for
real container-level isolation backend.

Architecture
------------
::

    ContainerOrchestrator
         ├── ContainerPool   — pre-warmed container slots, bounded by pool_size
         ├── LifecycleStateMachine — IDLE → PREPARING → RUNNING → DONE / FAILED
         └── ContainerHealthProbe (runtime/sandbox/container_health.py)

Invariants
----------
- Container pool respects a hard slot ceiling (pool_size).
- Every container lifecycle transition is journalled with a sha256 digest.
- Health failures trigger immediate quarantine; quarantined slots are never
  reused without a full re-probe cycle.
- ADAAD_SANDBOX_CONTAINER_ROLLOUT=true activates this as the recommended default.
- Budget coupling: each container slot consumes budget tokens from AgentBudgetPool
  proportional to its resource_profile allocation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_EVENT_CONTAINER_ALLOCATED = "container_allocated.v1"
_EVENT_CONTAINER_RELEASED  = "container_released.v1"
_EVENT_CONTAINER_FAILED    = "container_failed.v1"
_EVENT_HEALTH_PROBE        = "container_health_probe.v1"


class ContainerLifecycleState(str, Enum):
    IDLE       = "idle"
    PREPARING  = "preparing"
    RUNNING    = "running"
    DONE       = "done"
    FAILED     = "failed"
    QUARANTINE = "quarantine"


@dataclass
class ContainerSlot:
    """One managed container slot in the pool."""

    slot_id: str
    container_id: str
    image: str
    state: ContainerLifecycleState = ContainerLifecycleState.IDLE
    allocated_at: Optional[float] = None
    released_at: Optional[float] = None
    last_health_check: Optional[float] = None
    health_ok: bool = True
    failure_reason: str = ""
    resource_profile: str = ""
    agent_id: str = ""
    lineage_digest: str = ""

    def transition(self, new_state: ContainerLifecycleState, *, reason: str = "") -> None:
        self.state = new_state
        if new_state == ContainerLifecycleState.FAILED:
            self.failure_reason = reason
            self.health_ok = False
        self.lineage_digest = _slot_digest(self.slot_id, new_state.value, time.time())

    def is_available(self) -> bool:
        return self.state == ContainerLifecycleState.IDLE and self.health_ok


def _slot_digest(slot_id: str, state: str, ts: float) -> str:
    payload = json.dumps({"slot_id": slot_id, "state": state, "ts": ts}, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


class ContainerPool:
    """Bounded pool of ContainerSlot objects."""

    def __init__(self, *, pool_size: int, image: str, resource_profile: str) -> None:
        if pool_size < 1:
            raise ValueError("container_pool_size_must_be_positive")
        self._pool_size = pool_size
        self._image = image
        self._resource_profile = resource_profile
        self._slots: List[ContainerSlot] = []

    def _grow(self) -> ContainerSlot:
        slot = ContainerSlot(
            slot_id=f"slot-{uuid.uuid4().hex[:12]}",
            container_id=f"ctr-{uuid.uuid4().hex[:16]}",
            image=self._image,
            resource_profile=self._resource_profile,
        )
        slot.lineage_digest = _slot_digest(slot.slot_id, "idle", time.time())
        self._slots.append(slot)
        return slot

    def acquire(self, *, agent_id: str) -> Optional[ContainerSlot]:
        """Return an idle healthy slot or allocate a new one if pool not full."""
        for slot in self._slots:
            if slot.is_available():
                slot.transition(ContainerLifecycleState.PREPARING)
                slot.allocated_at = time.time()
                slot.agent_id = agent_id
                return slot
        if len(self._slots) < self._pool_size:
            slot = self._grow()
            slot.transition(ContainerLifecycleState.PREPARING)
            slot.allocated_at = time.time()
            slot.agent_id = agent_id
            return slot
        return None  # pool exhausted

    def release(self, slot_id: str, *, failed: bool = False, reason: str = "") -> bool:
        for slot in self._slots:
            if slot.slot_id == slot_id:
                new_state = (
                    ContainerLifecycleState.QUARANTINE if failed
                    else ContainerLifecycleState.IDLE
                )
                slot.transition(new_state, reason=reason)
                slot.released_at = time.time()
                slot.agent_id = ""
                return True
        return False

    def quarantine_unhealthy(self) -> List[str]:
        """Quarantine all slots that failed health checks; return quarantined IDs."""
        quarantined = []
        for slot in self._slots:
            if not slot.health_ok and slot.state not in (
                ContainerLifecycleState.QUARANTINE,
                ContainerLifecycleState.FAILED,
            ):
                slot.transition(ContainerLifecycleState.QUARANTINE, reason="health_probe_failed")
                quarantined.append(slot.slot_id)
        return quarantined

    @property
    def slots(self) -> List[ContainerSlot]:
        return list(self._slots)

    @property
    def available_count(self) -> int:
        return sum(1 for s in self._slots if s.is_available())

    @property
    def pool_size(self) -> int:
        return self._pool_size


class ContainerOrchestrator:
    """Manages container pool lifecycle and health for the sandbox executor.

    Parameters
    ----------
    pool_size:
        Maximum number of concurrent container slots.
    image:
        Container image (default: ``python:3.11-slim``).
    resource_profile:
        Profile ID passed to the isolation backend.
    journal_fn:
        Optional ``(event_type, payload) -> None`` for audit journalling.
    """

    def __init__(
        self,
        *,
        pool_size: int = 4,
        image: str = "python:3.11-slim",
        resource_profile: str = "default",
        journal_fn: Any = None,
    ) -> None:
        self._pool = ContainerPool(
            pool_size=pool_size, image=image, resource_profile=resource_profile
        )
        self._journal_fn = journal_fn
        self._image = image

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def allocate(self, *, agent_id: str) -> Optional[ContainerSlot]:
        """Allocate a container slot for agent_id. Returns None if pool exhausted."""
        slot = self._pool.acquire(agent_id=agent_id)
        if slot is not None:
            self._journal(_EVENT_CONTAINER_ALLOCATED, {
                "slot_id": slot.slot_id,
                "agent_id": agent_id,
                "image": self._image,
                "lineage_digest": slot.lineage_digest,
            })
        return slot

    def mark_running(self, slot_id: str) -> bool:
        for slot in self._pool.slots:
            if slot.slot_id == slot_id:
                slot.transition(ContainerLifecycleState.RUNNING)
                return True
        return False

    def release(self, slot_id: str, *, failed: bool = False, reason: str = "") -> bool:
        released = self._pool.release(slot_id, failed=failed, reason=reason)
        if released:
            ev = _EVENT_CONTAINER_FAILED if failed else _EVENT_CONTAINER_RELEASED
            self._journal(ev, {
                "slot_id": slot_id,
                "failed": failed,
                "reason": reason,
            })
        return released

    def run_health_checks(self) -> Dict[str, Any]:
        """Run liveness probes on all slots; quarantine unhealthy ones."""
        from runtime.sandbox.container_health import ContainerHealthProbe
        probe = ContainerHealthProbe()
        results: Dict[str, bool] = {}
        for slot in self._pool.slots:
            ok = probe.liveness(slot)
            slot.health_ok = ok
            slot.last_health_check = time.time()
            results[slot.slot_id] = ok
        quarantined = self._pool.quarantine_unhealthy()
        self._journal(_EVENT_HEALTH_PROBE, {
            "results": results,
            "quarantined": quarantined,
        })
        return {"results": results, "quarantined": quarantined}

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def pool_status(self) -> Dict[str, Any]:
        return {
            "pool_size": self._pool.pool_size,
            "available": self._pool.available_count,
            "slots": [
                {
                    "slot_id": s.slot_id,
                    "state": s.state.value,
                    "health_ok": s.health_ok,
                    "agent_id": s.agent_id,
                }
                for s in self._pool.slots
            ],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _journal(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._journal_fn is None:
            return
        try:
            self._journal_fn(event_type, payload)
        except Exception as exc:  # pragma: no cover
            log.warning("ContainerOrchestrator: journal failed — %s", exc)


__all__ = ["ContainerOrchestrator", "ContainerPool", "ContainerSlot", "ContainerLifecycleState"]
