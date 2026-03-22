# SPDX-License-Identifier: Apache-2.0
"""Innovation #15 — Agent Reputation Staking.
Agents stake credits on proposals. Failed proposals burn stake.
Converts hollow proposals into costly commitments.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIN_STAKE: float = 1.0
MAX_STAKE_FRACTION: float = 0.20  # agent can stake at most 20% of balance
GOVERNANCE_PASS_MULTIPLIER: float = 1.5
GOVERNANCE_FAIL_BURN_RATE: float = 1.0  # 100% of stake burned on fail

@dataclass
class StakeRecord:
    agent_id: str
    mutation_id: str
    epoch_id: str
    staked_amount: float
    pre_stake_balance: float
    outcome: str = "pending"   # pending | passed | failed
    final_balance: float = 0.0
    stake_digest: str = ""

    def __post_init__(self):
        if not self.stake_digest:
            payload = f"{self.agent_id}:{self.mutation_id}:{self.staked_amount}"
            self.stake_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


class ReputationStakingLedger:
    """Manages agent staking on mutation proposals."""

    def __init__(self, ledger_path: Path = Path("data/reputation_stakes.jsonl"),
                 wallet_path: Path = Path("data/agent_wallets.json")):
        self.ledger_path = Path(ledger_path)
        self.wallet_path = Path(wallet_path)
        self._wallets: dict[str, float] = {}
        self._stakes: dict[str, StakeRecord] = {}
        self._load()

    def register_agent(self, agent_id: str, initial_balance: float = 100.0) -> None:
        if agent_id not in self._wallets:
            self._wallets[agent_id] = initial_balance
            self._save_wallets()

    def stake(self, agent_id: str, mutation_id: str, epoch_id: str,
               amount: float | None = None) -> StakeRecord:
        """Agent stakes on their proposal."""
        balance = self._wallets.get(agent_id, 0.0)
        if amount is None:
            amount = max(MIN_STAKE, balance * 0.05)  # default: 5% of balance
        amount = min(amount, balance * MAX_STAKE_FRACTION)
        amount = max(MIN_STAKE, min(amount, balance))

        self._wallets[agent_id] = balance - amount
        record = StakeRecord(agent_id=agent_id, mutation_id=mutation_id,
                              epoch_id=epoch_id, staked_amount=round(amount, 2),
                              pre_stake_balance=round(balance, 2))
        self._stakes[mutation_id] = record
        self._persist(record)
        self._save_wallets()
        return record

    def resolve(self, mutation_id: str, passed: bool,
                 fitness_improved: bool = False) -> StakeRecord | None:
        record = self._stakes.get(mutation_id)
        if not record or record.outcome != "pending":
            return record
        if passed and fitness_improved:
            earned = record.staked_amount * GOVERNANCE_PASS_MULTIPLIER
            self._wallets[record.agent_id] = self._wallets.get(record.agent_id, 0) + earned
            record.outcome = "passed"
            record.final_balance = round(self._wallets[record.agent_id], 2)
        elif passed:
            # Pass but no improvement: return stake, no bonus
            self._wallets[record.agent_id] = self._wallets.get(record.agent_id, 0) + record.staked_amount
            record.outcome = "passed"
            record.final_balance = round(self._wallets[record.agent_id], 2)
        else:
            # Fail: stake burned
            record.outcome = "failed"
            record.final_balance = round(self._wallets.get(record.agent_id, 0), 2)

        self._persist(record)
        self._save_wallets()
        return record

    def balance(self, agent_id: str) -> float:
        return round(self._wallets.get(agent_id, 0.0), 2)

    def agent_win_rate(self, agent_id: str) -> float:
        agent_records = [r for r in self._stakes.values()
                          if r.agent_id == agent_id and r.outcome != "pending"]
        if not agent_records:
            return 1.0
        won = sum(1 for r in agent_records if r.outcome == "passed")
        return round(won / len(agent_records), 4)

    def _load(self) -> None:
        if self.wallet_path.exists():
            try:
                self._wallets = json.loads(self.wallet_path.read_text())
            except Exception:
                pass
        if self.ledger_path.exists():
            for line in self.ledger_path.read_text().splitlines():
                try:
                    d = json.loads(line)
                    mid = d["mutation_id"]
                    self._stakes[mid] = StakeRecord(**d)
                except Exception:
                    pass

    def _save_wallets(self) -> None:
        self.wallet_path.parent.mkdir(parents=True, exist_ok=True)
        self.wallet_path.write_text(json.dumps(self._wallets, indent=2))

    def _persist(self, record: StakeRecord) -> None:
        import dataclasses
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(record)) + "\n")


__all__ = ["ReputationStakingLedger", "StakeRecord",
           "MIN_STAKE", "GOVERNANCE_PASS_MULTIPLIER"]
