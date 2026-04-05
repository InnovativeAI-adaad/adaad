# SPDX-License-Identifier: Apache-2.0
"""Phase 108 — INNOV-23 Constitutional Epoch Sentinel (CES) acceptance tests.

T108-CES-01 … T108-CES-30  — 30/30 must pass.
"""
from __future__ import annotations

import hashlib
import json
import pytest

from runtime.innovations30.constitutional_epoch_sentinel import (
    CESViolation,
    CES_VERSION,
    ConstitutionalEpochSentinel,
    SentinelAdvisory,
    SentinelChannel,
    CES_INV_VERSION, CES_INV_WATCH, CES_INV_THRESH, CES_INV_EMIT,
    CES_INV_PERSIST, CES_INV_CHAIN, CES_INV_GATE, CES_INV_DETERM,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_ces(tmp_path):
    return ConstitutionalEpochSentinel(state_path=tmp_path / "sentinel.jsonl")


@pytest.fixture
def ch_low():
    """A channel with warning=0.7, violation=0.9."""
    return SentinelChannel("debt_score", warning_threshold=0.70, violation_threshold=0.90)


@pytest.fixture
def ch_high():
    """A channel with warning=0.8, violation=1.0."""
    return SentinelChannel("health_delta", warning_threshold=0.80, violation_threshold=1.00)


# ── T108-CES-01: CES_VERSION non-empty (CES-0) ───────────────────────────────

def test_ces_01_version_non_empty():
    """CES-0: CES_VERSION must be present and non-empty."""
    assert CES_VERSION
    assert isinstance(CES_VERSION, str)


# ── T108-CES-02: invariant codes exported (CES-0) ────────────────────────────

def test_ces_02_invariant_codes_exported():
    """CES-0: all eight invariant code constants must be non-empty strings."""
    for code in [
        CES_INV_VERSION, CES_INV_WATCH, CES_INV_THRESH, CES_INV_EMIT,
        CES_INV_PERSIST, CES_INV_CHAIN, CES_INV_GATE, CES_INV_DETERM,
    ]:
        assert isinstance(code, str) and code


# ── T108-CES-03: register_channel accepts valid channel (CES-THRESH-0) ───────

def test_ces_03_register_valid_channel(tmp_ces, ch_low):
    """CES-THRESH-0: valid channel registers without raising."""
    tmp_ces.register_channel(ch_low)
    status = tmp_ces.sentinel_status()
    assert status["registered_channels"] == 1


# ── T108-CES-04: warning >= violation raises at registration (CES-THRESH-0) ──

def test_ces_04_invalid_threshold_raises(tmp_ces):
    """CES-THRESH-0: warning_threshold >= violation_threshold raises CESViolation."""
    bad = SentinelChannel("bad_ch", warning_threshold=0.9, violation_threshold=0.9)
    with pytest.raises(CESViolation, match=CES_INV_THRESH):
        tmp_ces.register_channel(bad)


# ── T108-CES-05: warning > violation raises at registration (CES-THRESH-0) ───

def test_ces_05_warning_above_violation_raises(tmp_ces):
    """CES-THRESH-0: warning_threshold > violation_threshold raises CESViolation."""
    bad = SentinelChannel("bad_ch", warning_threshold=0.95, violation_threshold=0.80)
    with pytest.raises(CESViolation, match=CES_INV_THRESH):
        tmp_ces.register_channel(bad)


# ── T108-CES-06: blank epoch_id raises (CES-GATE-0) ─────────────────────────

def test_ces_06_blank_epoch_id_raises(tmp_ces, ch_low):
    """CES-GATE-0: blank epoch_id is a constitutional violation."""
    tmp_ces.register_channel(ch_low)
    with pytest.raises(CESViolation, match=CES_INV_GATE):
        tmp_ces.tick("", {"debt_score": 0.75})


# ── T108-CES-07: whitespace epoch_id raises (CES-GATE-0) ─────────────────────

def test_ces_07_whitespace_epoch_id_raises(tmp_ces, ch_low):
    """CES-GATE-0: whitespace-only epoch_id raises CESViolation."""
    tmp_ces.register_channel(ch_low)
    with pytest.raises(CESViolation, match=CES_INV_GATE):
        tmp_ces.tick("   ", {"debt_score": 0.75})


# ── T108-CES-08: metric below warning → no advisory (CES-EMIT-0) ─────────────

def test_ces_08_below_warning_no_advisory(tmp_ces, ch_low):
    """CES-EMIT-0: metric below warning_threshold produces no advisory."""
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.50})
    assert emitted == []
    assert tmp_ces.sentinel_status()["total_advisories"] == 0


# ── T108-CES-09: metric at warning → advisory emitted (CES-EMIT-0) ───────────

def test_ces_09_at_warning_emits_advisory(tmp_ces, ch_low):
    """CES-EMIT-0: metric == warning_threshold triggers advisory emission."""
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.70})
    assert len(emitted) == 1
    assert emitted[0].channel_name == "debt_score"


# ── T108-CES-10: metric above warning → advisory emitted (CES-EMIT-0) ────────

def test_ces_10_above_warning_emits_advisory(tmp_ces, ch_low):
    """CES-EMIT-0: metric above warning_threshold triggers advisory."""
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.85})
    assert len(emitted) == 1
    assert emitted[0].metric_value == 0.85


# ── T108-CES-11: margin_remaining computed correctly ─────────────────────────

def test_ces_11_margin_remaining_correct(tmp_ces, ch_low):
    """Advisory margin_remaining = violation_threshold - metric_value."""
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.80})
    assert len(emitted) == 1
    assert abs(emitted[0].margin_remaining - 0.10) < 1e-5


# ── T108-CES-12: all channels evaluated per tick (CES-WATCH-0) ───────────────

def test_ces_12_all_channels_evaluated(tmp_ces, ch_low, ch_high):
    """CES-WATCH-0: both channels evaluated; both emit when in corridor."""
    tmp_ces.register_channel(ch_low)
    tmp_ces.register_channel(ch_high)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.75, "health_delta": 0.85})
    names = {a.channel_name for a in emitted}
    assert names == {"debt_score", "health_delta"}


# ── T108-CES-13: channel not in metrics uses current_value (CES-WATCH-0) ─────

def test_ces_13_missing_metric_uses_current_value(tmp_ces, ch_low):
    """CES-WATCH-0: channel with no supplied metric uses channel.current_value."""
    ch_low.current_value = 0.75  # pre-set above warning
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {})  # no metrics supplied
    assert len(emitted) == 1


# ── T108-CES-14: advisory_digest deterministic (CES-DETERM-0) ────────────────

def test_ces_14_advisory_digest_deterministic(tmp_ces, ch_low):
    """CES-DETERM-0: advisory_digest is reproducible from canonical fields."""
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.75})
    advisory = emitted[0]
    # Recompute manually
    payload = (
        f"{advisory.epoch_id}:{advisory.channel_name}"
        f":{repr(advisory.metric_value)}"
        f":{advisory.prev_digest}"
    )
    expected = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
    assert advisory.advisory_digest == expected


# ── T108-CES-15: two advisories chain-link correctly (CES-CHAIN-0) ───────────

def test_ces_15_chain_links_across_advisories(tmp_ces, ch_low):
    """CES-CHAIN-0: second advisory's prev_digest == first advisory's digest."""
    tmp_ces.register_channel(ch_low)
    e1 = tmp_ces.tick("ep-01", {"debt_score": 0.72})
    e2 = tmp_ces.tick("ep-02", {"debt_score": 0.74})
    assert e1 and e2
    assert e2[0].prev_digest == e1[0].advisory_digest


# ── T108-CES-16: persist appends to JSONL (CES-PERSIST-0) ────────────────────

def test_ces_16_persist_appends_jsonl(tmp_path, ch_low):
    """CES-PERSIST-0: each advisory appends exactly one JSONL line."""
    ledger = tmp_path / "s.jsonl"
    ces = ConstitutionalEpochSentinel(state_path=ledger)
    ces.register_channel(ch_low)
    ces.tick("ep-01", {"debt_score": 0.72})
    ces.tick("ep-02", {"debt_score": 0.74})
    lines = [l for l in ledger.read_text().splitlines() if l.strip()]
    assert len(lines) == 2


# ── T108-CES-17: ledger uses append mode — no overwrite (CES-PERSIST-0) ──────

def test_ces_17_ledger_no_overwrite(tmp_path, ch_low):
    """CES-PERSIST-0: pre-existing ledger content is preserved."""
    ledger = tmp_path / "s.jsonl"
    sentinel_line = '{"sentinel": true}\n'
    ledger.write_text(sentinel_line)
    ces = ConstitutionalEpochSentinel(state_path=ledger)
    ces.register_channel(ch_low)
    ces.tick("ep-01", {"debt_score": 0.75})
    assert ledger.read_text().startswith(sentinel_line)


# ── T108-CES-18: chain integrity valid after single tick (CES-CHAIN-0) ───────

def test_ces_18_chain_valid_single_tick(tmp_path, ch_low):
    """CES-CHAIN-0: verify_chain() passes after one advisory."""
    ledger = tmp_path / "s.jsonl"
    ces = ConstitutionalEpochSentinel(state_path=ledger)
    ces.register_channel(ch_low)
    ces.tick("ep-01", {"debt_score": 0.75})
    ok, msg = ces.verify_chain()
    assert ok, msg


# ── T108-CES-19: chain valid across multiple ticks (CES-CHAIN-0) ─────────────

def test_ces_19_chain_valid_multiple_ticks(tmp_path, ch_low):
    """CES-CHAIN-0: chain verifies correctly across three advisory events."""
    ledger = tmp_path / "s.jsonl"
    ces = ConstitutionalEpochSentinel(state_path=ledger)
    ces.register_channel(ch_low)
    for i, v in enumerate([0.72, 0.75, 0.80], start=1):
        ces.tick(f"ep-{i:02d}", {"debt_score": v})
    ok, msg = ces.verify_chain()
    assert ok, msg


# ── T108-CES-20: tampered ledger fails chain verify (CES-CHAIN-0) ────────────

def test_ces_20_tampered_ledger_fails_chain(tmp_path, ch_low):
    """CES-CHAIN-0: a tampered ledger entry causes verify_chain to fail."""
    ledger = tmp_path / "s.jsonl"
    ces = ConstitutionalEpochSentinel(state_path=ledger)
    ces.register_channel(ch_low)
    ces.tick("ep-01", {"debt_score": 0.75})
    content = ledger.read_text()
    d = json.loads(content.strip())
    d["metric_value"] = 0.99   # tamper post-hoc
    ledger.write_text(json.dumps(d) + "\n")
    ok, _ = ces.verify_chain()
    assert not ok


# ── T108-CES-21: empty ledger chain verify passes (CES-CHAIN-0) ──────────────

def test_ces_21_empty_ledger_chain_valid(tmp_path):
    """CES-CHAIN-0: an empty ledger trivially passes chain verification."""
    ces = ConstitutionalEpochSentinel(state_path=tmp_path / "s.jsonl")
    ok, msg = ces.verify_chain()
    assert ok
    assert "trivially" in msg


# ── T108-CES-22: advisories reload from ledger (CES-PERSIST-0) ───────────────

def test_ces_22_advisories_reload_on_reinit(tmp_path, ch_low):
    """CES-PERSIST-0: advisory history is restored from ledger on reinit."""
    ledger = tmp_path / "s.jsonl"
    ces1 = ConstitutionalEpochSentinel(state_path=ledger)
    ces1.register_channel(ch_low)
    ces1.tick("ep-01", {"debt_score": 0.75})

    ces2 = ConstitutionalEpochSentinel(state_path=ledger)
    assert ces2.sentinel_status()["total_advisories"] == 1


# ── T108-CES-23: acknowledge removes from pending ────────────────────────────

def test_ces_23_acknowledge_clears_pending(tmp_ces, ch_low):
    """Acknowledging an advisory removes it from pending_advisories."""
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.75})
    digest = emitted[0].advisory_digest
    assert len(tmp_ces.pending_advisories()) == 1
    result = tmp_ces.acknowledge(digest)
    assert result is True
    assert len(tmp_ces.pending_advisories()) == 0


# ── T108-CES-24: acknowledge unknown digest returns False ────────────────────

def test_ces_24_acknowledge_unknown_returns_false(tmp_ces):
    """acknowledge() returns False for an unknown digest."""
    result = tmp_ces.acknowledge("sha256:nonexistent")
    assert result is False


# ── T108-CES-25: sentinel_status reports corridor channels ───────────────────

def test_ces_25_sentinel_status_corridor_channels(tmp_ces, ch_low, ch_high):
    """sentinel_status lists channels currently in warning corridor."""
    tmp_ces.register_channel(ch_low)
    tmp_ces.register_channel(ch_high)
    tmp_ces.tick("ep-01", {"debt_score": 0.75, "health_delta": 0.50})
    status = tmp_ces.sentinel_status()
    assert "debt_score" in status["channels_in_corridor"]
    assert "health_delta" not in status["channels_in_corridor"]


# ── T108-CES-26: sentinel_status tracks last_tick_epoch ──────────────────────

def test_ces_26_status_tracks_last_tick_epoch(tmp_ces, ch_low):
    """sentinel_status.last_tick_epoch reflects most recent tick call."""
    tmp_ces.register_channel(ch_low)
    tmp_ces.tick("ep-42", {"debt_score": 0.50})
    assert tmp_ces.sentinel_status()["last_tick_epoch"] == "ep-42"


# ── T108-CES-27: multiple channels, only in-corridor emit (CES-EMIT-0) ───────

def test_ces_27_only_corridor_channels_emit(tmp_ces, ch_low, ch_high):
    """CES-EMIT-0: only channels in warning corridor produce advisories."""
    tmp_ces.register_channel(ch_low)
    tmp_ces.register_channel(ch_high)
    # debt_score in corridor, health_delta below warning
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.75, "health_delta": 0.60})
    assert len(emitted) == 1
    assert emitted[0].channel_name == "debt_score"


# ── T108-CES-28: zero registered channels → no advisory, no error ────────────

def test_ces_28_no_channels_no_advisory(tmp_ces):
    """CES-WATCH-0: tick with no registered channels completes without error."""
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.99})
    assert emitted == []


# ── T108-CES-29: advisory fields match channel config ────────────────────────

def test_ces_29_advisory_fields_match_channel(tmp_ces, ch_low):
    """Advisory carries correct warning/violation thresholds from channel."""
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.75})
    adv = emitted[0]
    assert adv.warning_threshold == ch_low.warning_threshold
    assert adv.violation_threshold == ch_low.violation_threshold
    assert adv.epoch_id == "ep-01"


# ── T108-CES-30: SentinelAdvisory structure is complete ──────────────────────

def test_ces_30_advisory_structure_complete(tmp_ces, ch_low):
    """SentinelAdvisory carries all required fields for HUMAN-0 review."""
    tmp_ces.register_channel(ch_low)
    emitted = tmp_ces.tick("ep-01", {"debt_score": 0.82})
    adv = emitted[0]
    assert isinstance(adv, SentinelAdvisory)
    assert adv.advisory_digest.startswith("sha256:")
    assert adv.prev_digest == "genesis"
    assert adv.margin_remaining > 0
    assert not adv.acknowledged
