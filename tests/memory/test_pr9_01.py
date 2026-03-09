# SPDX-License-Identifier: Apache-2.0
"""
Phase 9 PR-9-01 — Test suite for SoulboundKey, SoulboundLedger, ContextFilterChain.

Test IDs: T9-01-01 through T9-01-25

Coverage:
    SoulboundKey    (T9-01-01..07) — env key loading, signing, verification, fail-closed
    SoulboundLedger (T9-01-08..17) — append, chain integrity, tamper detection, rotation
    ContextFilterChain (T9-01-18..25) — built-in filters, custom filters, chain halt
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

# ─── Test key helpers ───────────────────────────────────────────────────────

_TEST_KEY_HEX = "a" * 64        # 32-byte all-0xaa key for deterministic testing
_TEST_KEY_BYTES = bytes.fromhex(_TEST_KEY_HEX)


def _set_test_key(monkeypatch):
    monkeypatch.setenv("ADAAD_SOULBOUND_KEY", _TEST_KEY_HEX)


def _no_op_audit(*args, **kwargs):
    return {}


# ════════════════════════════════════════════════════════════════════════════
# SoulboundKey — T9-01-01..07
# ════════════════════════════════════════════════════════════════════════════

class TestSoulboundKey:

    def test_T9_01_01_get_key_returns_bytes_when_env_set(self, monkeypatch):
        """get_key() must return bytes equal to decoded env var."""
        _set_test_key(monkeypatch)
        from runtime.memory.soulbound_key import get_key
        key = get_key()
        assert isinstance(key, bytes)
        assert key == _TEST_KEY_BYTES

    def test_T9_01_02_get_key_raises_when_env_absent(self, monkeypatch):
        """get_key() must raise SoulboundKeyError when ADAAD_SOULBOUND_KEY is absent."""
        monkeypatch.delenv("ADAAD_SOULBOUND_KEY", raising=False)
        from runtime.memory.soulbound_key import get_key, SoulboundKeyError
        with pytest.raises(SoulboundKeyError):
            get_key()

    def test_T9_01_03_get_key_raises_on_non_hex(self, monkeypatch):
        """get_key() must raise SoulboundKeyError when env value is not valid hex."""
        monkeypatch.setenv("ADAAD_SOULBOUND_KEY", "not-hex-at-all!!")
        from runtime.memory.soulbound_key import get_key, SoulboundKeyError
        with pytest.raises(SoulboundKeyError):
            get_key()

    def test_T9_01_04_get_key_raises_when_key_too_short(self, monkeypatch):
        """get_key() must raise when decoded key is < 32 bytes."""
        monkeypatch.setenv("ADAAD_SOULBOUND_KEY", "deadbeef")  # 4 bytes only
        from runtime.memory.soulbound_key import get_key, SoulboundKeyError
        with pytest.raises(SoulboundKeyError, match="minimum"):
            get_key()

    def test_T9_01_05_sign_returns_64_char_hex(self):
        """sign() with key_override must return a 64-char hex HMAC-SHA256."""
        from runtime.memory.soulbound_key import sign
        result = sign(b"test data", key=_TEST_KEY_BYTES)
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_T9_01_06_verify_returns_true_for_valid_sig(self):
        """verify() must return True when signature matches."""
        from runtime.memory.soulbound_key import sign, verify
        data = b"canonical context data"
        sig = sign(data, key=_TEST_KEY_BYTES)
        assert verify(data, sig, key=_TEST_KEY_BYTES) is True

    def test_T9_01_07_verify_returns_false_for_tampered_data(self):
        """verify() must return False when data does not match signature."""
        from runtime.memory.soulbound_key import sign, verify
        data = b"original data"
        sig = sign(data, key=_TEST_KEY_BYTES)
        assert verify(b"tampered data", sig, key=_TEST_KEY_BYTES) is False


# ════════════════════════════════════════════════════════════════════════════
# SoulboundLedger — T9-01-08..17
# ════════════════════════════════════════════════════════════════════════════

class TestSoulboundLedger:

    def _make_ledger(self, tmp_path: Path):
        from runtime.memory.soulbound_ledger import SoulboundLedger
        return SoulboundLedger(
            ledger_path=tmp_path / "ledger.json",
            audit_writer=_no_op_audit,
            key_override=_TEST_KEY_BYTES,
        )

    def _payload(self, **kw) -> Dict[str, Any]:
        return {"epoch_id": "epoch-042", "context_hash": "abc123", **kw}

    def test_T9_01_08_append_returns_accepted_for_valid_entry(self, tmp_path):
        """append() must return AppendResult with accepted=True for valid input."""
        ledger = self._make_ledger(tmp_path)
        result = ledger.append(
            epoch_id="epoch-042",
            context_type="mutation_proposal",
            payload=self._payload(),
        )
        assert result.accepted is True
        assert result.entry.epoch_id == "epoch-042"
        assert result.entry.context_type == "mutation_proposal"

    def test_T9_01_09_append_rejects_invalid_context_type(self, tmp_path):
        """append() must reject unknown context_type values."""
        ledger = self._make_ledger(tmp_path)
        result = ledger.append(
            epoch_id="epoch-001",
            context_type="totally_invalid_type",
            payload=self._payload(),
        )
        assert result.accepted is False
        assert result.rejection_reason is not None
        assert "invalid_context_type" in result.rejection_reason

    def test_T9_01_10_append_rejects_empty_payload(self, tmp_path):
        """append() must reject empty payloads."""
        ledger = self._make_ledger(tmp_path)
        result = ledger.append(
            epoch_id="epoch-001",
            context_type="mutation_proposal",
            payload={},
        )
        assert result.accepted is False

    def test_T9_01_11_entry_has_64_char_context_digest(self, tmp_path):
        """Each accepted entry must have a valid SHA-256 hex context_digest."""
        ledger = self._make_ledger(tmp_path)
        result = ledger.append(
            epoch_id="epoch-001",
            context_type="fitness_signal",
            payload=self._payload(signal="plateau"),
        )
        assert len(result.entry.context_digest) == 64
        assert all(c in "0123456789abcdef" for c in result.entry.context_digest)

    def test_T9_01_12_entry_has_64_char_hmac_signature(self, tmp_path):
        """Each accepted entry must have a valid HMAC-SHA256 signature."""
        ledger = self._make_ledger(tmp_path)
        result = ledger.append(
            epoch_id="epoch-001",
            context_type="mutation_proposal",
            payload=self._payload(),
        )
        assert len(result.entry.hmac_signature) == 64
        assert all(c in "0123456789abcdef" for c in result.entry.hmac_signature)

    def test_T9_01_13_chain_hashes_link_consecutive_entries(self, tmp_path):
        """Each entry's chain_hash must differ from the previous."""
        ledger = self._make_ledger(tmp_path)
        r1 = ledger.append(epoch_id="e1", context_type="mutation_proposal", payload=self._payload())
        r2 = ledger.append(epoch_id="e2", context_type="fitness_signal",    payload=self._payload())
        assert r1.entry.chain_hash != r2.entry.chain_hash

    def test_T9_01_14_verify_chain_passes_on_intact_ledger(self, tmp_path):
        """verify_chain() must return (True, []) for an unmodified ledger."""
        ledger = self._make_ledger(tmp_path)
        for i in range(5):
            ledger.append(
                epoch_id=f"epoch-{i:03d}",
                context_type="mutation_proposal",
                payload=self._payload(idx=i),
            )
        ok, failures = ledger.verify_chain()
        assert ok is True
        assert failures == []

    def test_T9_01_15_verify_chain_detects_tampering(self, tmp_path):
        """verify_chain() must return (False, [reason]) when an entry is tampered."""
        from runtime.memory.soulbound_ledger import SoulboundLedger
        ledger_path = tmp_path / "ledger.json"
        ledger = SoulboundLedger(
            ledger_path=ledger_path,
            audit_writer=_no_op_audit,
            key_override=_TEST_KEY_BYTES,
        )
        ledger.append(epoch_id="e1", context_type="mutation_proposal", payload=self._payload())
        ledger.append(epoch_id="e2", context_type="fitness_signal",    payload=self._payload())

        # Tamper: corrupt the stored chain_hash of entry 1
        raw = json.loads(ledger_path.read_text())
        raw["entries"][0]["payload"]["chain_hash"] = "0" * 64
        ledger_path.write_text(json.dumps(raw))

        # Re-open with a fresh instance to force reload
        ledger2 = SoulboundLedger(
            ledger_path=ledger_path,
            audit_writer=_no_op_audit,
            key_override=_TEST_KEY_BYTES,
        )
        ok, failures = ledger2.verify_chain()
        assert ok is False
        assert len(failures) >= 1

    def test_T9_01_16_entry_count_increments_on_each_accepted_append(self, tmp_path):
        """entry_count() must increment by 1 for each accepted append."""
        ledger = self._make_ledger(tmp_path)
        assert ledger.entry_count() == 0
        for i in range(4):
            ledger.append(
                epoch_id=f"e{i}", context_type="mutation_proposal",
                payload=self._payload(idx=i),
            )
        assert ledger.entry_count() == 4

    def test_T9_01_17_key_absent_raises_soulbound_key_error(self, tmp_path, monkeypatch):
        """append() must raise SoulboundKeyError when env key is absent and no override."""
        from runtime.memory.soulbound_ledger import SoulboundLedger
        from runtime.memory.soulbound_key import SoulboundKeyError
        monkeypatch.delenv("ADAAD_SOULBOUND_KEY", raising=False)
        ledger = SoulboundLedger(
            ledger_path=tmp_path / "ledger_nokey.json",
            audit_writer=_no_op_audit,
            key_override=None,   # Force real env lookup
        )
        with pytest.raises(SoulboundKeyError):
            ledger.append(
                epoch_id="e1",
                context_type="mutation_proposal",
                payload=self._payload(),
            )


# ════════════════════════════════════════════════════════════════════════════
# ContextFilterChain — T9-01-18..25
# ════════════════════════════════════════════════════════════════════════════

class TestContextFilterChain:

    def _chain(self):
        from runtime.memory.context_filter_chain import ContextFilterChain
        return ContextFilterChain()

    def _payload(self, **kw):
        return {"epoch_id": "epoch-042", "context_hash": "abc123", **kw}

    def test_T9_01_18_valid_payload_passes_all_builtin_filters(self):
        """A well-formed payload must pass all built-in filters."""
        chain = self._chain()
        result = chain.evaluate(
            payload=self._payload(),
            context_type="mutation_proposal",
        )
        assert result.accepted is True
        assert result.rejection_reason is None

    def test_T9_01_19_missing_epoch_id_rejected_by_builtin_filter(self):
        """Payload without epoch_id must be rejected."""
        chain = self._chain()
        result = chain.evaluate(
            payload={"context_hash": "abc"},
            context_type="mutation_proposal",
        )
        assert result.accepted is False
        assert "epoch_id" in (result.rejection_reason or "")

    def test_T9_01_20_oversized_payload_rejected(self):
        """Payload exceeding MAX_PAYLOAD_BYTES must be rejected."""
        from runtime.memory.context_filter_chain import MAX_PAYLOAD_BYTES
        chain = self._chain()
        big_payload = {"epoch_id": "e1", "data": "x" * (MAX_PAYLOAD_BYTES + 1)}
        result = chain.evaluate(payload=big_payload, context_type="mutation_proposal")
        assert result.accepted is False
        assert "size" in (result.rejection_reason or "")

    def test_T9_01_21_private_key_pattern_rejected(self):
        """Payload containing a private key pattern must be rejected."""
        chain = self._chain()
        payload = self._payload(secret_key="sk-abc123def456ghi789jkl000mno111")
        result = chain.evaluate(payload=payload, context_type="mutation_proposal")
        assert result.accepted is False
        assert "private_key" in (result.rejection_reason or "")

    def test_T9_01_22_invalid_context_type_rejected_by_allowlist(self):
        """Unknown context_type must be rejected by the allowlist filter."""
        chain = self._chain()
        result = chain.evaluate(
            payload=self._payload(),
            context_type="not_a_valid_type",
        )
        assert result.accepted is False
        assert "allowlist" in (result.rejection_reason or "")

    def test_T9_01_23_custom_filter_runs_after_builtins(self):
        """A registered custom filter must run after all built-in filters pass."""
        from runtime.memory.context_filter_chain import FilterResult
        chain = self._chain()
        calls = []

        def my_filter(payload, context_type):
            calls.append((payload, context_type))
            return FilterResult.accept("my_filter")

        chain.register(my_filter)
        result = chain.evaluate(payload=self._payload(), context_type="mutation_proposal")
        assert result.accepted is True
        assert len(calls) == 1

    def test_T9_01_24_builtin_rejection_halts_chain_before_custom_filter(self):
        """Custom filter must NOT be called when a built-in filter rejects."""
        from runtime.memory.context_filter_chain import FilterResult
        chain = self._chain()
        custom_calls = []

        def custom_filter(payload, context_type):
            custom_calls.append(True)
            return FilterResult.accept("custom")

        chain.register(custom_filter)
        # Missing epoch_id → built-in rejects immediately
        result = chain.evaluate(payload={"data": "x"}, context_type="mutation_proposal")
        assert result.accepted is False
        assert len(custom_calls) == 0, "custom filter must not be called after built-in rejection"

    def test_T9_01_25_filter_count_reflects_builtins_plus_custom(self):
        """filter_count must equal len(built-ins) + len(custom) registered."""
        from runtime.memory.context_filter_chain import _BUILTIN_FILTERS
        chain = self._chain()
        builtin_count = len(_BUILTIN_FILTERS)
        assert chain.filter_count == builtin_count
        assert chain.custom_filter_count == 0

        from runtime.memory.context_filter_chain import FilterResult
        chain.register(lambda p, c: FilterResult.accept("f1"))
        chain.register(lambda p, c: FilterResult.accept("f2"))
        assert chain.filter_count == builtin_count + 2
        assert chain.custom_filter_count == 2
