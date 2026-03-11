# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest

from security.ledger.append import append_entry

pytestmark = pytest.mark.governance_gate


def _read_entries(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_append_entry_chain_continuity(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"

    first = append_entry({"event_type": "alpha"}, path=str(ledger_path))
    second = append_entry({"event_type": "beta"}, path=str(ledger_path))

    assert first["prev_entry_hash"] == "0" * 64
    assert second["prev_entry_hash"] == first["entry_hash"]

    entries = _read_entries(ledger_path)
    assert entries[1]["prev_entry_hash"] == entries[0]["entry_hash"]


def test_append_entry_rejects_malformed_tail(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text('{"event_type":"ok","entry_hash":"' + ("a" * 64) + '"}\nnot-json\n', encoding="utf-8")

    with pytest.raises(ValueError, match="^ledger_tail_invalid$"):
        append_entry({"event_type": "gamma"}, path=str(ledger_path))

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert lines[-1] == "not-json"


def test_append_entry_preserves_genesis_for_empty_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "new-ledger.jsonl"
    created = append_entry({"event_type": "genesis"}, path=str(missing_path))
    assert created["prev_entry_hash"] == "0" * 64

    empty_path = tmp_path / "empty-ledger.jsonl"
    empty_path.write_text("\n", encoding="utf-8")
    appended = append_entry({"event_type": "genesis-2"}, path=str(empty_path))
    assert appended["prev_entry_hash"] == "0" * 64
