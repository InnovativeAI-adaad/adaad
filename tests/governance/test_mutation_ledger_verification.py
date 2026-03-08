# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.governance.mutation_ledger import LedgerEntry, MutationLedger
from scripts.verify_mutation_ledger import verify_mutation_ledger


def test_verify_mutation_ledger_accepts_valid_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_path = tmp_path / "mutation_ledger.jsonl"
    monkeypatch.setenv("ADAAD_ENV", "test")
    monkeypatch.setenv("ADAAD_LEDGER_SIGNING_KEYS", json.dumps({"mock-kms-key": "mock-ledger-secret"}))
    ledger = MutationLedger(ledger_path, test_mode=True)
    ledger.append(LedgerEntry(variant_id="v1", seed=1, metrics={"fitness": 0.7}, promoted=False))
    ledger.append(LedgerEntry(variant_id="v2", seed=2, metrics={"fitness": 0.9}, promoted=True))

    verify_mutation_ledger(ledger_path)


def test_verify_mutation_ledger_rejects_tampered_prev_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_path = tmp_path / "mutation_ledger.jsonl"
    monkeypatch.setenv("ADAAD_ENV", "test")
    monkeypatch.setenv("ADAAD_LEDGER_SIGNING_KEYS", json.dumps({"mock-kms-key": "mock-ledger-secret"}))
    ledger = MutationLedger(ledger_path, test_mode=True)
    ledger.append(LedgerEntry(variant_id="v1", seed=1, metrics={"fitness": 0.7}, promoted=False))
    ledger.append(LedgerEntry(variant_id="v2", seed=2, metrics={"fitness": 0.9}, promoted=True))

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[1]["prev_hash"] = "sha256:" + ("f" * 64)
    ledger_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="prev_hash mismatch"):
        verify_mutation_ledger(ledger_path)
