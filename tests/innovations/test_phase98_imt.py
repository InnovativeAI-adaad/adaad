# SPDX-License-Identifier: Apache-2.0
"""T98-IMT-01..30 — Phase 98 INNOV-13 Institutional Memory Transfer acceptance tests.

Invariants under test:
  IMT-0        KnowledgeBundle MUST be signed before transmission
  IMT-VERIFY-0 import_bundle() MUST verify signature before any knowledge state write
  IMT-CHAIN-0  Every import event MUST be recorded in chain-of-custody ledger
  IMT-DETERM-0 Bundle serialization is deterministic (no RNG/datetime/uuid4)
"""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import pytest

from runtime.innovations30.knowledge_transfer import (
    InstitutionalMemoryTransfer,
    KnowledgeBundle,
    TransferVerificationError,
    TransferIntegrityError,
    _compute_hmac,
    _IMT_BUNDLE_VERSION,
    _IMT_SIGN_ALGO,
)

KEY = "test-signing-key-adaad"
ALT_KEY = "wrong-key"

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def imt(tmp_path):
    return InstitutionalMemoryTransfer(
        transfer_log=tmp_path / "transfers.jsonl",
        chain_ledger=tmp_path / "governance_events.jsonl",
    )

@pytest.fixture()
def knowledge():
    return {"weights": {"layer_1": 0.42}, "epochs": 10}

@pytest.fixture()
def unsigned_bundle(knowledge):
    return KnowledgeBundle.create("instance-A", knowledge, epoch_count=5)

@pytest.fixture()
def signed_bundle(unsigned_bundle, imt):
    return imt.sign_bundle(unsigned_bundle, KEY)

# ─────────────────────────────────────────────────────────────────────────────
# IMT-0 — Signing gate (T98-IMT-01..06)
# ─────────────────────────────────────────────────────────────────────────────

def test_imt_01_unsigned_bundle_signature_is_empty(unsigned_bundle):
    """IMT-0: freshly created bundle has empty signature."""
    assert unsigned_bundle.signature == ""


def test_imt_02_sign_bundle_populates_signature(imt, unsigned_bundle):
    """IMT-0: sign_bundle() produces non-empty signature."""
    signed = imt.sign_bundle(unsigned_bundle, KEY)
    assert signed.signature != ""


def test_imt_03_sign_bundle_empty_key_raises(imt, unsigned_bundle):
    """IMT-0: empty signing_key must raise ValueError."""
    with pytest.raises(ValueError, match="IMT-0"):
        imt.sign_bundle(unsigned_bundle, "")


def test_imt_04_import_unsigned_raises_verification_error(imt, unsigned_bundle, tmp_path):
    """IMT-0 / IMT-VERIFY-0: importing unsigned bundle raises TransferVerificationError."""
    with pytest.raises(TransferVerificationError, match="IMT-0"):
        imt.import_bundle(unsigned_bundle, {}, KEY)


def test_imt_05_import_unsigned_records_chain_event(imt, unsigned_bundle, tmp_path):
    """IMT-CHAIN-0: even rejected (unsigned) bundles are recorded in chain ledger."""
    with pytest.raises(TransferVerificationError):
        imt.import_bundle(unsigned_bundle, {}, KEY)
    events = [json.loads(l) for l in imt.chain_ledger.read_text().splitlines()]
    assert events[0]["outcome"] == "REJECTED_UNSIGNED"


def test_imt_06_sign_bundle_returns_new_instance(imt, unsigned_bundle):
    """IMT-0: sign_bundle returns a new object, does not mutate the input."""
    signed = imt.sign_bundle(unsigned_bundle, KEY)
    assert unsigned_bundle.signature == ""  # original unchanged
    assert signed is not unsigned_bundle


# ─────────────────────────────────────────────────────────────────────────────
# IMT-VERIFY-0 — Signature verification (T98-IMT-07..13)
# ─────────────────────────────────────────────────────────────────────────────

def test_imt_07_verify_signature_correct_key(signed_bundle):
    """IMT-VERIFY-0: correct key verifies True."""
    assert signed_bundle.verify_signature(KEY) is True


def test_imt_08_verify_signature_wrong_key(signed_bundle):
    """IMT-VERIFY-0: wrong key verifies False."""
    assert signed_bundle.verify_signature(ALT_KEY) is False


def test_imt_09_verify_signature_empty_returns_false(unsigned_bundle):
    """IMT-VERIFY-0: empty signature always returns False."""
    assert unsigned_bundle.verify_signature(KEY) is False


def test_imt_10_import_wrong_key_raises(imt, signed_bundle, tmp_path):
    """IMT-VERIFY-0: import with wrong key raises TransferVerificationError."""
    with pytest.raises(TransferVerificationError, match="HMAC"):
        imt.import_bundle(signed_bundle, {}, ALT_KEY)


def test_imt_11_import_wrong_key_records_chain_event(imt, signed_bundle):
    """IMT-CHAIN-0: bad-signature rejection is recorded in chain ledger."""
    with pytest.raises(TransferVerificationError):
        imt.import_bundle(signed_bundle, {}, ALT_KEY)
    events = [json.loads(l) for l in imt.chain_ledger.read_text().splitlines()]
    assert events[0]["outcome"] == "REJECTED_BAD_SIGNATURE"


def test_imt_12_import_tampered_bundle_raises(imt, signed_bundle):
    """IMT-VERIFY-0: tampered bundle_hash causes signature mismatch."""
    tampered = KnowledgeBundle(
        source_instance_id=signed_bundle.source_instance_id,
        bundle_version=signed_bundle.bundle_version,
        epoch_count=signed_bundle.epoch_count,
        knowledge_snapshot=signed_bundle.knowledge_snapshot,
        bundle_hash="sha256:aaaa" + "0" * 60,  # forged hash
        signature=signed_bundle.signature,
    )
    with pytest.raises(TransferVerificationError):
        imt.import_bundle(tampered, {}, KEY)


def test_imt_13_import_success_with_valid_signature(imt, signed_bundle, tmp_path):
    """IMT-VERIFY-0: valid signed bundle imports successfully."""
    result = imt.import_bundle(signed_bundle, {}, KEY, human_0_authorized=True)
    assert result.success is True
    assert result.signature_verified is True


# ─────────────────────────────────────────────────────────────────────────────
# IMT-CHAIN-0 — Chain-of-custody ledger (T98-IMT-14..20)
# ─────────────────────────────────────────────────────────────────────────────

def test_imt_14_successful_import_records_chain_event(imt, signed_bundle):
    """IMT-CHAIN-0: successful import appends IMPORTED_OK event."""
    imt.import_bundle(signed_bundle, {}, KEY, human_0_authorized=True)
    events = [json.loads(l) for l in imt.chain_ledger.read_text().splitlines()]
    assert events[-1]["outcome"] == "IMPORTED_OK"


def test_imt_15_chain_event_contains_invariant_list(imt, signed_bundle):
    """IMT-CHAIN-0: event records all four invariant codes."""
    imt.import_bundle(signed_bundle, {}, KEY)
    events = [json.loads(l) for l in imt.chain_ledger.read_text().splitlines()]
    inv = events[-1]["invariants"]
    assert "IMT-0" in inv and "IMT-VERIFY-0" in inv
    assert "IMT-CHAIN-0" in inv and "IMT-DETERM-0" in inv


def test_imt_16_chain_event_records_bundle_hash(imt, signed_bundle):
    """IMT-CHAIN-0: bundle_hash present in chain event for forensic replay."""
    imt.import_bundle(signed_bundle, {}, KEY)
    events = [json.loads(l) for l in imt.chain_ledger.read_text().splitlines()]
    assert events[-1]["bundle_hash"] == signed_bundle.bundle_hash


def test_imt_17_chain_event_records_sign_algo(imt, signed_bundle):
    """IMT-CHAIN-0: sign_algo label recorded."""
    imt.import_bundle(signed_bundle, {}, KEY)
    events = [json.loads(l) for l in imt.chain_ledger.read_text().splitlines()]
    assert events[-1]["sign_algo"] == _IMT_SIGN_ALGO


def test_imt_18_chain_event_records_human_0_flag(imt, signed_bundle):
    """IMT-CHAIN-0: human_0_authorized field present."""
    imt.import_bundle(signed_bundle, {}, KEY, human_0_authorized=True)
    events = [json.loads(l) for l in imt.chain_ledger.read_text().splitlines()]
    assert events[-1]["human_0_authorized"] is True


def test_imt_19_chain_event_uses_path_open(imt, signed_bundle):
    """IMT-CHAIN-0: _record_chain_event uses Path.open — not builtins.open."""
    with patch("runtime.innovations30.knowledge_transfer.Path.open",
               mock_open()) as mocked:
        try:
            imt.import_bundle(signed_bundle, {}, KEY)
        except Exception:
            pass
        mocked.assert_called()


def test_imt_20_multiple_events_append_not_overwrite(imt, signed_bundle):
    """IMT-CHAIN-0: multiple imports append; ledger is not overwritten."""
    imt.import_bundle(signed_bundle, {}, KEY)
    imt.import_bundle(signed_bundle, {}, KEY)
    events = [json.loads(l) for l in imt.chain_ledger.read_text().splitlines()]
    assert len(events) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# IMT-DETERM-0 — Determinism (T98-IMT-21..27)
# ─────────────────────────────────────────────────────────────────────────────

def test_imt_21_same_knowledge_same_bundle_hash(knowledge):
    """IMT-DETERM-0: identical knowledge snapshot produces identical bundle_hash."""
    b1 = KnowledgeBundle.create("inst-A", knowledge, 10)
    b2 = KnowledgeBundle.create("inst-A", knowledge, 10)
    assert b1.bundle_hash == b2.bundle_hash


def test_imt_22_different_knowledge_different_hash(knowledge):
    """IMT-DETERM-0: mutated knowledge produces different bundle_hash."""
    b1 = KnowledgeBundle.create("inst-A", knowledge, 10)
    mutated = dict(knowledge, extra="data")
    b2 = KnowledgeBundle.create("inst-A", mutated, 10)
    assert b1.bundle_hash != b2.bundle_hash


def test_imt_23_same_key_same_signature(imt, knowledge):
    """IMT-DETERM-0: identical bundle + key -> identical signature."""
    b = KnowledgeBundle.create("inst-A", knowledge, 10)
    s1 = imt.sign_bundle(b, KEY)
    s2 = imt.sign_bundle(b, KEY)
    assert s1.signature == s2.signature


def test_imt_24_to_bytes_is_deterministic(signed_bundle):
    """IMT-DETERM-0: to_bytes() produces identical bytes on repeated calls."""
    assert signed_bundle.to_bytes() == signed_bundle.to_bytes()


def test_imt_25_from_bytes_roundtrip(signed_bundle):
    """IMT-DETERM-0: from_bytes(to_bytes()) round-trips losslessly."""
    restored = KnowledgeBundle.from_bytes(signed_bundle.to_bytes())
    assert restored.bundle_hash == signed_bundle.bundle_hash
    assert restored.signature == signed_bundle.signature
    assert restored.knowledge_snapshot == signed_bundle.knowledge_snapshot


def test_imt_26_bundle_hash_prefix_is_sha256(unsigned_bundle):
    """IMT-DETERM-0: bundle_hash always begins with 'sha256:'."""
    assert unsigned_bundle.bundle_hash.startswith("sha256:")


def test_imt_27_verify_integrity_tampered_snapshot(signed_bundle):
    """IMT-DETERM-0: tampered snapshot fails verify_integrity."""
    tampered = KnowledgeBundle(
        source_instance_id=signed_bundle.source_instance_id,
        bundle_version=signed_bundle.bundle_version,
        epoch_count=signed_bundle.epoch_count,
        knowledge_snapshot={"injected": "evil"},
        bundle_hash=signed_bundle.bundle_hash,  # hash unchanged — mismatch
        signature=signed_bundle.signature,
    )
    assert tampered.verify_integrity() is False


# ─────────────────────────────────────────────────────────────────────────────
# Integration and edge cases (T98-IMT-28..30)
# ─────────────────────────────────────────────────────────────────────────────

def test_imt_28_export_and_import_roundtrip(imt, tmp_path):
    """Integration: export → sign → import writes knowledge to target paths."""
    src = tmp_path / "source" / "weights.json"
    src.parent.mkdir()
    src.write_text(json.dumps({"layer_1": 0.9}))

    bundle = imt.export_bundle("inst-X", {"weights": src}, epoch_count=7)
    signed = imt.sign_bundle(bundle, KEY)

    target = tmp_path / "target" / "weights.json"
    result = imt.import_bundle(signed, {"weights": target}, KEY, human_0_authorized=True)

    assert result.success is True
    assert result.imported_items == 1
    assert target.exists()
    data = json.loads(target.read_text())
    assert data == {"layer_1": 0.9}


def test_imt_29_export_missing_source_skipped(imt, tmp_path):
    """IMT-DETERM-0: missing source paths are silently skipped; bundle still valid."""
    bundle = imt.export_bundle("inst-Y", {"missing": tmp_path / "nope.json"}, epoch_count=1)
    assert bundle.knowledge_snapshot == {}
    assert bundle.verify_integrity() is True


def test_imt_30_integrity_check_before_import_guard(imt, signed_bundle):
    """IMT-DETERM-0 / IMT-VERIFY-0: integrity failure raises TransferIntegrityError."""
    # Forge a bundle that passes sig check but fails integrity
    bad_hash = "sha256:" + "f" * 64
    import hmac as _hmac, hashlib as _hashlib
    forged_sig = _hmac.new(KEY.encode(), bad_hash.encode(), _hashlib.sha256).hexdigest()
    tampered = KnowledgeBundle(
        source_instance_id=signed_bundle.source_instance_id,
        bundle_version=signed_bundle.bundle_version,
        epoch_count=signed_bundle.epoch_count,
        knowledge_snapshot={"injected": "data"},
        bundle_hash=bad_hash,
        signature=forged_sig,
    )
    with pytest.raises(TransferIntegrityError, match="IMT-DETERM-0"):
        imt.import_bundle(tampered, {}, KEY)
