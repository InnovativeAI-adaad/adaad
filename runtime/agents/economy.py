# SPDX-License-Identifier: Apache-2.0
"""Agent economy primitives for budgeting and credits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentWallet:
    agent_id: str
    credits: float = 0.0


@dataclass(frozen=True)
class EconomyTransfer:
    sender: str
    recipient: str
    amount: float


class AgentEconomy:
    """Simple in-memory economy API with typed transfer records."""

    def allocate(self, wallet: AgentWallet, amount: float) -> AgentWallet:
        return AgentWallet(agent_id=wallet.agent_id, credits=wallet.credits + max(amount, 0.0))

    def spend(self, wallet: AgentWallet, amount: float) -> AgentWallet:
        remaining = wallet.credits - max(amount, 0.0)
        return AgentWallet(agent_id=wallet.agent_id, credits=max(remaining, 0.0))

    def transfer(self, sender: AgentWallet, recipient: AgentWallet, amount: float) -> tuple[AgentWallet, AgentWallet, EconomyTransfer]:
        bounded_amount = min(max(amount, 0.0), sender.credits)
        updated_sender = AgentWallet(agent_id=sender.agent_id, credits=sender.credits - bounded_amount)
        updated_recipient = AgentWallet(agent_id=recipient.agent_id, credits=recipient.credits + bounded_amount)
        return updated_sender, updated_recipient, EconomyTransfer(
            sender=sender.agent_id,
            recipient=recipient.agent_id,
            amount=bounded_amount,
        )
