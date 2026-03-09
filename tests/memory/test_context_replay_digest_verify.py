# SPDX-License-Identifier: Apache-2.0
"""Phase 12 / Track 11-C — Cross-epoch ledger digest verification (PR-12-C-01).

Tests verify:
  T12-C-01  SoulboundLedger.current_chain_hash() exists and returns the chain tip
  T12-C-02  verify_replay_digest() returns True when digest matches current_chain_hash
  T12-C-03  verify_replay_digest() returns False when digest does not match
  T12-C-04  verify_replay_digest() returns False on empty digest
  T12-C-05  verify_replay_digest() emits context_digest_mismatch.v1 on mismatch
  T12-C-06  verify_replay_digest() returns False and emits event on ledger read error
  T12-C-07  EvolutionLoop Phase 0c skips injection when verify_replay_digest returns False
  T12-C-08  EvolutionLoop Phase 0c applies injection when verify_replay_digest returns True
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from runtime.memory.context_replay_interface import ContextReplayInterface
from runtime.memory.soulbound_ledger import SoulboundLedger


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FAKE_HASH = "a" * 64
_OTHER_HASH = "b" * 64


def _make_mock_ledger(chain_hash: str = _FAKE_HASH) -> MagicMock:
    ledger = MagicMock(spec=SoulboundLedger)
    ledger.current_chain_hash.return_value = chain_hash
    ledger.last_chain_hash.return_value = chain_hash
    ledger._all_entries.return_value = []
    return ledger


def _make_replay_interface(
    chain_hash: str = _FAKE_HASH,
    audit_events: list | None = None,
) -> ContextReplayInterface:
    ledger = _make_mock_ledger(chain_hash)
    events = audit_events if audit_events is not None else []

    def _capture_audit(tx_type: str, payload: dict) -> dict:
        events.append({"tx_type": tx_type, "payload": payload})
        return {}

    return ContextReplayInterface(ledger=ledger, audit_writer=_capture_audit), events


# ---------------------------------------------------------------------------
# T12-C-01: SoulboundLedger.current_chain_hash()
# ---------------------------------------------------------------------------

class TestSoulboundLedgerCurrentChainHash:
    def _make_ledger(self, tmp_path):
        return SoulboundLedger(ledger_path=tmp_path / "ledger.json")

    def test_current_chain_hash_method_exists(self, tmp_path):
        ledger = self._make_ledger(tmp_path)
        assert hasattr(ledger, "current_chain_hash")
        assert callable(ledger.current_chain_hash)

    def test_current_chain_hash_returns_string(self, tmp_path):
        ledger = self._make_ledger(tmp_path)
        result = ledger.current_chain_hash()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_current_chain_hash_equals_last_chain_hash(self, tmp_path):
        ledger = self._make_ledger(tmp_path)
        assert ledger.current_chain_hash() == ledger.last_chain_hash()


# ---------------------------------------------------------------------------
# T12-C-02: verify_replay_digest() match
# ---------------------------------------------------------------------------

class TestVerifyReplayDigestMatch:
    def test_returns_true_when_digest_matches(self):
        replay, _ = _make_replay_interface(chain_hash=_FAKE_HASH)
        result = replay.verify_replay_digest(digest=_FAKE_HASH, epoch_id="ep-001")
        assert result is True

    def test_no_mismatch_event_emitted_on_match(self):
        replay, events = _make_replay_interface(chain_hash=_FAKE_HASH)
        replay.verify_replay_digest(digest=_FAKE_HASH, epoch_id="ep-001")
        mismatch_events = [e for e in events if e["tx_type"] == "context_digest_mismatch.v1"]
        assert len(mismatch_events) == 0


# ---------------------------------------------------------------------------
# T12-C-03: verify_replay_digest() mismatch
# ---------------------------------------------------------------------------

class TestVerifyReplayDigestMismatch:
    def test_returns_false_when_digest_does_not_match(self):
        replay, _ = _make_replay_interface(chain_hash=_OTHER_HASH)
        result = replay.verify_replay_digest(digest=_FAKE_HASH, epoch_id="ep-002")
        assert result is False

    def test_mismatch_event_emitted_on_hash_divergence(self):
        replay, events = _make_replay_interface(chain_hash=_OTHER_HASH)
        replay.verify_replay_digest(digest=_FAKE_HASH, epoch_id="ep-002")
        mismatch_events = [e for e in events if e["tx_type"] == "context_digest_mismatch.v1"]
        assert len(mismatch_events) == 1

    def test_mismatch_event_payload_contains_epoch_id(self):
        replay, events = _make_replay_interface(chain_hash=_OTHER_HASH)
        replay.verify_replay_digest(digest=_FAKE_HASH, epoch_id="ep-xyz")
        evt = next(e for e in events if e["tx_type"] == "context_digest_mismatch.v1")
        assert evt["payload"]["epoch_id"] == "ep-xyz"

    def test_mismatch_event_payload_match_is_false(self):
        replay, events = _make_replay_interface(chain_hash=_OTHER_HASH)
        replay.verify_replay_digest(digest=_FAKE_HASH, epoch_id="ep-003")
        evt = next(e for e in events if e["tx_type"] == "context_digest_mismatch.v1")
        assert evt["payload"]["match"] is False


# ---------------------------------------------------------------------------
# T12-C-04: Empty digest always returns False
# ---------------------------------------------------------------------------

class TestVerifyReplayDigestEmpty:
    def test_empty_digest_returns_false(self):
        replay, _ = _make_replay_interface()
        assert replay.verify_replay_digest(digest="", epoch_id="ep-004") is False

    def test_empty_digest_emits_mismatch_event(self):
        replay, events = _make_replay_interface()
        replay.verify_replay_digest(digest="", epoch_id="ep-004")
        mismatch_events = [e for e in events if e["tx_type"] == "context_digest_mismatch.v1"]
        assert len(mismatch_events) == 1

    def test_empty_digest_event_reason_is_empty_digest(self):
        replay, events = _make_replay_interface()
        replay.verify_replay_digest(digest="", epoch_id="ep-004")
        evt = next(e for e in events if e["tx_type"] == "context_digest_mismatch.v1")
        assert evt["payload"]["reason"] == "empty_digest"


# ---------------------------------------------------------------------------
# T12-C-06: Ledger read error → False + event
# ---------------------------------------------------------------------------

class TestVerifyReplayDigestLedgerError:
    def test_ledger_read_error_returns_false(self):
        ledger = MagicMock(spec=SoulboundLedger)
        ledger.current_chain_hash.side_effect = IOError("ledger locked")
        ledger._all_entries.return_value = []
        events: list = []

        def _audit(tx_type, payload):
            events.append({"tx_type": tx_type, "payload": payload})
            return {}

        replay = ContextReplayInterface(ledger=ledger, audit_writer=_audit)
        result = replay.verify_replay_digest(digest=_FAKE_HASH, epoch_id="ep-err")
        assert result is False

    def test_ledger_read_error_emits_mismatch_event(self):
        ledger = MagicMock(spec=SoulboundLedger)
        ledger.current_chain_hash.side_effect = IOError("ledger locked")
        ledger._all_entries.return_value = []
        events: list = []

        def _audit(tx_type, payload):
            events.append({"tx_type": tx_type, "payload": payload})
            return {}

        replay = ContextReplayInterface(ledger=ledger, audit_writer=_audit)
        replay.verify_replay_digest(digest=_FAKE_HASH, epoch_id="ep-err")
        mismatch_events = [e for e in events if e["tx_type"] == "context_digest_mismatch.v1"]
        assert len(mismatch_events) == 1


# ---------------------------------------------------------------------------
# T12-C-07/08: EvolutionLoop Phase 0c wiring
# ---------------------------------------------------------------------------

class TestEvolutionLoopDigestVerificationWiring:
    """Verify Phase 0c skips injection on verify_replay_digest=False and applies on True."""

    def _run_epoch_with_mock_replay(self, verify_returns: bool):
        from runtime.evolution.evolution_loop import EvolutionLoop
        from runtime.autonomy.ai_mutation_proposer import CodebaseContext

        mock_replay = MagicMock(spec=ContextReplayInterface)

        # build_injection returns a non-skipped, quality-ok injection
        fake_injection = MagicMock()
        fake_injection.skipped = False
        fake_injection.signal_quality_ok = True
        fake_injection.context_digest = _FAKE_HASH
        fake_injection.adjusted_explore_ratio = 0.75
        fake_injection.dominant_pattern = "structural"
        fake_injection.mean_elite_score = 0.42
        fake_injection.valid_entry_count = 3

        mock_replay.build_injection.return_value = fake_injection
        mock_replay.verify_replay_digest.return_value = verify_returns

        loop = EvolutionLoop(
            api_key="k",
            simulate_outcomes=True,
            replay_interface=mock_replay,
        )
        ctx = CodebaseContext(
            file_summaries={},
            recent_failures=[],
            current_epoch_id="ep-verify-test",
        )
        with patch(
            "runtime.evolution.evolution_loop.propose_from_all_agents",
            return_value=[],
        ):
            loop.run_epoch(ctx)
        return ctx, mock_replay

    def test_injection_skipped_when_verify_returns_false(self):
        ctx, _ = self._run_epoch_with_mock_replay(verify_returns=False)
        # explore_ratio should remain at default (not overridden)
        assert ctx.explore_ratio != 0.75

    def test_injection_applied_when_verify_returns_true(self):
        ctx, _ = self._run_epoch_with_mock_replay(verify_returns=True)
        assert ctx.explore_ratio == 0.75

    def test_verify_called_with_correct_digest_and_epoch_id(self):
        _, mock_replay = self._run_epoch_with_mock_replay(verify_returns=True)
        mock_replay.verify_replay_digest.assert_called_once_with(
            digest=_FAKE_HASH,
            epoch_id="ep-verify-test",
        )
