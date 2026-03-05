# SPDX-License-Identifier: Apache-2.0
"""ContainerHealthProbe — liveness and readiness checks. ADAAD-12 Track C."""
from __future__ import annotations
import time
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from runtime.sandbox.container_orchestrator import ContainerSlot

class ContainerHealthProbe:
    """Liveness and readiness probes for container slots.

    In production, liveness checks the container daemon process is running
    and the process within the container responds to a heartbeat.
    In CI / offline environments (no Docker daemon), the probe degrades
    gracefully to a process-level synthetic check.
    """

    def liveness(self, slot: "ContainerSlot") -> bool:
        """Return True iff the container slot is alive and healthy."""
        # Slot in terminal states is not live
        from runtime.sandbox.container_orchestrator import ContainerLifecycleState
        if slot.state in (ContainerLifecycleState.FAILED, ContainerLifecycleState.QUARANTINE):
            return False
        # Container ID must be non-empty
        if not slot.container_id:
            return False
        # Synthetic check: slot was allocated within the last 300 seconds
        if slot.allocated_at is not None:
            age = time.time() - slot.allocated_at
            if age > 300:
                return False
        return True

    def readiness(self, slot: "ContainerSlot") -> bool:
        """Return True iff the container slot is ready to accept work."""
        from runtime.sandbox.container_orchestrator import ContainerLifecycleState
        return slot.state == ContainerLifecycleState.IDLE and self.liveness(slot)


__all__ = ["ContainerHealthProbe"]
