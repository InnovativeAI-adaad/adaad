# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.agm_event import AGMEventEnvelope
from runtime.evolution.event_signing import DeterministicMockSigner
from runtime.state.ledger_store import ScoringLedgerStore


def _event(*, event_id: str, signature: str | None = None) -> AGMEventEnvelope:
    signer = DeterministicMockSigner()
    envelope = AGMEventEnvelope(
        schema_version="1.0",
        event_id=event_id,
        event_type="scoring_event",
        emitted_at="2026-01-01T00:00:00Z",
        payload={"mutation_id": event_id, "score": 0.9},
        signature="",
        signing_key_id="",
        signature_algorithm="",
    )
    message = ScoringLedgerStore.canonical_event_content(envelope)
    signed = signer.sign(message)
    return AGMEventEnvelope(
        schema_version=envelope.schema_version,
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        emitted_at=envelope.emitted_at,
        payload=envelope.payload,
        signature=signature if signature is not None else signed.signature,
        signing_key_id=signed.signing_key_id,
        signature_algorithm=signed.algorithm,
    )


def test_ledger_store_append_and_verify_json(tmp_path) -> None:
    ledger = ScoringLedgerStore(path=tmp_path / "scoring.jsonl", backend="json")
    signer = DeterministicMockSigner()
    ledger.append_event(_event(event_id="evt-1"), verifier=signer)
    ledger.append_event(_event(event_id="evt-2"), verifier=signer)

    report = ledger.verify_chain(verifier=signer)

    assert report["ok"] is True
    assert report["count"] == 2


def test_ledger_store_detects_hash_chain_tamper(tmp_path) -> None:
    ledger_path = tmp_path / "scoring.jsonl"
    ledger = ScoringLedgerStore(path=ledger_path, backend="json")
    signer = DeterministicMockSigner()
    ledger.append_event(_event(event_id="evt-1"), verifier=signer)
    ledger.append_event(_event(event_id="evt-2"), verifier=signer)

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace('"prev_hash": "', '"prev_hash": "sha256:deadbeef')
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = ledger.verify_chain(verifier=signer)

    assert report["ok"] is False
    assert report["error"] == "prev_hash_mismatch"


def test_ledger_store_json_sqlite_parity(tmp_path) -> None:
    json_path = tmp_path / "scoring.jsonl"
    sqlite_path = tmp_path / "scoring.sqlite"
    json_ledger = ScoringLedgerStore(path=json_path, backend="json")
    sqlite_ledger = ScoringLedgerStore(path=json_path, sqlite_path=sqlite_path, backend="sqlite")
    signer = DeterministicMockSigner()

    for event_id in ["evt-a", "evt-b", "evt-c"]:
        envelope = _event(event_id=event_id)
        json_ledger.append_event(envelope, verifier=signer)
        sqlite_ledger.append_event(envelope, verifier=signer)

    assert json_ledger.iter_records() == sqlite_ledger.iter_records()
    assert sqlite_ledger.verify_chain(verifier=signer)["ok"] is True


def test_ledger_store_rejects_invalid_signature(tmp_path) -> None:
    ledger = ScoringLedgerStore(path=tmp_path / "scoring.jsonl", backend="json")
    signer = DeterministicMockSigner()
    invalid = _event(event_id="evt-bad", signature="sig:deadbeef")

    try:
        ledger.append_event(invalid, verifier=signer)
        assert False, "append should fail for invalid signature"
    except ValueError as exc:
        assert str(exc) == "invalid_event_signature"
