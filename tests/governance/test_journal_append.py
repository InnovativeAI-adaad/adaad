# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.governance_gate

import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from security.ledger import journal


def _temp_paths(tmp_path: Path, name: str = "cryovant_journal") -> journal.JournalPaths:
    base_path = tmp_path / name
    return journal.JournalPaths(
        journal_path=base_path.with_suffix(".jsonl"),
        genesis_path=base_path.with_name(f"{base_path.name}.genesis.jsonl"),
        tail_state_path=base_path.with_name(f"{base_path.name}.tail.json"),
        lock_path=base_path.with_name(f"{base_path.name}.lock"),
    )


def test_journal_hash_chaining(tmp_path: Path) -> None:
    paths = _temp_paths(tmp_path)
    first = journal.append_tx("test", {"i": 1}, tx_id="TX-1", journal_paths=paths)
    second = journal.append_tx("test", {"i": 2}, tx_id="TX-2", journal_paths=paths)
    assert second["prev_hash"] == first["hash"]


def test_concurrent_thread_appends_preserve_chain(tmp_path: Path) -> None:
    paths = _temp_paths(tmp_path)
    workers = 8
    per_worker = 25

    def _append(worker_id: int, index: int) -> None:
        tx_id = f"T-{worker_id}-{index}"
        journal.append_tx(
            "thread",
            {"worker": worker_id, "index": index},
            tx_id=tx_id,
            journal_paths=paths,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for worker_id in range(workers):
            for index in range(per_worker):
                pool.submit(_append, worker_id, index)

    journal.verify_journal_integrity(journal_paths=paths)
    lines = [line for line in paths.journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == workers * per_worker


def _process_append(paths: tuple[str, str, str, str], tx_id: str) -> None:
    journal.append_tx(
        "process",
        {"tx": tx_id},
        tx_id=tx_id,
        journal_paths=journal.JournalPaths(
            journal_path=Path(paths[0]),
            genesis_path=Path(paths[1]),
            tail_state_path=Path(paths[2]),
            lock_path=Path(paths[3]),
        ),
    )


def test_concurrent_process_appends_preserve_chain(tmp_path: Path) -> None:
    paths = _temp_paths(tmp_path)
    tx_count = 24
    process_paths = (
        str(paths.journal_path),
        str(paths.genesis_path),
        str(paths.tail_state_path),
        str(paths.lock_path),
    )
    args = [(process_paths, f"P-{index}") for index in range(tx_count)]

    with multiprocessing.get_context("spawn").Pool(processes=6) as pool:
        pool.starmap(_process_append, args)

    journal.verify_journal_integrity(journal_paths=paths)
    entries = [json.loads(line) for line in paths.journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(entries) == tx_count
    assert len({entry["tx"] for entry in entries}) == tx_count


def test_append_rejects_unknown_event_type(tmp_path: Path) -> None:
    paths = _temp_paths(tmp_path)
    try:
        journal.append_tx("unknown_type", {"agm_step": "step_1"}, tx_id="TX-BAD", journal_paths=paths)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "event_type_not_allowed:unknown_type:agm_step_01"

    assert not paths.journal_path.exists() or paths.journal_path.read_text(encoding="utf-8").strip() == ""


def test_temp_journals_do_not_share_tail_state_lock_or_cache(tmp_path: Path) -> None:
    journal._VERIFIED_TAIL_CACHE.clear()
    alpha = _temp_paths(tmp_path / "alpha")
    beta = _temp_paths(tmp_path / "beta")

    alpha_first = journal.append_tx("test", {"i": 1}, tx_id="TX-A1", journal_paths=alpha)
    beta_first = journal.append_tx("test", {"i": 1}, tx_id="TX-B1", journal_paths=beta)
    alpha_second = journal.append_tx("test", {"i": 2}, tx_id="TX-A2", journal_paths=alpha)

    assert alpha.tail_state_path != beta.tail_state_path
    assert alpha.lock_path != beta.lock_path
    assert alpha.tail_state_path.exists()
    assert beta.tail_state_path.exists()
    assert alpha.lock_path.exists()
    assert beta.lock_path.exists()
    assert json.loads(alpha.tail_state_path.read_text(encoding="utf-8"))["last_hash"] == alpha_second["hash"]
    assert json.loads(beta.tail_state_path.read_text(encoding="utf-8"))["last_hash"] == beta_first["hash"]

    alpha_key = str(alpha.journal_path.resolve())
    beta_key = str(beta.journal_path.resolve())
    assert set(journal._VERIFIED_TAIL_CACHE) >= {alpha_key, beta_key}
    assert journal._VERIFIED_TAIL_CACHE[alpha_key][0] == alpha_second["hash"]
    assert journal._VERIFIED_TAIL_CACHE[beta_key][0] == beta_first["hash"]
    assert beta_first["prev_hash"] == "0" * 64
    assert alpha_first["prev_hash"] == "0" * 64
