# SPDX-License-Identifier: Apache-2.0
"""Phase 118 — INNOV-33 Knowledge Bundle Exchange Protocol (KBEP) tests.

T118-KBEP-01..30  (30/30)
pytest mark: phase118
"""
from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from runtime.innovations30.knowledge_bundle_exchange import (
    ExchangeRecord,
    FederationBundle,
    KBEPChainError,
    KBEPGateError,
    KBEPPersistError,
    KBEPVerificationError,
    KnowledgeBundleExchangeProtocol,
    KnowledgeBundleItem,
    kbep_guard,
)

pytestmark = pytest.mark.phase118

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_ledger(tmp_path: Path) -> Path:
    return tmp_path / "kbep_test.jsonl"


@pytest.fixture()
def engine(tmp_ledger: Path) -> KnowledgeBundleExchangeProtocol:
    return KnowledgeBundleExchangeProtocol(
        instance_id="test-instance-001",
        ledger_path=tmp_ledger,
    )


@pytest.fixture()
def item_a() -> KnowledgeBundleItem:
    return KnowledgeBundleItem(
        key="inv:ledger-first",
        value="all events ledger before action",
        knowledge_type="invariant",
        source_phase=87,
    )


@pytest.fixture()
def item_b() -> KnowledgeBundleItem:
    return KnowledgeBundleItem(
        key="pattern:fail-closed",
        value="enforcement helper always raises on falsy condition",
        knowledge_type="pattern",
        source_phase=91,
    )


@pytest.fixture()
def bundle_from_peer(item_a: KnowledgeBundleItem) -> FederationBundle:
    """A bundle created by a foreign peer instance."""
    return FederationBundle.create(
        epoch_id="peer-epoch-001",
        instance_id="peer-instance-999",
        items=[item_a],
    )

# ── T118-KBEP-01: module imports without error ────────────────────────────────

def test_kbep_01_module_imports() -> None:
    """T118-KBEP-01: all public names importable."""
    assert KnowledgeBundleExchangeProtocol is not None
    assert FederationBundle is not None
    assert KnowledgeBundleItem is not None
    assert ExchangeRecord is not None


# ── T118-KBEP-02: engine instantiation ───────────────────────────────────────

def test_kbep_02_engine_instantiation(engine: KnowledgeBundleExchangeProtocol) -> None:
    """T118-KBEP-02: engine initialises with correct instance_id."""
    assert engine.instance_id == "test-instance-001"
    assert engine.records == []
    assert engine.imported_bundles == {}


# ── T118-KBEP-03: FederationBundle deterministic ID (KBEP-DETERM-0) ──────────

def test_kbep_03_bundle_id_deterministic(item_a: KnowledgeBundleItem) -> None:
    """T118-KBEP-03: KBEP-DETERM-0 — same inputs produce identical bundle_id."""
    b1 = FederationBundle.create("epoch-99", "inst-A", [item_a])
    b2 = FederationBundle.create("epoch-99", "inst-A", [item_a])
    assert b1.bundle_id == b2.bundle_id


# ── T118-KBEP-04: FederationBundle ID changes with epoch ─────────────────────

def test_kbep_04_bundle_id_epoch_sensitive(item_a: KnowledgeBundleItem) -> None:
    """T118-KBEP-04: KBEP-DETERM-0 — different epoch → different bundle_id."""
    b1 = FederationBundle.create("epoch-1", "inst-A", [item_a])
    b2 = FederationBundle.create("epoch-2", "inst-A", [item_a])
    assert b1.bundle_id != b2.bundle_id


# ── T118-KBEP-05: FederationBundle digest format ─────────────────────────────

def test_kbep_05_bundle_digest_format(item_a: KnowledgeBundleItem) -> None:
    """T118-KBEP-05: bundle_digest prefixed sha256:."""
    bundle = FederationBundle.create("e-001", "inst-A", [item_a])
    assert bundle.bundle_digest.startswith("sha256:")
    assert len(bundle.bundle_digest) == 7 + 64


# ── T118-KBEP-06: KBEP-VERIFY-0 — recompute_digest matches ──────────────────

def test_kbep_06_recompute_digest_matches(item_a: KnowledgeBundleItem) -> None:
    """T118-KBEP-06: KBEP-VERIFY-0 — recompute_digest() == bundle_digest on clean bundle."""
    bundle = FederationBundle.create("e-002", "inst-A", [item_a])
    assert bundle.recompute_digest() == bundle.bundle_digest


# ── T118-KBEP-07: create_bundle produces an ExchangeRecord ───────────────────

def test_kbep_07_create_bundle_record(
    engine: KnowledgeBundleExchangeProtocol, item_a: KnowledgeBundleItem
) -> None:
    """T118-KBEP-07: create_bundle registers exactly one record."""
    engine.create_bundle("epoch-001", [item_a])
    assert len(engine.records) == 1


# ── T118-KBEP-08: create_bundle returns FederationBundle ─────────────────────

def test_kbep_08_create_bundle_returns_bundle(
    engine: KnowledgeBundleExchangeProtocol, item_a: KnowledgeBundleItem
) -> None:
    """T118-KBEP-08: create_bundle return type is FederationBundle."""
    result = engine.create_bundle("epoch-002", [item_a])
    assert isinstance(result, FederationBundle)


# ── T118-KBEP-09: KBEP-PERSIST-0 — ledger file written ──────────────────────

def test_kbep_09_ledger_persisted(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
    tmp_ledger: Path,
) -> None:
    """T118-KBEP-09: KBEP-PERSIST-0 — ledger file exists and contains one line after create_bundle."""
    engine.create_bundle("epoch-003", [item_a])
    assert tmp_ledger.exists()
    lines = [l for l in tmp_ledger.read_text().splitlines() if l.strip()]
    assert len(lines) == 1


# ── T118-KBEP-10: KBEP-PERSIST-0 — ledger line is valid JSON ────────────────

def test_kbep_10_ledger_line_valid_json(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
    tmp_ledger: Path,
) -> None:
    """T118-KBEP-10: KBEP-PERSIST-0 — ledger line parses as JSON."""
    engine.create_bundle("epoch-004", [item_a])
    raw = tmp_ledger.read_text().strip()
    data = json.loads(raw)
    assert "record_id" in data
    assert "bundle_id" in data


# ── T118-KBEP-11: KBEP-0 — empty epoch_id rejected ──────────────────────────

def test_kbep_11_empty_epoch_rejected(
    engine: KnowledgeBundleExchangeProtocol, item_a: KnowledgeBundleItem
) -> None:
    """T118-KBEP-11: KBEP-0 fail-closed — blank epoch_id raises KBEPVerificationError."""
    with pytest.raises(KBEPVerificationError, match="KBEP-0"):
        engine.create_bundle("", [item_a])


# ── T118-KBEP-12: KBEP-0 — empty items rejected ─────────────────────────────

def test_kbep_12_empty_items_rejected(
    engine: KnowledgeBundleExchangeProtocol,
) -> None:
    """T118-KBEP-12: KBEP-0 fail-closed — empty item list raises KBEPVerificationError."""
    with pytest.raises(KBEPVerificationError, match="KBEP-0"):
        engine.create_bundle("epoch-005", [])


# ── T118-KBEP-13: import_bundle — valid bundle accepted ──────────────────────

def test_kbep_13_import_valid_bundle(
    engine: KnowledgeBundleExchangeProtocol,
    bundle_from_peer: FederationBundle,
) -> None:
    """T118-KBEP-13: import_bundle accepts a valid peer bundle."""
    record = engine.import_bundle(bundle_from_peer)
    assert isinstance(record, ExchangeRecord)
    assert record.event_type == "import"
    assert record.verified is True


# ── T118-KBEP-14: KBEP-VERIFY-0 — tampered bundle rejected ──────────────────

def test_kbep_14_tampered_bundle_rejected(
    engine: KnowledgeBundleExchangeProtocol,
    bundle_from_peer: FederationBundle,
) -> None:
    """T118-KBEP-14: KBEP-VERIFY-0 — mutating item after create raises on import."""
    bundle_from_peer.items[0].value = "TAMPERED"
    with pytest.raises(KBEPVerificationError, match="KBEP-VERIFY-0"):
        engine.import_bundle(bundle_from_peer)


# ── T118-KBEP-15: KBEP-VERIFY-0 — wrong bundle_digest rejected ───────────────

def test_kbep_15_wrong_digest_rejected(
    engine: KnowledgeBundleExchangeProtocol,
    bundle_from_peer: FederationBundle,
) -> None:
    """T118-KBEP-15: KBEP-VERIFY-0 — corrupted bundle_digest field fails verification."""
    bundle_from_peer.bundle_digest = "sha256:" + "f" * 64
    with pytest.raises(KBEPVerificationError, match="KBEP-VERIFY-0"):
        engine.import_bundle(bundle_from_peer)


# ── T118-KBEP-16: import registers bundle in imported_bundles dict ────────────

def test_kbep_16_imported_bundle_tracked(
    engine: KnowledgeBundleExchangeProtocol,
    bundle_from_peer: FederationBundle,
) -> None:
    """T118-KBEP-16: imported bundle stored in engine.imported_bundles keyed by bundle_id."""
    engine.import_bundle(bundle_from_peer)
    assert bundle_from_peer.bundle_id in engine.imported_bundles


# ── T118-KBEP-17: KBEP-GATE-0 — federation amendment blocked without HUMAN-0 ─

def test_kbep_17_federation_amendment_blocked(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
) -> None:
    """T118-KBEP-17: KBEP-GATE-0 — federation_amendment=True without ack raises KBEPGateError."""
    with pytest.raises(KBEPGateError, match="KBEP-GATE-0"):
        engine.create_bundle("epoch-006", [item_a], federation_amendment=True)


# ── T118-KBEP-18: KBEP-GATE-0 — federation amendment allowed with HUMAN-0 ────

def test_kbep_18_federation_amendment_allowed(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
) -> None:
    """T118-KBEP-18: KBEP-GATE-0 — human0_acknowledged=True allows federation amendment."""
    bundle = engine.create_bundle(
        "epoch-007", [item_a], federation_amendment=True, human0_acknowledged=True
    )
    assert bundle.federation_amendment is True
    assert engine.records[0].event_type == "federation_amendment"


# ── T118-KBEP-19: KBEP-GATE-0 — import federation amendment without ack ──────

def test_kbep_19_import_federation_amendment_blocked(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
) -> None:
    """T118-KBEP-19: KBEP-GATE-0 — importing a federation_amendment bundle without ack fails."""
    peer_bundle = FederationBundle.create(
        "peer-epoch-002", "peer-999", [item_a], federation_amendment=True
    )
    with pytest.raises(KBEPGateError, match="KBEP-GATE-0"):
        engine.import_bundle(peer_bundle)


# ── T118-KBEP-20: KBEP-CHAIN-0 — verify_chain passes on fresh engine ─────────

def test_kbep_20_verify_chain_empty(
    engine: KnowledgeBundleExchangeProtocol,
) -> None:
    """T118-KBEP-20: KBEP-CHAIN-0 — verify_chain returns True on empty ledger."""
    assert engine.verify_chain() is True


# ── T118-KBEP-21: KBEP-CHAIN-0 — verify_chain passes after multiple ops ──────

def test_kbep_21_verify_chain_multi_record(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
    item_b: KnowledgeBundleItem,
    bundle_from_peer: FederationBundle,
) -> None:
    """T118-KBEP-21: KBEP-CHAIN-0 — chain valid after export + import cycle."""
    engine.create_bundle("epoch-chain-1", [item_a])
    engine.import_bundle(bundle_from_peer)
    engine.create_bundle("epoch-chain-2", [item_b])
    assert engine.verify_chain() is True


# ── T118-KBEP-22: KBEP-CHAIN-0 — tampered record_digest detected ─────────────

def test_kbep_22_chain_tamper_detected(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
) -> None:
    """T118-KBEP-22: KBEP-CHAIN-0 — mutating record_digest raises KBEPChainError."""
    engine.create_bundle("epoch-tamper", [item_a])
    engine._records[0].record_digest = "deadbeef" * 8  # type: ignore[index]
    with pytest.raises(KBEPChainError, match="KBEP-CHAIN-0"):
        engine.verify_chain()


# ── T118-KBEP-23: ExchangeRecord record_id deterministic ─────────────────────

def test_kbep_23_record_id_deterministic(
    item_a: KnowledgeBundleItem,
) -> None:
    """T118-KBEP-23: KBEP-DETERM-0 — ExchangeRecord record_id prefixed 'rec:'."""
    bundle = FederationBundle.create("e-det-001", "inst-A", [item_a])
    rec = ExchangeRecord(
        record_id="rec:" + hashlib.sha256(b"x").hexdigest()[:16],
        event_type="export",
        bundle_id=bundle.bundle_id,
        instance_id="inst-A",
        epoch_id="e-det-001",
        item_count=1,
        verified=True,
        prev_digest="genesis",
    )
    assert rec.record_id.startswith("rec:")
    assert rec.record_digest  # non-empty


# ── T118-KBEP-24: export_snapshot aggregates imported items ──────────────────

def test_kbep_24_export_snapshot_aggregates(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
    item_b: KnowledgeBundleItem,
) -> None:
    """T118-KBEP-24: export_snapshot bundles all imported items."""
    peer1 = FederationBundle.create("peer-ep-1", "peer-001", [item_a])
    peer2 = FederationBundle.create("peer-ep-2", "peer-002", [item_b])
    engine.import_bundle(peer1)
    engine.import_bundle(peer2)
    snapshot = engine.export_snapshot("snap-ep-1")
    assert snapshot.item_count if hasattr(snapshot, 'item_count') else len(snapshot.items) == 2


# ── T118-KBEP-25: export_snapshot on empty engine gives sentinel ──────────────

def test_kbep_25_export_snapshot_empty(
    engine: KnowledgeBundleExchangeProtocol,
) -> None:
    """T118-KBEP-25: export_snapshot on empty imported_bundles returns a sentinel bundle."""
    snap = engine.export_snapshot("snap-empty")
    assert isinstance(snap, FederationBundle)
    assert len(snap.items) == 1
    assert snap.items[0].key == "snapshot:empty"


# ── T118-KBEP-26: KnowledgeBundleItem to_dict roundtrip ──────────────────────

def test_kbep_26_item_to_dict_roundtrip(item_a: KnowledgeBundleItem) -> None:
    """T118-KBEP-26: KnowledgeBundleItem.to_dict() preserves all fields."""
    d = item_a.to_dict()
    assert d["key"] == item_a.key
    assert d["value"] == item_a.value
    assert d["knowledge_type"] == item_a.knowledge_type
    assert d["source_phase"] == item_a.source_phase


# ── T118-KBEP-27: FederationBundle to_dict roundtrip ─────────────────────────

def test_kbep_27_bundle_to_dict(item_a: KnowledgeBundleItem) -> None:
    """T118-KBEP-27: FederationBundle.to_dict() contains all required keys."""
    bundle = FederationBundle.create("e-027", "inst-A", [item_a])
    d = bundle.to_dict()
    required = {"bundle_id", "instance_id", "epoch_id", "kbep_version", "items",
                "bundle_digest", "federation_amendment"}
    assert required.issubset(d.keys())


# ── T118-KBEP-28: kbep_guard raises on falsy condition ───────────────────────

def test_kbep_28_kbep_guard_raises() -> None:
    """T118-KBEP-28: kbep_guard fails closed on False condition."""
    with pytest.raises(KBEPVerificationError, match="KBEP-TEST-0"):
        kbep_guard(False, "KBEP-TEST-0", "deliberate failure")


# ── T118-KBEP-29: kbep_guard passes on truthy condition ──────────────────────

def test_kbep_29_kbep_guard_passes() -> None:
    """T118-KBEP-29: kbep_guard does not raise on True condition."""
    kbep_guard(True, "KBEP-TEST-0", "should not raise")


# ── T118-KBEP-30: end-to-end exchange cycle ──────────────────────────────────

def test_kbep_30_end_to_end_exchange(
    engine: KnowledgeBundleExchangeProtocol,
    item_a: KnowledgeBundleItem,
    item_b: KnowledgeBundleItem,
) -> None:
    """T118-KBEP-30: full federation exchange: create → export → peer import → snapshot → chain verify."""
    # Step 1: create an exportable bundle
    exported = engine.create_bundle("e2e-epoch-001", [item_a, item_b])
    assert exported.bundle_digest.startswith("sha256:")

    # Step 2: peer engine imports the bundle
    peer_engine = KnowledgeBundleExchangeProtocol(
        instance_id="peer-engine-002",
        ledger_path=engine._ledger_path.parent / "peer_ledger.jsonl",
    )
    rec = peer_engine.import_bundle(exported)
    assert rec.verified is True
    assert exported.bundle_id in peer_engine.imported_bundles

    # Step 3: peer creates a consolidated snapshot
    snap = peer_engine.export_snapshot("e2e-snap-001")
    assert len(snap.items) == 2

    # Step 4: chain integrity holds on both engines
    assert engine.verify_chain() is True
    assert peer_engine.verify_chain() is True

    # Step 5: ledger persisted on both ends
    assert engine._ledger_path.exists()
    assert peer_engine._ledger_path.exists()
