# SPDX-License-Identifier: Apache-2.0
"""Tests for runtime.evolution.checkpoint_chain (new chained checkpoint module)."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.checkpoint_chain import (
    CHAIN_VERSION,
    ChainedCheckpoint,
    build_checkpoint_chain,
    checkpoint_chain_digest,
    verify_checkpoint_chain,
)
from runtime.governance.foundation.hashing import ZERO_HASH


def test_genesis_links_to_zero_hash():
    cp = checkpoint_chain_digest({"state": "boot"}, epoch_id="epoch_0")
    assert cp.predecessor_digest == ZERO_HASH


def test_chain_links_correctly():
    genesis = checkpoint_chain_digest({"state": "boot"}, epoch_id="epoch_0")
    next_cp = checkpoint_chain_digest(
        {"state": "evolved"},
        epoch_id="epoch_1",
        predecessor_digest=genesis.chain_digest,
    )
    assert next_cp.predecessor_digest == genesis.chain_digest


def test_identical_inputs_are_deterministic():
    cp1 = checkpoint_chain_digest({"x": 1}, epoch_id="e0")
    cp2 = checkpoint_chain_digest({"x": 1}, epoch_id="e0")
    assert cp1.chain_digest == cp2.chain_digest


def test_different_payloads_produce_different_digests():
    cp1 = checkpoint_chain_digest({"x": 1}, epoch_id="e0")
    cp2 = checkpoint_chain_digest({"x": 2}, epoch_id="e0")
    assert cp1.chain_digest != cp2.chain_digest


def test_build_chain_three_entries():
    entries = [
        ("epoch_0", {"state": "boot"}),
        ("epoch_1", {"state": "evolve_1"}),
        ("epoch_2", {"state": "evolve_2"}),
    ]
    chain = build_checkpoint_chain(entries)
    assert len(chain) == 3
    assert chain[0].predecessor_digest == ZERO_HASH
    assert chain[1].predecessor_digest == chain[0].chain_digest
    assert chain[2].predecessor_digest == chain[1].chain_digest


def test_build_chain_empty_raises():
    with pytest.raises(ValueError, match="checkpoint_chain_requires_at_least_one_entry"):
        build_checkpoint_chain([])


def test_verify_valid_chain():
    entries = [("e0", {"v": 1}), ("e1", {"v": 2}), ("e2", {"v": 3})]
    chain = build_checkpoint_chain(entries)
    assert verify_checkpoint_chain(chain) is True


def test_verify_empty_chain_fails():
    assert verify_checkpoint_chain([]) is False


def test_verify_tampered_payload_fails():
    chain = build_checkpoint_chain([("e0", {"v": 1}), ("e1", {"v": 2})])
    tampered = ChainedCheckpoint(
        epoch_id=chain[0].epoch_id,
        payload={"v": 999},
        predecessor_digest=chain[0].predecessor_digest,
        payload_digest="sha256:" + "f" * 64,
        chain_digest=chain[0].chain_digest,
    )
    assert verify_checkpoint_chain([tampered, chain[1]]) is False


def test_verify_broken_predecessor_link_fails():
    chain = build_checkpoint_chain([("e0", {"v": 1}), ("e1", {"v": 2}), ("e2", {"v": 3})])
    broken_entry = checkpoint_chain_digest({"v": 2}, epoch_id="e1", predecessor_digest=ZERO_HASH)
    assert verify_checkpoint_chain([chain[0], broken_entry, chain[2]]) is False


def test_ledger_event_structure():
    cp = checkpoint_chain_digest({"state": "boot"}, epoch_id="epoch_0")
    event = cp.to_ledger_event()
    assert event["event_type"] == "checkpoint_chain_link"
    assert event["epoch_id"] == "epoch_0"
    assert event["chain_version"] == CHAIN_VERSION
    assert event["chain_digest"] == cp.chain_digest
