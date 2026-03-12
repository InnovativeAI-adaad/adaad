# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from security import challenge_store
import pytest


pytestmark = pytest.mark.governance_gate

def _mark_nonce_worker(path: str, nonce: str) -> None:
    challenge_store.mark_nonce(nonce, ttl_seconds=3600, path=path)


def _put_challenge_worker(path: str, challenge_id: str, payload: str) -> None:
    challenge_store.put_challenge(challenge_id, payload, ttl_seconds=3600, path=path)


def test_mark_nonce_concurrent_process_writes_preserve_all_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "nonce_store.json"
    worker_count = 24
    ctx = multiprocessing.get_context("spawn")
    procs = [ctx.Process(target=_mark_nonce_worker, args=(str(db_path), f"nonce-{i:03d}")) for i in range(worker_count)]

    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=20)
        assert proc.exitcode == 0

    data = json.loads(db_path.read_text(encoding="utf-8"))
    assert len(data.get("nonces", {})) == worker_count


def test_put_challenge_concurrent_thread_writes_preserve_all_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "challenge_store.json"
    worker_count = 32

    def _worker(index: int) -> None:
        challenge_store.put_challenge(f"challenge-{index:03d}", f"payload-{index:03d}", ttl_seconds=3600, path=str(db_path))

    with ThreadPoolExecutor(max_workers=8) as pool:
        for i in range(worker_count):
            pool.submit(_worker, i)

    data = json.loads(db_path.read_text(encoding="utf-8"))
    challenges = data.get("challenges", {})
    assert len(challenges) == worker_count
    assert all(challenges[f"challenge-{i:03d}"]["challenge"] == f"payload-{i:03d}" for i in range(worker_count))
