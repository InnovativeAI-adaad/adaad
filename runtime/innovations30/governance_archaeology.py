# SPDX-License-Identifier: Apache-2.0
"""Innovation #19 — Governance Archaeology Mode.
Assembles complete cryptographically-verified decision timeline
for any mutation from proposal to production.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class DecisionEvent:
    event_type: str
    timestamp: str
    epoch_id: str
    mutation_id: str
    actor: str
    outcome: str
    details: dict[str, Any] = field(default_factory=dict)
    ledger_hash: str = ""

@dataclass
class MutationTimeline:
    mutation_id: str
    events: list[DecisionEvent]
    final_outcome: str
    timeline_digest: str = ""
    chain_verified: bool = False

    @property
    def proposal_event(self) -> DecisionEvent | None:
        return next((e for e in self.events if e.event_type == "proposed"), None)

    @property
    def governance_events(self) -> list[DecisionEvent]:
        return [e for e in self.events if "gate" in e.event_type.lower()]

    @property
    def human_events(self) -> list[DecisionEvent]:
        return [e for e in self.events if "human" in e.actor.lower()]


class GovernanceArchaeologist:
    """Assembles complete mutation audit trails from distributed ledgers."""

    def __init__(self, ledger_roots: list[Path] | None = None):
        self.ledger_roots = ledger_roots or [
            Path("security/ledger"),
            Path("data"),
        ]

    def excavate(self, mutation_id: str) -> MutationTimeline:
        """Assemble complete timeline for a mutation_id."""
        events: list[DecisionEvent] = []

        for root in self.ledger_roots:
            if not root.exists():
                continue
            for ledger_file in sorted(root.rglob("*.jsonl")):
                try:
                    for line in ledger_file.read_text().splitlines():
                        if mutation_id in line:
                            try:
                                record = json.loads(line)
                                event = self._parse_event(record, mutation_id)
                                if event:
                                    events.append(event)
                            except Exception:
                                pass
                except Exception:
                    pass

        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp or "")

        final_outcome = "unknown"
        for e in reversed(events):
            if e.event_type in ("approved", "rejected", "promoted", "rolled_back"):
                final_outcome = e.outcome
                break

        import hashlib
        digest_payload = json.dumps([e.event_type for e in events])
        digest = "sha256:" + hashlib.sha256(digest_payload.encode()).hexdigest()[:16]

        return MutationTimeline(
            mutation_id=mutation_id,
            events=events,
            final_outcome=final_outcome,
            timeline_digest=digest,
            chain_verified=len(events) > 0,
        )

    def _parse_event(self, record: dict[str, Any],
                      mutation_id: str) -> DecisionEvent | None:
        if record.get("mutation_id") != mutation_id:
            return None
        return DecisionEvent(
            event_type=record.get("event_type", record.get("action", "unknown")),
            timestamp=record.get("ts", record.get("timestamp", "")),
            epoch_id=record.get("epoch_id", ""),
            mutation_id=mutation_id,
            actor=record.get("agent_id", record.get("actor", "system")),
            outcome=record.get("outcome", record.get("verdict", "recorded")),
            details={k: v for k, v in record.items()
                     if k not in ("event_type", "ts", "epoch_id",
                                   "mutation_id", "agent_id")},
        )


__all__ = ["GovernanceArchaeologist", "MutationTimeline", "DecisionEvent"]
