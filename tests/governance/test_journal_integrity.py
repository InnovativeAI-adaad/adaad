# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.governance_gate

from security.ledger import journal


def _temp_paths(tmp_path: Path, name: str = "cryovant_journal") -> journal.JournalPaths:
    base_path = tmp_path / name
    return journal.JournalPaths(
        journal_path=base_path.with_suffix(".jsonl"),
        genesis_path=base_path.with_name(f"{base_path.name}.genesis.jsonl"),
        tail_state_path=base_path.with_name(f"{base_path.name}.tail.json"),
        lock_path=base_path.with_name(f"{base_path.name}.lock"),
    )


def test_verify_journal_integrity_valid_chain(tmp_path: Path) -> None:
    paths = _temp_paths(tmp_path)
    journal.append_tx("test", {"i": 1}, tx_id="TX-1", journal_paths=paths)
    journal.append_tx("test", {"i": 2}, tx_id="TX-2", journal_paths=paths)
    journal.verify_journal_integrity(journal_paths=paths)


def test_verify_journal_integrity_detects_tamper(tmp_path: Path) -> None:
    paths = _temp_paths(tmp_path)
    journal.append_tx("test", {"i": 1}, tx_id="TX-1", journal_paths=paths)
    entry = json.loads(paths.journal_path.read_text(encoding="utf-8").splitlines()[0])
    entry["payload"]["i"] = 999
    paths.journal_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(journal.JournalIntegrityError, match="journal_hash_mismatch"):
        journal.verify_journal_integrity(journal_paths=paths)


def test_verify_journal_integrity_detects_malformed_json(tmp_path: Path) -> None:
    paths = _temp_paths(tmp_path)
    paths.journal_path.write_text('{"tx":"oops"\n', encoding="utf-8")
    with pytest.raises(journal.JournalIntegrityError, match="journal_invalid_json"):
        journal.verify_journal_integrity(journal_paths=paths)


def test_append_tx_blocked_after_corruption(tmp_path: Path) -> None:
    paths = _temp_paths(tmp_path)
    journal.append_tx("test", {"i": 1}, tx_id="TX-1", journal_paths=paths)
    entry = json.loads(paths.journal_path.read_text(encoding="utf-8").splitlines()[0])
    entry["prev_hash"] = "f" * 64
    paths.journal_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(journal.JournalIntegrityError, match="journal_prev_hash_mismatch"):
        journal.append_tx("test", {"i": 2}, tx_id="TX-2", journal_paths=paths)


def test_corrupted_temp_journal_cache_does_not_poison_other_journal(tmp_path: Path) -> None:
    journal._VERIFIED_TAIL_CACHE.clear()
    alpha = _temp_paths(tmp_path / "alpha")
    beta = _temp_paths(tmp_path / "beta")

    journal.append_tx("test", {"i": 1}, tx_id="TX-A1", journal_paths=alpha)
    beta_first = journal.append_tx("test", {"i": 1}, tx_id="TX-B1", journal_paths=beta)

    tampered = json.loads(alpha.journal_path.read_text(encoding="utf-8").splitlines()[0])
    tampered["prev_hash"] = "f" * 64
    alpha.journal_path.write_text(json.dumps(tampered, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(journal.JournalIntegrityError, match="journal_prev_hash_mismatch"):
        journal.verify_journal_integrity(journal_paths=alpha)

    beta_second = journal.append_tx("test", {"i": 2}, tx_id="TX-B2", journal_paths=beta)
    assert beta_second["prev_hash"] == beta_first["hash"]
    assert journal._VERIFIED_TAIL_CACHE[str(beta.journal_path.resolve())][0] == beta_second["hash"]
