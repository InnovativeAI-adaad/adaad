# SPDX-License-Identifier: Apache-2.0
"""Tests for PR-7-01: Reviewer Reputation Ledger.

Validates:
- Entry creation and hash correctness
- Genesis sentinel on first entry
- Hash-chain continuity across multiple entries
- Write-once / duplicate rejection
- Invalid decision rejection
- Chain integrity verification (passes and detects tampering)
- Ledger digest determinism
- reviewer_id derivation is stable and opaque
- Epoch and reviewer filtering
- Persistence: flush() / load() round-trip
- load() integrity verification
- Thread-safety of concurrent appends
- outcome recording
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.reviewer_reputation_ledger import (
    DECISION_APPROVE,
    DECISION_OVERRIDE,
    DECISION_REJECT,
    DECISION_TIMEOUT,
    GENESIS_PREV_HASH,
    LEDGER_EVENT_TYPE,
    LEDGER_FORMAT_VERSION,
    DuplicateReviewError,
    InvalidDecisionError,
    LedgerIntegrityError,
    ReputationLedgerEntry,
    ReviewerReputationLedger,
    derive_reviewer_id,
    new_ledger,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ledger() -> ReviewerReputationLedger:
    return new_ledger()


def _entry(
    ledger: ReviewerReputationLedger,
    *,
    reviewer_id: str = "rid:aa",
    epoch_id: str = "ep-1",
    mutation_id: str = "mut-1",
    decision: str = DECISION_APPROVE,
    rationale_length: int = 120,
    outcome_validated: bool | None = None,
) -> ReputationLedgerEntry:
    return ledger.append(
        reviewer_id=reviewer_id,
        epoch_id=epoch_id,
        mutation_id=mutation_id,
        decision=decision,
        rationale_length=rationale_length,
        outcome_validated=outcome_validated,
    )


# ---------------------------------------------------------------------------
# Entry creation and basic fields
# ---------------------------------------------------------------------------


class TestEntryCreation:
    def test_first_entry_seq_zero(self, ledger):
        e = _entry(ledger)
        assert e.sequence_number == 0

    def test_second_entry_seq_one(self, ledger):
        _entry(ledger, mutation_id="mut-1")
        e = _entry(ledger, mutation_id="mut-2")
        assert e.sequence_number == 1

    def test_first_entry_prev_hash_is_genesis(self, ledger):
        e = _entry(ledger)
        assert e.prev_entry_hash == GENESIS_PREV_HASH

    def test_second_entry_prev_hash_matches_first(self, ledger):
        e1 = _entry(ledger, mutation_id="mut-1")
        e2 = _entry(ledger, mutation_id="mut-2")
        assert e2.prev_entry_hash == e1.entry_hash

    def test_entry_hash_non_empty(self, ledger):
        e = _entry(ledger)
        assert e.entry_hash.startswith("sha256:")
        assert len(e.entry_hash) == len("sha256:") + 64

    def test_entry_hash_verify(self, ledger):
        e = _entry(ledger)
        assert e.verify_hash() is True

    def test_decision_field_stored(self, ledger):
        e = _entry(ledger, decision=DECISION_REJECT)
        assert e.decision == DECISION_REJECT

    def test_rationale_length_stored(self, ledger):
        e = _entry(ledger, rationale_length=42)
        assert e.rationale_length == 42

    def test_outcome_validated_none_by_default(self, ledger):
        e = _entry(ledger)
        assert e.outcome_validated is None

    def test_outcome_validated_stored(self, ledger):
        e = _entry(ledger, outcome_validated=True)
        assert e.outcome_validated is True

    def test_event_type_in_canonical_payload(self, ledger):
        e = _entry(ledger)
        assert e._canonical_payload()["event_type"] == LEDGER_EVENT_TYPE

    def test_ledger_format_version_in_canonical_payload(self, ledger):
        e = _entry(ledger)
        assert e._canonical_payload()["ledger_format_version"] == LEDGER_FORMAT_VERSION

    def test_to_dict_round_trip(self, ledger):
        e = _entry(ledger)
        d = e.to_dict()
        e2 = ReputationLedgerEntry.from_dict(d)
        assert e2.entry_hash == e.entry_hash
        assert e2.sequence_number == e.sequence_number
        assert e2.decision == e.decision


# ---------------------------------------------------------------------------
# All valid decisions accepted
# ---------------------------------------------------------------------------


class TestDecisionValues:
    @pytest.mark.parametrize(
        "decision",
        [DECISION_APPROVE, DECISION_REJECT, DECISION_TIMEOUT, DECISION_OVERRIDE],
    )
    def test_valid_decisions_accepted(self, ledger, decision):
        e = ledger.append(
            reviewer_id="rid:x",
            epoch_id="ep-1",
            mutation_id=f"mut-{decision}",
            decision=decision,
            rationale_length=10,
        )
        assert e.decision == decision

    def test_invalid_decision_raises(self, ledger):
        with pytest.raises(InvalidDecisionError):
            ledger.append(
                reviewer_id="rid:x",
                epoch_id="ep-1",
                mutation_id="mut-bad",
                decision="rubber_stamp",
                rationale_length=0,
            )


# ---------------------------------------------------------------------------
# Write-once invariant
# ---------------------------------------------------------------------------


class TestWriteOnce:
    def test_duplicate_key_raises(self, ledger):
        _entry(ledger, reviewer_id="rid:a", epoch_id="ep-1", mutation_id="mut-1")
        with pytest.raises(DuplicateReviewError):
            _entry(ledger, reviewer_id="rid:a", epoch_id="ep-1", mutation_id="mut-1")

    def test_different_mutation_id_allowed(self, ledger):
        _entry(ledger, reviewer_id="rid:a", epoch_id="ep-1", mutation_id="mut-1")
        e2 = _entry(ledger, reviewer_id="rid:a", epoch_id="ep-1", mutation_id="mut-2")
        assert e2.mutation_id == "mut-2"

    def test_different_epoch_id_allowed(self, ledger):
        _entry(ledger, reviewer_id="rid:a", epoch_id="ep-1", mutation_id="mut-1")
        e2 = _entry(ledger, reviewer_id="rid:a", epoch_id="ep-2", mutation_id="mut-1")
        assert e2.epoch_id == "ep-2"

    def test_different_reviewer_id_allowed(self, ledger):
        _entry(ledger, reviewer_id="rid:a", epoch_id="ep-1", mutation_id="mut-1")
        e2 = _entry(ledger, reviewer_id="rid:b", epoch_id="ep-1", mutation_id="mut-1")
        assert e2.reviewer_id == "rid:b"


# ---------------------------------------------------------------------------
# Hash-chain integrity
# ---------------------------------------------------------------------------


class TestChainIntegrity:
    def test_empty_ledger_integrity_passes(self, ledger):
        assert ledger.verify_chain_integrity() is True

    def test_single_entry_integrity_passes(self, ledger):
        _entry(ledger)
        assert ledger.verify_chain_integrity() is True

    def test_multi_entry_integrity_passes(self, ledger):
        for i in range(5):
            _entry(ledger, mutation_id=f"mut-{i}")
        assert ledger.verify_chain_integrity() is True

    def test_tampered_entry_hash_detected(self, ledger):
        _entry(ledger, mutation_id="mut-0")
        _entry(ledger, mutation_id="mut-1")
        # Corrupt the first entry's hash directly
        bad = ReputationLedgerEntry(
            sequence_number=ledger._entries[0].sequence_number,
            reviewer_id=ledger._entries[0].reviewer_id,
            epoch_id=ledger._entries[0].epoch_id,
            mutation_id=ledger._entries[0].mutation_id,
            decision=ledger._entries[0].decision,
            rationale_length=ledger._entries[0].rationale_length,
            outcome_validated=ledger._entries[0].outcome_validated,
            scoring_algorithm_version=ledger._entries[0].scoring_algorithm_version,
            prev_entry_hash=ledger._entries[0].prev_entry_hash,
            entry_hash="sha256:" + "f" * 64,
        )
        ledger._entries[0] = bad
        with pytest.raises(LedgerIntegrityError):
            ledger.verify_chain_integrity()

    def test_broken_prev_hash_detected(self, ledger):
        _entry(ledger, mutation_id="mut-0")
        _entry(ledger, mutation_id="mut-1")
        # Alter prev_entry_hash on the second entry
        bad = ReputationLedgerEntry(
            sequence_number=ledger._entries[1].sequence_number,
            reviewer_id=ledger._entries[1].reviewer_id,
            epoch_id=ledger._entries[1].epoch_id,
            mutation_id=ledger._entries[1].mutation_id,
            decision=ledger._entries[1].decision,
            rationale_length=ledger._entries[1].rationale_length,
            outcome_validated=ledger._entries[1].outcome_validated,
            scoring_algorithm_version=ledger._entries[1].scoring_algorithm_version,
            prev_entry_hash="sha256:" + "0" * 64,
            entry_hash=ledger._entries[1].entry_hash,
        )
        ledger._entries[1] = bad
        with pytest.raises(LedgerIntegrityError):
            ledger.verify_chain_integrity()


# ---------------------------------------------------------------------------
# Ledger digest determinism
# ---------------------------------------------------------------------------


class TestLedgerDigest:
    def test_empty_digest_is_stable(self):
        l1 = new_ledger()
        l2 = new_ledger()
        assert l1.ledger_digest() == l2.ledger_digest()

    def test_digest_changes_after_append(self, ledger):
        d0 = ledger.ledger_digest()
        _entry(ledger)
        d1 = ledger.ledger_digest()
        assert d0 != d1

    def test_same_sequence_same_digest(self):
        l1 = new_ledger()
        l2 = new_ledger()
        for lid in (l1, l2):
            lid.append(
                reviewer_id="rid:x",
                epoch_id="ep-1",
                mutation_id="mut-1",
                decision=DECISION_APPROVE,
                rationale_length=100,
            )
        assert l1.ledger_digest() == l2.ledger_digest()

    def test_different_order_different_digest(self):
        l1 = new_ledger()
        l2 = new_ledger()
        l1.append(reviewer_id="rid:a", epoch_id="ep-1", mutation_id="mut-1",
                  decision=DECISION_APPROVE, rationale_length=10)
        l1.append(reviewer_id="rid:b", epoch_id="ep-1", mutation_id="mut-2",
                  decision=DECISION_REJECT, rationale_length=20)
        l2.append(reviewer_id="rid:b", epoch_id="ep-1", mutation_id="mut-2",
                  decision=DECISION_REJECT, rationale_length=20)
        l2.append(reviewer_id="rid:a", epoch_id="ep-1", mutation_id="mut-1",
                  decision=DECISION_APPROVE, rationale_length=10)
        assert l1.ledger_digest() != l2.ledger_digest()


# ---------------------------------------------------------------------------
# reviewer_id derivation
# ---------------------------------------------------------------------------


class TestDeriveReviewerId:
    def test_output_starts_with_rid(self):
        rid = derive_reviewer_id("SHA256:abc", hmac_secret=b"secret")
        assert rid.startswith("rid:")

    def test_stable_for_same_inputs(self):
        a = derive_reviewer_id("SHA256:abc", hmac_secret=b"secret")
        b = derive_reviewer_id("SHA256:abc", hmac_secret=b"secret")
        assert a == b

    def test_different_fingerprints_different_ids(self):
        a = derive_reviewer_id("SHA256:abc", hmac_secret=b"secret")
        b = derive_reviewer_id("SHA256:xyz", hmac_secret=b"secret")
        assert a != b

    def test_different_secrets_different_ids(self):
        a = derive_reviewer_id("SHA256:abc", hmac_secret=b"secret1")
        b = derive_reviewer_id("SHA256:abc", hmac_secret=b"secret2")
        assert a != b

    def test_opaque_no_plaintext(self):
        rid = derive_reviewer_id("SHA256:abc", hmac_secret=b"secret")
        assert "abc" not in rid
        assert "SHA256" not in rid


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


class TestQueryHelpers:
    def test_entries_for_reviewer(self, ledger):
        _entry(ledger, reviewer_id="rid:a", mutation_id="mut-1")
        _entry(ledger, reviewer_id="rid:b", mutation_id="mut-2")
        _entry(ledger, reviewer_id="rid:a", mutation_id="mut-3")
        result = ledger.entries_for_reviewer("rid:a")
        assert len(result) == 2
        assert all(e.reviewer_id == "rid:a" for e in result)

    def test_entries_for_epoch(self, ledger):
        _entry(ledger, epoch_id="ep-1", mutation_id="mut-1")
        _entry(ledger, epoch_id="ep-2", mutation_id="mut-2")
        _entry(ledger, epoch_id="ep-1", mutation_id="mut-3")
        result = ledger.entries_for_epoch("ep-1")
        assert len(result) == 2
        assert all(e.epoch_id == "ep-1" for e in result)

    def test_len(self, ledger):
        assert len(ledger) == 0
        _entry(ledger, mutation_id="mut-1")
        assert len(ledger) == 1

    def test_entries_returns_snapshot(self, ledger):
        _entry(ledger, mutation_id="mut-1")
        snap = ledger.entries()
        assert len(snap) == 1
        # Appending after snapshot does not mutate it
        _entry(ledger, mutation_id="mut-2")
        assert len(snap) == 1


# ---------------------------------------------------------------------------
# Outcome recording
# ---------------------------------------------------------------------------


class TestOutcomeRecording:
    def test_record_outcome_appends_entry(self, ledger):
        _entry(ledger, reviewer_id="rid:a", mutation_id="mut-1")
        ledger.record_outcome(
            reviewer_id="rid:a",
            mutation_id="mut-1",
            epoch_id="ep-1",
            outcome_validated=True,
        )
        assert len(ledger) == 2

    def test_record_outcome_uses_original_decision(self, ledger):
        _entry(ledger, reviewer_id="rid:a", mutation_id="mut-1", decision=DECISION_REJECT)
        e = ledger.record_outcome(
            reviewer_id="rid:a",
            mutation_id="mut-1",
            epoch_id="ep-1",
            outcome_validated=False,
        )
        assert e.decision == DECISION_REJECT
        assert e.outcome_validated is False


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_flush_creates_file(self, tmp_path, ledger):
        _entry(ledger, mutation_id="mut-1")
        target = tmp_path / "rep_ledger.jsonl"
        ledger.flush(target)
        assert target.exists()
        assert target.stat().st_size > 0

    def test_flush_load_round_trip(self, tmp_path, ledger):
        for i in range(3):
            _entry(ledger, mutation_id=f"mut-{i}")
        target = tmp_path / "rep_ledger.jsonl"
        ledger.flush(target)

        loaded = ReviewerReputationLedger.load(target)
        assert len(loaded) == len(ledger)
        assert loaded.ledger_digest() == ledger.ledger_digest()

    def test_load_verifies_integrity(self, tmp_path, ledger):
        _entry(ledger, mutation_id="mut-1")
        target = tmp_path / "rep_ledger.jsonl"
        ledger.flush(target)

        # Tamper the file
        lines = target.read_text().splitlines()
        data = json.loads(lines[0])
        data["rationale_length"] = 9999
        lines[0] = json.dumps(data)
        target.write_text("\n".join(lines))

        with pytest.raises(LedgerIntegrityError):
            ReviewerReputationLedger.load(target, verify_integrity=True)

    def test_load_non_existent_path_returns_empty(self, tmp_path):
        loaded = ReviewerReputationLedger.load(tmp_path / "nonexistent.jsonl")
        assert len(loaded) == 0

    def test_flush_no_path_raises(self):
        ledger = new_ledger()  # no path configured
        with pytest.raises(ValueError):
            ledger.flush()


# ---------------------------------------------------------------------------
# Thread-safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_appends_all_succeed(self):
        """50 concurrent appends each with a unique key must all succeed."""
        ledger = new_ledger()
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                ledger.append(
                    reviewer_id=f"rid:{idx}",
                    epoch_id="ep-1",
                    mutation_id=f"mut-{idx}",
                    decision=DECISION_APPROVE,
                    rationale_length=idx,
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(ledger) == 50
        assert ledger.verify_chain_integrity() is True
