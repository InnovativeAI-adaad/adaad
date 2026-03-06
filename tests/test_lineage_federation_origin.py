# SPDX-License-Identifier: Apache-2.0
"""Tests for Phase 5 FederationOrigin lineage extension.

Invariants under test
---------------------
- FederationOrigin serialises to / deserialises from a deterministic dict.
- MutationBundleEvent.is_federated() returns True iff federation_origin is set.
- MutationBundleEvent.to_certificate_dict() embeds federation_origin under
  'federation_origin' key when present; omits key entirely when None.
- LineageLedgerV2.append_typed_event() writes federation_origin into certificate
  and the resulting ledger entry is readable / integrity-verifiable.
- Local (non-federated) MutationBundleEvents are unaffected by the Phase 5 change.
- Determinism: two identical FederationOrigin instances produce identical dicts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.evolution.lineage_v2 import (
    FederationOrigin,
    LineageLedgerV2,
    MutationBundleEvent,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ORIGIN = FederationOrigin(
    source_repo="InnovativeAI-adaad/ADAAD-payments",
    source_epoch_id="epoch-payments-042",
    source_mutation_id="mut-payments-007",
    source_chain_digest="sha256:" + "a" * 64,
    federation_gate_id="gate-fed-001",
)

_CERT_BASE: dict = {
    "agent_id": "architect",
    "mutation_id": "mut-local-001",
    "strategy_snapshot_hash": "snap-" + "b" * 32,
}


def _make_local_event(**kwargs) -> MutationBundleEvent:
    return MutationBundleEvent(
        epoch_id="epoch-001",
        bundle_id="bundle-001",
        impact=0.75,
        certificate=dict(_CERT_BASE),
        **kwargs,
    )


def _make_federated_event(**kwargs) -> MutationBundleEvent:
    return MutationBundleEvent(
        epoch_id="epoch-002",
        bundle_id="bundle-fed-001",
        impact=0.65,
        certificate=dict(_CERT_BASE),
        federation_origin=_ORIGIN,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# FederationOrigin unit tests
# ---------------------------------------------------------------------------


class TestFederationOrigin:
    def test_to_dict_contains_all_fields(self) -> None:
        d = _ORIGIN.to_dict()
        assert d["source_repo"] == _ORIGIN.source_repo
        assert d["source_epoch_id"] == _ORIGIN.source_epoch_id
        assert d["source_mutation_id"] == _ORIGIN.source_mutation_id
        assert d["source_chain_digest"] == _ORIGIN.source_chain_digest
        assert d["federation_gate_id"] == _ORIGIN.federation_gate_id

    def test_to_dict_is_deterministic(self) -> None:
        """Two identical FederationOrigin instances must produce identical dicts."""
        origin_a = FederationOrigin(
            source_repo="repo-x",
            source_epoch_id="ep-1",
            source_mutation_id="mut-1",
            source_chain_digest="sha256:" + "c" * 64,
        )
        origin_b = FederationOrigin(
            source_repo="repo-x",
            source_epoch_id="ep-1",
            source_mutation_id="mut-1",
            source_chain_digest="sha256:" + "c" * 64,
        )
        assert origin_a.to_dict() == origin_b.to_dict()

    def test_from_dict_roundtrip(self) -> None:
        reconstructed = FederationOrigin.from_dict(_ORIGIN.to_dict())
        assert reconstructed == _ORIGIN

    def test_from_dict_default_gate_id(self) -> None:
        data = _ORIGIN.to_dict()
        del data["federation_gate_id"]
        origin = FederationOrigin.from_dict(data)
        assert origin.federation_gate_id == ""

    def test_to_dict_keys_sorted(self) -> None:
        """Keys must be in sorted order for canonical JSON serialisation."""
        keys = list(_ORIGIN.to_dict().keys())
        assert keys == sorted(keys)

    def test_json_serialisable(self) -> None:
        serialised = json.dumps(_ORIGIN.to_dict(), sort_keys=True)
        assert "source_repo" in serialised
        assert "InnovativeAI-adaad/ADAAD-payments" in serialised


# ---------------------------------------------------------------------------
# MutationBundleEvent Phase 5 contract
# ---------------------------------------------------------------------------


class TestMutationBundleEventPhase5:
    def test_is_federated_false_for_local(self) -> None:
        assert _make_local_event().is_federated() is False

    def test_is_federated_true_for_federated(self) -> None:
        assert _make_federated_event().is_federated() is True

    def test_to_certificate_dict_local_omits_federation_key(self) -> None:
        cert = _make_local_event().to_certificate_dict()
        assert "federation_origin" not in cert

    def test_to_certificate_dict_federated_embeds_origin(self) -> None:
        cert = _make_federated_event().to_certificate_dict()
        assert "federation_origin" in cert
        assert cert["federation_origin"]["source_repo"] == _ORIGIN.source_repo

    def test_to_certificate_dict_preserves_original_cert_fields(self) -> None:
        cert = _make_federated_event().to_certificate_dict()
        for key, val in _CERT_BASE.items():
            assert cert[key] == val

    def test_to_certificate_dict_local_identical_to_certificate(self) -> None:
        """Local event: to_certificate_dict() must equal the raw certificate dict."""
        event = _make_local_event()
        assert event.to_certificate_dict() == event.certificate

    def test_federation_origin_in_cert_is_deterministic(self) -> None:
        cert_a = _make_federated_event().to_certificate_dict()
        cert_b = _make_federated_event().to_certificate_dict()
        assert cert_a == cert_b

    def test_default_federation_origin_is_none(self) -> None:
        event = _make_local_event()
        assert event.federation_origin is None


# ---------------------------------------------------------------------------
# LineageLedgerV2 integration — ledger write/read with federation_origin
# ---------------------------------------------------------------------------


class TestLineageLedgerV2FederationOrigin:
    def test_federated_event_appended_and_readable(self, tmp_path: Path) -> None:
        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
        event = _make_federated_event()
        ledger.append_typed_event(event)

        entries = ledger.read_all()
        assert len(entries) == 1
        payload = entries[0]["payload"]
        cert = payload["certificate"]
        assert "federation_origin" in cert
        assert cert["federation_origin"]["source_repo"] == _ORIGIN.source_repo
        assert cert["federation_origin"]["source_epoch_id"] == _ORIGIN.source_epoch_id
        assert cert["federation_origin"]["source_chain_digest"] == _ORIGIN.source_chain_digest

    def test_local_event_appended_without_federation_key(self, tmp_path: Path) -> None:
        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
        event = _make_local_event()
        ledger.append_typed_event(event)

        entries = ledger.read_all()
        cert = entries[0]["payload"]["certificate"]
        assert "federation_origin" not in cert

    def test_integrity_holds_after_federated_event(self, tmp_path: Path) -> None:
        """Hash-chain integrity must hold after appending a federated event."""
        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
        ledger.append_typed_event(_make_federated_event())
        # verify_integrity raises on tampering; must complete silently here
        ledger.verify_integrity()

    def test_mixed_local_and_federated_events(self, tmp_path: Path) -> None:
        """Mixed local + federated events must all preserve integrity."""
        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
        ledger.append_typed_event(_make_local_event())
        ledger.append_typed_event(_make_federated_event())
        ledger.append_typed_event(MutationBundleEvent(epoch_id="epoch-003", bundle_id="bundle-003", impact=0.55, certificate=dict(_CERT_BASE)))

        entries = ledger.read_all()
        assert len(entries) == 3
        assert "federation_origin" not in entries[0]["payload"]["certificate"]
        assert "federation_origin" in entries[1]["payload"]["certificate"]
        assert "federation_origin" not in entries[2]["payload"]["certificate"]
        ledger.verify_integrity()

    def test_federation_gate_id_persisted(self, tmp_path: Path) -> None:
        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
        ledger.append_typed_event(_make_federated_event())
        entries = ledger.read_all()
        gate_id = entries[0]["payload"]["certificate"]["federation_origin"]["federation_gate_id"]
        assert gate_id == "gate-fed-001"

    def test_standard_fields_intact_for_federated_event(self, tmp_path: Path) -> None:
        """Non-federation payload fields must be unchanged."""
        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
        event = _make_federated_event()
        ledger.append_typed_event(event)
        payload = ledger.read_all()[0]["payload"]
        assert payload["epoch_id"] == event.epoch_id
        assert payload["bundle_id"] == event.bundle_id
        assert abs(payload["impact"] - event.impact) < 1e-9
