# SPDX-License-Identifier: Apache-2.0
"""Innovation #26 — Constitutional Entropy Budget.
Rate-limits constitutional drift. When 30% of rules differ from genesis,
further amendments require double-HUMAN-0.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DRIFT_WARNING_THRESHOLD: float = 0.20   # 20% drift → warning
DRIFT_CRITICAL_THRESHOLD: float = 0.30  # 30% drift → double-HUMAN-0 required
COOLING_PERIOD_EPOCHS: int = 10

@dataclass
class ConstitutionalDriftReport:
    current_rule_count: int
    genesis_rule_count: int
    modified_rules: list[str]
    added_rules: list[str]
    removed_rules: list[str]
    drift_ratio: float
    requires_double_signoff: bool
    cooling_period_active: bool
    last_amendment_epoch: str = ""
    report_digest: str = ""

    def __post_init__(self):
        if not self.report_digest:
            payload = f"{self.drift_ratio:.4f}:{self.requires_double_signoff}"
            self.report_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


class ConstitutionalEntropyBudget:
    """Monitors and rate-limits constitutional drift from genesis state."""

    def __init__(self, genesis_path: Path | None = None,
                 state_path: Path = Path("data/constitutional_entropy.json")):
        self.genesis_path = genesis_path or Path("runtime/governance/constitution.yaml")
        self.state_path = Path(state_path)
        self._genesis_rules: set[str] = set()
        self._last_amendment_epoch: str = ""
        self._last_amendment_seq: int = 0
        self._load()

    def snapshot_genesis(self, rule_names: list[str]) -> None:
        """Record the genesis state of the constitution."""
        self._genesis_rules = set(rule_names)
        self._save()

    def check_drift(self, current_rule_names: list[str],
                     current_epoch_seq: int,
                     proposed_amendment_rules: list[str] | None = None) -> ConstitutionalDriftReport:
        current = set(current_rule_names)
        genesis = self._genesis_rules

        if not genesis:
            genesis = current  # first run: treat current as genesis
            self._genesis_rules = genesis
            self._save()

        modified = []
        added = list(current - genesis)
        removed = list(genesis - current)
        # Simplified: count added+removed as total drift
        total_changed = len(added) + len(removed)
        drift_ratio = total_changed / max(1, len(genesis))

        requires_double = drift_ratio >= DRIFT_CRITICAL_THRESHOLD
        cooling_active = (
            self._last_amendment_seq > 0
            and current_epoch_seq - self._last_amendment_seq < COOLING_PERIOD_EPOCHS
        )

        return ConstitutionalDriftReport(
            current_rule_count=len(current),
            genesis_rule_count=len(genesis),
            modified_rules=modified,
            added_rules=added,
            removed_rules=removed,
            drift_ratio=round(drift_ratio, 4),
            requires_double_signoff=requires_double,
            cooling_period_active=cooling_active,
            last_amendment_epoch=self._last_amendment_epoch,
        )

    def record_amendment(self, epoch_id: str, epoch_seq: int) -> None:
        self._last_amendment_epoch = epoch_id
        self._last_amendment_seq = epoch_seq
        self._save()

    def _load(self) -> None:
        if self.state_path.exists():
            try:
                d = json.loads(self.state_path.read_text())
                self._genesis_rules = set(d.get("genesis_rules", []))
                self._last_amendment_epoch = d.get("last_amendment_epoch", "")
                self._last_amendment_seq = d.get("last_amendment_seq", 0)
            except Exception:
                pass

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({
            "genesis_rules": list(self._genesis_rules),
            "last_amendment_epoch": self._last_amendment_epoch,
            "last_amendment_seq": self._last_amendment_seq,
        }, indent=2))


__all__ = ["ConstitutionalEntropyBudget", "ConstitutionalDriftReport",
           "DRIFT_CRITICAL_THRESHOLD", "COOLING_PERIOD_EPOCHS"]
