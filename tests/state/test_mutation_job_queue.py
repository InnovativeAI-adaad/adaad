# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.state.mutation_job_queue import MutationJobQueueStore
from runtime.state.mutation_job_transitions import MutationJobTransitionStore


@pytest.mark.parametrize("backend", ["json", "sqlite"])
def test_enqueue_is_deterministic_and_idempotent(tmp_path: Path, backend: str) -> None:
    store = MutationJobQueueStore(tmp_path / "jobs.json", backend=backend)
    payload = {"mutation": "m-1", "epoch": "e-1"}

    first = store.enqueue(payload, dedupe_key="phase6", now_ts=100.0)
    second = store.enqueue(payload, dedupe_key="phase6", now_ts=101.0)

    assert first["job_id"] == second["job_id"]
    assert len(store.list_jobs()) == 1
    assert store.list_jobs()[0]["state"] == "queued"


@pytest.mark.parametrize("backend", ["json", "sqlite"])
def test_duplicate_dispatch_only_leases_once(tmp_path: Path, backend: str) -> None:
    store = MutationJobQueueStore(tmp_path / "jobs.json", backend=backend, lease_timeout_s=20)
    store.enqueue({"mutation": "m-1"}, now_ts=100.0)

    leased = store.lease_next(worker_id="worker-a", now_ts=101.0)
    duplicate = store.lease_next(worker_id="worker-b", now_ts=102.0)

    assert leased is not None
    assert duplicate is None
    assert store.get(leased["job_id"])["state"] == "leased"


@pytest.mark.parametrize("backend", ["json", "sqlite"])
def test_worker_crash_recovery_reclaims_stale_lease(tmp_path: Path, backend: str) -> None:
    store = MutationJobQueueStore(tmp_path / "jobs.json", backend=backend, lease_timeout_s=10)
    job = store.enqueue({"mutation": "m-2"}, now_ts=100.0)

    leased = store.lease_next(worker_id="worker-a", now_ts=100.0)
    assert leased is not None
    assert store.mark_running(job_id=job["job_id"], worker_id="worker-a", now_ts=101.0)

    recovered = store.recover_orphans(now_ts=120.0)
    assert job["job_id"] in recovered
    row = store.get(job["job_id"])
    assert row is not None
    assert row["state"] == "queued"
    assert row["error"] == "stale_lease_reclaimed"


@pytest.mark.parametrize("backend", ["json", "sqlite"])
def test_heartbeat_extends_lease(tmp_path: Path, backend: str) -> None:
    store = MutationJobQueueStore(tmp_path / "jobs.json", backend=backend, lease_timeout_s=5)
    job = store.enqueue({"mutation": "m-3"}, now_ts=200.0)
    store.lease_next(worker_id="worker-a", now_ts=200.0)

    assert store.heartbeat(job_id=job["job_id"], worker_id="worker-a", now_ts=202.0)
    row = store.get(job["job_id"])
    assert row is not None
    assert row["lease_expires_at"] == 207.0


@pytest.mark.parametrize("backend", ["json", "sqlite"])
def test_exactly_once_completion_rejects_non_owner_duplicate(tmp_path: Path, backend: str) -> None:
    store = MutationJobQueueStore(tmp_path / "jobs.json", backend=backend, lease_timeout_s=10)
    job = store.enqueue({"mutation": "m-once"}, now_ts=1.0)
    store.lease_next(worker_id="worker-a", now_ts=2.0)
    assert store.mark_running(job_id=job["job_id"], worker_id="worker-a", now_ts=2.1)

    assert store.complete(job_id=job["job_id"], state="succeeded", worker_id="worker-a", now_ts=3.0)
    assert not store.complete(job_id=job["job_id"], state="failed", worker_id="worker-b", now_ts=3.1)
    assert store.get(job["job_id"])["state"] == "succeeded"


@pytest.mark.parametrize("backend", ["json", "sqlite"])
def test_transitions_persist_state_history(tmp_path: Path, backend: str) -> None:
    transition_store = MutationJobTransitionStore(tmp_path / "job_transitions.json", backend=backend)
    store = MutationJobQueueStore(
        tmp_path / "jobs.json",
        backend=backend,
        lease_timeout_s=5,
        transition_store=transition_store,
    )
    job = store.enqueue({"mutation": "m-history"}, now_ts=1.0)
    store.lease_next(worker_id="worker-a", now_ts=2.0)
    store.mark_running(job_id=job["job_id"], worker_id="worker-a", now_ts=3.0)
    store.complete(job_id=job["job_id"], state="succeeded", worker_id="worker-a", now_ts=4.0)

    transitions = transition_store.list_transitions(job_id=job["job_id"])
    assert [row["to_state"] for row in transitions] == ["queued", "leased", "running", "succeeded"]
