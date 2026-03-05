# SPDX-License-Identifier: Apache-2.0
"""Tests for ContainerOrchestrator + ContainerHealthProbe — ADAAD-12 PR-12-02."""
from __future__ import annotations
import pytest
from runtime.sandbox.container_orchestrator import (
    ContainerOrchestrator, ContainerPool, ContainerLifecycleState
)
from runtime.sandbox.container_health import ContainerHealthProbe

class TestContainerPool:
    def _pool(self, size=3):
        return ContainerPool(pool_size=size, image="python:3.11-slim", resource_profile="default")

    def test_acquire_returns_slot(self):
        pool = self._pool()
        slot = pool.acquire(agent_id="agent-1")
        assert slot is not None
        assert slot.state == ContainerLifecycleState.PREPARING

    def test_pool_bounded_by_pool_size(self):
        pool = self._pool(size=2)
        pool.acquire(agent_id="a"); pool.acquire(agent_id="b")
        assert pool.acquire(agent_id="c") is None

    def test_release_returns_slot_to_idle(self):
        pool = self._pool()
        slot = pool.acquire(agent_id="a")
        pool.release(slot.slot_id)
        assert pool.available_count == 1

    def test_failed_release_quarantines_slot(self):
        pool = self._pool()
        slot = pool.acquire(agent_id="a")
        pool.release(slot.slot_id, failed=True, reason="oom")
        assert slot.state == ContainerLifecycleState.QUARANTINE

    def test_quarantine_unhealthy_quarantines_bad_slots(self):
        pool = self._pool()
        slot = pool.acquire(agent_id="a")
        slot.health_ok = False
        quarantined = pool.quarantine_unhealthy()
        assert slot.slot_id in quarantined

    def test_zero_pool_size_raises(self):
        with pytest.raises(ValueError):
            ContainerPool(pool_size=0, image="x", resource_profile="y")

class TestContainerOrchestrator:
    def _orch(self, journal_calls=None):
        calls = journal_calls if journal_calls is not None else []
        return ContainerOrchestrator(
            pool_size=3, image="python:3.11-slim", resource_profile="default",
            journal_fn=lambda ev, p: calls.append((ev, p))
        ), calls

    def test_allocate_returns_slot(self):
        orch, _ = self._orch()
        slot = orch.allocate(agent_id="agent-x")
        assert slot is not None

    def test_allocate_journals_event(self):
        orch, calls = self._orch()
        orch.allocate(agent_id="agent-j")
        assert any("container_allocated" in ev for ev, _ in calls)

    def test_release_ok_journals_release(self):
        orch, calls = self._orch()
        slot = orch.allocate(agent_id="a")
        orch.release(slot.slot_id)
        assert any("container_released" in ev for ev, _ in calls)

    def test_release_failed_journals_failure(self):
        orch, calls = self._orch()
        slot = orch.allocate(agent_id="a")
        orch.release(slot.slot_id, failed=True, reason="oom_kill")
        assert any("container_failed" in ev for ev, _ in calls)

    def test_mark_running_transitions_state(self):
        orch, _ = self._orch()
        slot = orch.allocate(agent_id="a")
        result = orch.mark_running(slot.slot_id)
        assert result is True
        assert slot.state == ContainerLifecycleState.RUNNING

    def test_pool_status_returns_snapshot(self):
        orch, _ = self._orch()
        orch.allocate(agent_id="a")
        status = orch.pool_status()
        assert "pool_size" in status
        assert "available" in status
        assert "slots" in status

    def test_run_health_checks_journals_probe(self):
        orch, calls = self._orch()
        slot = orch.allocate(agent_id="a")
        orch.mark_running(slot.slot_id)
        orch.release(slot.slot_id)  # back to idle
        result = orch.run_health_checks()
        assert "results" in result
        assert any("health_probe" in ev for ev, _ in calls)

class TestContainerHealthProbe:
    def _idle_slot(self):
        from runtime.sandbox.container_orchestrator import ContainerSlot
        import time
        slot = ContainerSlot(
            slot_id="s1", container_id="ctr-abc", image="python:3.11-slim",
            allocated_at=time.time(), health_ok=True
        )
        return slot

    def test_liveness_passes_for_fresh_idle_slot(self):
        probe = ContainerHealthProbe()
        slot = self._idle_slot()
        assert probe.liveness(slot) is True

    def test_liveness_fails_for_quarantined_slot(self):
        probe = ContainerHealthProbe()
        slot = self._idle_slot()
        slot.state = ContainerLifecycleState.QUARANTINE
        assert probe.liveness(slot) is False

    def test_liveness_fails_for_empty_container_id(self):
        probe = ContainerHealthProbe()
        slot = self._idle_slot()
        slot.container_id = ""
        assert probe.liveness(slot) is False

    def test_readiness_requires_idle_and_live(self):
        probe = ContainerHealthProbe()
        slot = self._idle_slot()
        assert probe.readiness(slot) is True

    def test_slot_lineage_digest_format(self):
        slot = self._idle_slot()
        assert slot.lineage_digest == ""  # not set until transition

class TestContainerLifecycleFSM:
    def test_full_lifecycle_idle_prepare_run_release(self):
        orch = ContainerOrchestrator(pool_size=2, image="python:3.11-slim", resource_profile="default")
        slot = orch.allocate(agent_id="agent-fsm")
        assert slot.state == ContainerLifecycleState.PREPARING
        orch.mark_running(slot.slot_id)
        assert slot.state == ContainerLifecycleState.RUNNING
        orch.release(slot.slot_id)
        assert slot.state == ContainerLifecycleState.IDLE

    def test_failed_lifecycle_quarantines(self):
        orch = ContainerOrchestrator(pool_size=2, image="python:3.11-slim", resource_profile="default")
        slot = orch.allocate(agent_id="agent-fail")
        orch.mark_running(slot.slot_id)
        orch.release(slot.slot_id, failed=True, reason="segfault")
        assert slot.state == ContainerLifecycleState.QUARANTINE

    def test_lineage_digest_set_on_transition(self):
        orch = ContainerOrchestrator(pool_size=2, image="python:3.11-slim", resource_profile="default")
        slot = orch.allocate(agent_id="agent-digest")
        assert slot.lineage_digest.startswith("sha256:")
