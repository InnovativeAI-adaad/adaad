# SPDX-License-Identifier: Apache-2.0
"""T100-ARS-01..30 — Phase 100 INNOV-15 Agent Reputation Staking acceptance tests.

Invariants under test:
  STAKE-0        balance must be >= MIN_STAKE before stake() commits
  STAKE-CAP-0    staked amount capped at MAX_STAKE_FRACTION (20%) of pre-stake balance
  STAKE-BURN-0   resolve(passed=False) burns 100% of staked_amount; no return
  STAKE-DETERM-0 stake_digest = full sha256(agent_id:mutation_id:epoch_id:staked_amount)
  STAKE-PERSIST-0 _persist uses Path.open("a"); wallets use sort_keys=True
"""
from __future__ import annotations
import json, dataclasses
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from runtime.innovations30.reputation_staking import (
    ReputationStakingLedger, StakeRecord,
    InsufficientStakeError, StakeAlreadyResolvedError,
    MIN_STAKE, MAX_STAKE_FRACTION, GOVERNANCE_PASS_MULTIPLIER,
    _compute_stake_digest,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def ledger(tmp_path):
    L = ReputationStakingLedger(
        ledger_path=tmp_path / "stakes.jsonl",
        wallet_path=tmp_path / "wallets.json",
    )
    L.register_agent("agent-A", initial_balance=100.0)
    L.register_agent("agent-B", initial_balance=50.0)
    return L

# ─────────────────────────────────────────────────────────────────────────────
# STAKE-0 — Balance gate (T100-ARS-01..06)
# ─────────────────────────────────────────────────────────────────────────────

def test_ars_01_stake_deducts_from_balance(ledger):
    """STAKE-0: staking reduces agent balance by staked_amount."""
    r = ledger.stake("agent-A", "mut-001", "ep-1", amount=10.0)
    assert ledger.balance("agent-A") == pytest.approx(90.0)
    assert r.staked_amount == pytest.approx(10.0)

def test_ars_02_stake_below_min_raises(tmp_path):
    """STAKE-0: agent with zero balance raises InsufficientStakeError."""
    L = ReputationStakingLedger(tmp_path/"s.jsonl", tmp_path/"w.json")
    with pytest.raises(InsufficientStakeError, match="STAKE-0"):
        L.stake("no-such-agent", "mut-X", "ep-1")

def test_ars_03_stake_exactly_min_stake_succeeds(tmp_path):
    """STAKE-0: agent with exactly MIN_STAKE balance can stake."""
    L = ReputationStakingLedger(tmp_path/"s.jsonl", tmp_path/"w.json")
    L.register_agent("agent-C", initial_balance=MIN_STAKE)
    r = L.stake("agent-C", "mut-Y", "ep-1", amount=MIN_STAKE)
    assert r.staked_amount == pytest.approx(MIN_STAKE)

def test_ars_04_stake_records_pre_stake_balance(ledger):
    """STAKE-0: StakeRecord.pre_stake_balance reflects balance before deduction."""
    r = ledger.stake("agent-A", "mut-001", "ep-1", amount=10.0)
    assert r.pre_stake_balance == pytest.approx(100.0)

def test_ars_05_stake_outcome_initially_pending(ledger):
    """STAKE-0: freshly staked record has outcome='pending'."""
    r = ledger.stake("agent-A", "mut-001", "ep-1")
    assert r.outcome == "pending"

def test_ars_06_balance_of_unregistered_agent_is_zero(ledger):
    """STAKE-0: unregistered agent returns 0.0 balance."""
    assert ledger.balance("no-such") == 0.0

# ─────────────────────────────────────────────────────────────────────────────
# STAKE-CAP-0 — Stake cap enforcement (T100-ARS-07..10)
# ─────────────────────────────────────────────────────────────────────────────

def test_ars_07_stake_capped_at_max_fraction(ledger):
    """STAKE-CAP-0: requesting 50% stake is capped to MAX_STAKE_FRACTION (20%)."""
    r = ledger.stake("agent-A", "mut-001", "ep-1", amount=50.0)
    assert r.staked_amount <= 100.0 * MAX_STAKE_FRACTION + 1e-9

def test_ars_08_default_stake_is_five_percent(ledger):
    """STAKE-CAP-0: default stake (no amount) is ~5% of balance."""
    r = ledger.stake("agent-A", "mut-001", "ep-1")
    assert r.staked_amount == pytest.approx(max(MIN_STAKE, 100.0 * 0.05))

def test_ars_09_stake_cap_absolute_max(tmp_path):
    """STAKE-CAP-0: large balance still capped at MAX_STAKE_FRACTION."""
    L = ReputationStakingLedger(tmp_path/"s.jsonl", tmp_path/"w.json")
    L.register_agent("rich", initial_balance=10_000.0)
    r = L.stake("rich", "mut-001", "ep-1", amount=5000.0)
    assert r.staked_amount <= 10_000.0 * MAX_STAKE_FRACTION + 1e-9

def test_ars_10_stake_cap_never_exceeds_balance(tmp_path):
    """STAKE-CAP-0: stake never exceeds current balance."""
    L = ReputationStakingLedger(tmp_path/"s.jsonl", tmp_path/"w.json")
    L.register_agent("low", initial_balance=2.0)
    r = L.stake("low", "mut-001", "ep-1", amount=100.0)
    assert r.staked_amount <= 2.0

# ─────────────────────────────────────────────────────────────────────────────
# STAKE-BURN-0 — Burn on failure (T100-ARS-11..16)
# ─────────────────────────────────────────────────────────────────────────────

def test_ars_11_failed_stake_burns_amount(ledger):
    """STAKE-BURN-0: failed proposal — staked_amount is NOT returned."""
    ledger.stake("agent-A", "mut-001", "ep-1", amount=10.0)
    balance_before_resolve = ledger.balance("agent-A")
    ledger.resolve("mut-001", passed=False)
    assert ledger.balance("agent-A") == pytest.approx(balance_before_resolve)

def test_ars_12_failed_outcome_is_failed(ledger):
    """STAKE-BURN-0: resolve(passed=False) sets outcome='failed'."""
    ledger.stake("agent-A", "mut-001", "ep-1", amount=5.0)
    r = ledger.resolve("mut-001", passed=False)
    assert r.outcome == "failed"

def test_ars_13_pass_with_fitness_gives_bonus(ledger):
    """STAKE-BURN-0: pass + fitness_improved awards stake * GOVERNANCE_PASS_MULTIPLIER."""
    ledger.stake("agent-A", "mut-001", "ep-1", amount=10.0)
    pre = ledger.balance("agent-A")
    r = ledger.resolve("mut-001", passed=True, fitness_improved=True)
    expected = pre + round(10.0 * GOVERNANCE_PASS_MULTIPLIER, 2)
    assert r.final_balance == pytest.approx(expected)

def test_ars_14_pass_without_fitness_returns_stake(ledger):
    """STAKE-BURN-0: pass without fitness improvement returns stake at face value."""
    ledger.stake("agent-A", "mut-001", "ep-1", amount=10.0)
    pre = ledger.balance("agent-A")
    r = ledger.resolve("mut-001", passed=True, fitness_improved=False)
    assert r.final_balance == pytest.approx(pre + 10.0)

def test_ars_15_resolve_already_resolved_raises(ledger):
    """STAKE-BURN-0: resolving an already-resolved record raises StakeAlreadyResolvedError."""
    ledger.stake("agent-A", "mut-001", "ep-1")
    ledger.resolve("mut-001", passed=True)
    with pytest.raises(StakeAlreadyResolvedError):
        ledger.resolve("mut-001", passed=False)

def test_ars_16_resolve_unknown_mutation_returns_none(ledger):
    """STAKE-BURN-0: resolving a non-existent mutation_id returns None."""
    result = ledger.resolve("no-such-mut", passed=True)
    assert result is None

# ─────────────────────────────────────────────────────────────────────────────
# STAKE-DETERM-0 — Digest determinism (T100-ARS-17..22)
# ─────────────────────────────────────────────────────────────────────────────

def test_ars_17_same_inputs_same_digest(ledger):
    """STAKE-DETERM-0: identical field values produce identical stake_digest."""
    r1 = StakeRecord("A","mut-1","ep-1",10.0,100.0)
    r2 = StakeRecord("A","mut-1","ep-1",10.0,100.0)
    assert r1.stake_digest == r2.stake_digest

def test_ars_18_digest_prefix_sha256(ledger):
    """STAKE-DETERM-0: stake_digest always begins with 'sha256:'."""
    r = ledger.stake("agent-A", "mut-001", "ep-1", amount=10.0)
    assert r.stake_digest.startswith("sha256:")

def test_ars_19_digest_full_length(ledger):
    """STAKE-DETERM-0: digest is full sha256 (64 hex chars after 'sha256:')."""
    r = ledger.stake("agent-A", "mut-001", "ep-1", amount=10.0)
    assert len(r.stake_digest) == len("sha256:") + 64

def test_ars_20_different_mutation_different_digest():
    """STAKE-DETERM-0: different mutation_id produces different digest."""
    r1 = StakeRecord("A","mut-1","ep-1",10.0,100.0)
    r2 = StakeRecord("A","mut-2","ep-1",10.0,100.0)
    assert r1.stake_digest != r2.stake_digest

def test_ars_21_different_amount_different_digest():
    """STAKE-DETERM-0: different staked_amount produces different digest."""
    r1 = StakeRecord("A","mut-1","ep-1",10.0,100.0)
    r2 = StakeRecord("A","mut-1","ep-1",11.0,100.0)
    assert r1.stake_digest != r2.stake_digest

def test_ars_22_compute_digest_helper_idempotent():
    """STAKE-DETERM-0: _compute_stake_digest is pure — same args, same result."""
    d1 = _compute_stake_digest("A","mut-1","ep-1",10.0)
    d2 = _compute_stake_digest("A","mut-1","ep-1",10.0)
    assert d1 == d2

# ─────────────────────────────────────────────────────────────────────────────
# STAKE-PERSIST-0 — Path.open append (T100-ARS-23..26)
# ─────────────────────────────────────────────────────────────────────────────

def test_ars_23_persist_uses_path_open(ledger):
    """STAKE-PERSIST-0: _persist uses Path.open not builtins.open."""
    with patch("runtime.innovations30.reputation_staking.Path.open",
               mock_open()) as mocked:
        r = StakeRecord("A","mut-x","ep-1",5.0,100.0)
        ledger._persist(r)
        mocked.assert_called()

def test_ars_24_ledger_appends_not_overwrites(ledger):
    """STAKE-PERSIST-0: multiple stakes append to ledger; no overwrite."""
    ledger.stake("agent-A", "mut-001", "ep-1", amount=5.0)
    ledger.stake("agent-B", "mut-002", "ep-1", amount=5.0)
    lines = ledger.ledger_path.read_text().splitlines()
    assert len(lines) >= 2

def test_ars_25_wallets_json_is_sorted(ledger):
    """STAKE-PERSIST-0: wallet file uses sort_keys=True for determinism."""
    raw = ledger.wallet_path.read_text()
    data = json.loads(raw)
    keys = list(data.keys())
    assert keys == sorted(keys)

def test_ars_26_ledger_records_sort_keys(ledger):
    """STAKE-PERSIST-0: each ledger record serialized with sort_keys=True."""
    ledger.stake("agent-A","mut-001","ep-1",amount=5.0)
    line = ledger.ledger_path.read_text().strip().splitlines()[-1]
    parsed = json.loads(line)
    keys = list(parsed.keys())
    assert keys == sorted(keys)

# ─────────────────────────────────────────────────────────────────────────────
# Integration and edge cases (T100-ARS-27..30)
# ─────────────────────────────────────────────────────────────────────────────

def test_ars_27_win_rate_empty_history(ledger):
    """Integration: agent with no resolved stakes returns win_rate=1.0."""
    assert ledger.agent_win_rate("agent-A") == pytest.approx(1.0)

def test_ars_28_win_rate_all_passed(ledger):
    """Integration: 2/2 passed → win_rate=1.0."""
    ledger.stake("agent-A","mut-001","ep-1",amount=5.0)
    ledger.stake("agent-A","mut-002","ep-1",amount=5.0)
    ledger.resolve("mut-001", passed=True)
    ledger.resolve("mut-002", passed=True)
    assert ledger.agent_win_rate("agent-A") == pytest.approx(1.0)

def test_ars_29_win_rate_half_passed(ledger):
    """Integration: 1/2 passed → win_rate=0.5."""
    ledger.stake("agent-A","mut-001","ep-1",amount=5.0)
    ledger.stake("agent-A","mut-002","ep-1",amount=5.0)
    ledger.resolve("mut-001", passed=True)
    ledger.resolve("mut-002", passed=False)
    assert ledger.agent_win_rate("agent-A") == pytest.approx(0.5)

def test_ars_30_load_fail_open_on_corrupt_ledger(tmp_path):
    """Integration (fail-open): corrupt ledger lines silently skipped on reload."""
    lp = tmp_path / "stakes.jsonl"
    wp = tmp_path / "wallets.json"
    wp.write_text(json.dumps({"agent-A": 100.0}))
    lp.write_text("NOT_JSON\n{\"mutation_id\":\"mut-1\",\"agent_id\":\"agent-A\",\"epoch_id\":\"ep-1\",\"staked_amount\":5.0,\"pre_stake_balance\":100.0,\"outcome\":\"pending\",\"final_balance\":0.0,\"stake_digest\":\"sha256:abc\"}\n")
    L = ReputationStakingLedger(lp, wp)
    assert L.balance("agent-A") == pytest.approx(100.0)
    assert "mut-1" in L._stakes
