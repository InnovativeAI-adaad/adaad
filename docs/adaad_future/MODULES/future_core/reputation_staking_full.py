# SPDX-License-Identifier: Apache-2.0
"""Innovation #15 — Agent Reputation Staking (ARS).

Full implementation spec for Phase 100 promotion from scaffold.

Agents stake credits on proposals. Failed proposals burn stake.
Successful proposals return stake × GOVERNANCE_PASS_MULTIPLIER.
Converts hollow proposals into costly, accountable commitments.

Hard-class invariants:
    STAKE-0         — ledger persists before balance mutates (ledger-first)
    STAKE-DETERM-0  — stake_digest = sha256(agent_id:mutation_id:staked_amount)[:16]
    STAKE-HUMAN-0   — balance ceiling advisory at 10x initial_balance
    STAKE-BURN-0    — outcome settlement is atomic (no partial burns)
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MIN_STAKE: float = 1.0
MAX_STAKE_FRACTION: float = 0.20          # agent may stake at most 20% of balance
GOVERNANCE_PASS_MULTIPLIER: float = 1.5   # returned on pass
GOVERNANCE_FAIL_BURN_RATE: float = 1.0    # 100% burned on fail
BALANCE_CEILING_MULTIPLIER: float = 10.0  # advisory above 10x initial
DEFAULT_INITIAL_BALANCE: float = 100.0
STAKE_ADVISORY_EVENT: str = "stake_balance_ceiling_advisory.v1"

# ── Invariant declarations ────────────────────────────────────────────────────
INVARIANTS: dict[str, str] = {
    "STAKE-0": "Hard: ledger record persisted before balance decremented",
    "STAKE-DETERM-0": "Hard: stake_digest = sha256(agent_id:mutation_id:staked_amount)[:16]",
    "STAKE-HUMAN-0": "Hard: advisory fires when balance exceeds BALANCE_CEILING_MULTIPLIER × initial",
    "STAKE-BURN-0": "Hard: settlement is atomic — full pass multiplier or full burn, no partial",
}


# ── Data models ───────────────────────────────────────────────────────────────
@dataclass
class StakeRecord:
    agent_id: str
    mutation_id: str
    epoch_id: str
    staked_amount: float
    pre_stake_balance: float
    outcome: str = "pending"      # pending | passed | failed
    final_balance: float = 0.0
    stake_digest: str = ""

    def __post_init__(self) -> None:
        # STAKE-DETERM-0: deterministic digest from (agent, mutation, amount)
        if not self.stake_digest:
            payload = f"{self.agent_id}:{self.mutation_id}:{self.staked_amount}"
            self.stake_digest = (
                "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]
            )

    def is_pending(self) -> bool:
        return self.outcome == "pending"


@dataclass
class StakeAdvisoryEvent:
    """STAKE-HUMAN-0: advisory event when balance ceiling exceeded."""
    agent_id: str
    current_balance: float
    initial_balance: float
    ceiling_multiple: float
    epoch_id: str
    event_type: str = STAKE_ADVISORY_EVENT


# ── Core ledger ───────────────────────────────────────────────────────────────
class ReputationStakingLedger:
    """Manages agent reputation stakes with ledger-first STAKE-0 invariant."""

    def __init__(
        self,
        ledger_path: Path = Path("data/reputation_stakes.jsonl"),
        wallet_path: Path = Path("data/agent_wallets.json"),
        advisory_path: Path = Path("data/stake_advisories.jsonl"),
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.wallet_path = Path(wallet_path)
        self.advisory_path = Path(advisory_path)
        self._wallets: dict[str, float] = {}
        self._initial_balances: dict[str, float] = {}
        self._stakes: dict[str, StakeRecord] = {}   # keyed by stake_digest
        self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def register_agent(
        self, agent_id: str, initial_balance: float = DEFAULT_INITIAL_BALANCE
    ) -> None:
        """Register an agent with an initial balance. Idempotent."""
        if agent_id not in self._wallets:
            self._wallets[agent_id] = initial_balance
            self._initial_balances[agent_id] = initial_balance
            self._save_wallets()

    def balance(self, agent_id: str) -> float:
        """Return current balance. 0.0 for unknown agents."""
        return self._wallets.get(agent_id, 0.0)

    def stake(
        self,
        agent_id: str,
        mutation_id: str,
        epoch_id: str,
        amount: float | None = None,
    ) -> StakeRecord:
        """Agent stakes on a mutation proposal.

        STAKE-0: ledger record persists BEFORE balance is decremented.
        STAKE-HUMAN-0: advisory fires if resulting balance exceeds ceiling.
        """
        balance = self._wallets.get(agent_id, 0.0)

        # Compute stake amount
        if amount is None:
            amount = max(MIN_STAKE, balance * 0.05)
        amount = min(amount, balance * MAX_STAKE_FRACTION)
        amount = max(MIN_STAKE, min(amount, balance))

        record = StakeRecord(
            agent_id=agent_id,
            mutation_id=mutation_id,
            epoch_id=epoch_id,
            staked_amount=amount,
            pre_stake_balance=balance,
        )

        # STAKE-0: persist FIRST, then mutate balance
        self._persist_stake(record)
        self._wallets[agent_id] = balance - amount
        self._save_wallets()

        # STAKE-HUMAN-0: ceiling advisory
        self._check_ceiling_advisory(agent_id, epoch_id)

        self._stakes[record.stake_digest] = record
        return record

    def settle(self, stake_record: StakeRecord, outcome: str) -> StakeRecord:
        """Settle a stake after governance verdict.

        STAKE-BURN-0: atomic settlement — full multiplier or full burn.
        outcome: 'passed' | 'failed'
        """
        if stake_record.outcome != "pending":
            raise ValueError(
                f"Cannot settle: record {stake_record.stake_digest} already settled "
                f"as '{stake_record.outcome}'"
            )
        if outcome not in ("passed", "failed"):
            raise ValueError(f"Invalid outcome '{outcome}': must be 'passed' or 'failed'")

        current = self._wallets.get(stake_record.agent_id, 0.0)

        if outcome == "passed":
            # STAKE-BURN-0: full multiplier, atomic
            returned = stake_record.staked_amount * GOVERNANCE_PASS_MULTIPLIER
            self._wallets[stake_record.agent_id] = current + returned
        # outcome == 'failed': stake already deducted on stake(); nothing to return

        stake_record.outcome = outcome
        stake_record.final_balance = self._wallets.get(stake_record.agent_id, 0.0)

        # Persist updated record
        self._persist_stake(stake_record)
        self._save_wallets()

        return stake_record

    def cumulative_stats(self, agent_id: str) -> dict[str, Any]:
        """Cumulative pass/fail stats and ROI for an agent."""
        agent_stakes = [
            r for r in self._stakes.values()
            if r.agent_id == agent_id and r.outcome != "pending"
        ]
        total = len(agent_stakes)
        passed = sum(1 for r in agent_stakes if r.outcome == "passed")
        total_staked = sum(r.staked_amount for r in agent_stakes)
        total_returned = sum(
            r.staked_amount * GOVERNANCE_PASS_MULTIPLIER
            for r in agent_stakes if r.outcome == "passed"
        )
        net_gain = total_returned - total_staked
        return {
            "agent_id": agent_id,
            "total_proposals": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "total_staked": total_staked,
            "net_gain": net_gain,
            "current_balance": self.balance(agent_id),
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    def _check_ceiling_advisory(self, agent_id: str, epoch_id: str) -> None:
        """STAKE-HUMAN-0: emit advisory if balance exceeds ceiling."""
        initial = self._initial_balances.get(agent_id, DEFAULT_INITIAL_BALANCE)
        ceiling = initial * BALANCE_CEILING_MULTIPLIER
        current = self._wallets.get(agent_id, 0.0)
        if current > ceiling:
            advisory = StakeAdvisoryEvent(
                agent_id=agent_id,
                current_balance=current,
                initial_balance=initial,
                ceiling_multiple=current / initial,
                epoch_id=epoch_id,
            )
            self._persist_advisory(advisory)
            logger.warning(
                "STAKE-HUMAN-0 advisory: agent %s balance %.2f exceeds %.1f× initial %.2f",
                agent_id, current, BALANCE_CEILING_MULTIPLIER, initial,
            )

    def _persist_stake(self, record: StakeRecord) -> None:
        """Append-only JSONL write for stake record."""
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def _persist_advisory(self, advisory: StakeAdvisoryEvent) -> None:
        self.advisory_path.parent.mkdir(parents=True, exist_ok=True)
        with self.advisory_path.open("a") as f:
            f.write(json.dumps(asdict(advisory)) + "\n")

    def _save_wallets(self) -> None:
        self.wallet_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "wallets": self._wallets,
            "initial_balances": self._initial_balances,
        }
        self.wallet_path.write_text(json.dumps(payload, indent=2))

    def _load(self) -> None:
        """Fail-open load of wallets and stakes from disk."""
        if self.wallet_path.exists():
            try:
                data = json.loads(self.wallet_path.read_text())
                self._wallets = data.get("wallets", {})
                self._initial_balances = data.get("initial_balances", {})
            except Exception:
                pass  # fail-open

        if self.ledger_path.exists():
            try:
                for line in self.ledger_path.read_text().splitlines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        record = StakeRecord(**data)
                        self._stakes[record.stake_digest] = record
                    except Exception:
                        pass  # corrupt line silently skipped
            except Exception:
                pass  # fail-open


__all__ = [
    "ReputationStakingLedger",
    "StakeRecord",
    "StakeAdvisoryEvent",
    "INVARIANTS",
    "MIN_STAKE",
    "MAX_STAKE_FRACTION",
    "GOVERNANCE_PASS_MULTIPLIER",
    "GOVERNANCE_FAIL_BURN_RATE",
    "BALANCE_CEILING_MULTIPLIER",
]
