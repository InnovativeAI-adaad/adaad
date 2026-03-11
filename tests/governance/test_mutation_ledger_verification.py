# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.evolution.event_signing import EventSigner, HMACKeyringVerifier, SignatureBundle
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


def test_verify_mutation_ledger_rejects_line_edit_payload_tamper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_path = tmp_path / "mutation_ledger.jsonl"
    monkeypatch.setenv("ADAAD_ENV", "test")
    monkeypatch.setenv("ADAAD_LEDGER_SIGNING_KEYS", json.dumps({"mock-kms-key": "mock-ledger-secret"}))
    ledger = MutationLedger(ledger_path, test_mode=True)
    ledger.append(LedgerEntry(variant_id="v1", seed=1, metrics={"fitness": 0.7}, promoted=False))
    ledger.append(LedgerEntry(variant_id="v2", seed=2, metrics={"fitness": 0.9}, promoted=True))

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[1]["entry"]["metrics"]["fitness"] = 0.5
    ledger_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="canonical_payload_hash mismatch"):
        verify_mutation_ledger(ledger_path)


def test_verify_mutation_ledger_rejects_truncation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_path = tmp_path / "mutation_ledger.jsonl"
    monkeypatch.setenv("ADAAD_ENV", "test")
    monkeypatch.setenv("ADAAD_LEDGER_SIGNING_KEYS", json.dumps({"mock-kms-key": "mock-ledger-secret"}))
    ledger = MutationLedger(ledger_path, test_mode=True)
    ledger.append(LedgerEntry(variant_id="v1", seed=1, metrics={"fitness": 0.7}, promoted=False))
    ledger.append(LedgerEntry(variant_id="v2", seed=2, metrics={"fitness": 0.9}, promoted=True))

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[1].pop("signature_bundle")
    ledger_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="signature_bundle must be an object"):
        verify_mutation_ledger(ledger_path)


def test_verify_mutation_ledger_rejects_reordered_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_path = tmp_path / "mutation_ledger.jsonl"
    monkeypatch.setenv("ADAAD_ENV", "test")
    monkeypatch.setenv("ADAAD_LEDGER_SIGNING_KEYS", json.dumps({"mock-kms-key": "mock-ledger-secret"}))
    ledger = MutationLedger(ledger_path, test_mode=True)
    ledger.append(LedgerEntry(variant_id="v1", seed=1, metrics={"fitness": 0.7}, promoted=False))
    ledger.append(LedgerEntry(variant_id="v2", seed=2, metrics={"fitness": 0.9}, promoted=True))
    ledger.append(LedgerEntry(variant_id="v3", seed=3, metrics={"fitness": 1.1}, promoted=True))

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[1], rows[2] = rows[2], rows[1]
    ledger_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="prev_hash mismatch"):
        verify_mutation_ledger(ledger_path)


class _HMACTestSigner(EventSigner):
    def __init__(self, key_id: str, secret: str) -> None:
        self._key_id = key_id
        self._secret = secret

    def sign(self, message: str) -> SignatureBundle:
        import hashlib
        import hmac

        digest = hmac.new(self._secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        return SignatureBundle(signature=f"sig:{digest}", signing_key_id=self._key_id, algorithm="hmac-sha256")


def test_mutation_ledger_strict_non_test_mode_rejects_tampered_existing_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_path = tmp_path / "mutation_ledger.jsonl"
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("ADAAD_LEDGER_SIGNING_KEYS", json.dumps({"prod-key": "prod-secret"}))
    signer = _HMACTestSigner("prod-key", "prod-secret")
    verifier = HMACKeyringVerifier({"prod-key": "prod-secret"})

    ledger = MutationLedger(ledger_path, signer=signer, verifier=verifier, test_mode=False)
    ledger.append(LedgerEntry(variant_id="v1", seed=1, metrics={"fitness": 0.7}, promoted=False))

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["canonical_payload_hash"] = "sha256:" + ("f" * 64)
    ledger_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="canonical_payload_hash mismatch"):
        ledger.append(LedgerEntry(variant_id="v2", seed=2, metrics={"fitness": 0.9}, promoted=True))
