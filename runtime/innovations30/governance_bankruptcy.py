# SPDX-License-Identifier: Apache-2.0
"""Innovation #21 — Governance Debt Bankruptcy Protocol.
When governance debt is catastrophic: suspend proposals,
activate RemediationAgent, define exit criteria.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BANKRUPTCY_THRESHOLD: float = 0.90   # debt_score above this
REMEDIATION_HEALTH_TARGET: float = 0.65
REMEDIATION_CLEAN_STREAK: int = 5
BANKRUPTCY_EVENT_TYPE: str = "governance_bankruptcy_declared.v1"

@dataclass
class BankruptcyDeclaration:
    epoch_id: str
    debt_score: float
    health_score: float
    reason: str
    remediation_target_health: float = REMEDIATION_HEALTH_TARGET
    required_clean_epochs: int = REMEDIATION_CLEAN_STREAK
    status: str = "active"   # active | remediation | discharged
    declaration_digest: str = ""

    def __post_init__(self):
        if not self.declaration_digest:
            payload = f"{self.epoch_id}:{self.debt_score:.4f}:{self.status}"
            self.declaration_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]

@dataclass
class RemediationStep:
    step_id: str
    epoch_id: str
    mutation_id: str
    debt_reduction: float
    health_improvement: float
    accepted: bool


class GovernanceBankruptcyProtocol:
    """Manages structured remediation when governance debt is catastrophic."""

    def __init__(self, state_path: Path = Path("data/bankruptcy_state.jsonl")):
        self.state_path = Path(state_path)
        self._active_declaration: BankruptcyDeclaration | None = None
        self._clean_epoch_streak: int = 0
        self._load()

    @property
    def in_bankruptcy(self) -> bool:
        return (self._active_declaration is not None
                and self._active_declaration.status in ("active", "remediation"))

    def evaluate(self, epoch_id: str, debt_score: float,
                  health_score: float) -> BankruptcyDeclaration | None:
        """Check if bankruptcy should be declared."""
        if self.in_bankruptcy:
            return self._active_declaration
        if debt_score >= BANKRUPTCY_THRESHOLD:
            decl = BankruptcyDeclaration(
                epoch_id=epoch_id,
                debt_score=round(debt_score, 4),
                health_score=round(health_score, 4),
                reason=f"Governance debt {debt_score:.3f} exceeds critical threshold {BANKRUPTCY_THRESHOLD}",
            )
            self._active_declaration = decl
            self._persist_event(decl)
            return decl
        return None

    def record_remediation_epoch(self, epoch_id: str,
                                   health_score: float) -> bool:
        """Record a clean epoch during remediation. Returns True when discharged."""
        if not self.in_bankruptcy:
            return False
        if health_score >= REMEDIATION_HEALTH_TARGET:
            self._clean_epoch_streak += 1
        else:
            self._clean_epoch_streak = 0

        if self._clean_epoch_streak >= REMEDIATION_CLEAN_STREAK:
            self._active_declaration.status = "discharged"
            self._persist_event(self._active_declaration)
            self._active_declaration = None
            self._clean_epoch_streak = 0
            return True
        return False

    def is_mutation_allowed(self, mutation_intent: str) -> tuple[bool, str]:
        """During bankruptcy only debt-reducing mutations are allowed."""
        if not self.in_bankruptcy:
            return True, ""
        debt_reducing_keywords = [
            "fix governance", "reduce debt", "close finding",
            "resolve violation", "correct invariant", "fix compliance"
        ]
        if any(kw in mutation_intent.lower() for kw in debt_reducing_keywords):
            return True, "debt-reducing mutation allowed during bankruptcy"
        return False, (
            f"BANKRUPTCY ACTIVE (streak={self._clean_epoch_streak}/"
            f"{REMEDIATION_CLEAN_STREAK}): only debt-reducing mutations permitted"
        )

    def remediation_progress(self) -> dict[str, Any]:
        if not self._active_declaration:
            return {"status": "healthy", "in_bankruptcy": False}
        return {
            "status": self._active_declaration.status,
            "in_bankruptcy": True,
            "debt_score": self._active_declaration.debt_score,
            "clean_epoch_streak": self._clean_epoch_streak,
            "required_streak": REMEDIATION_CLEAN_STREAK,
            "target_health": REMEDIATION_HEALTH_TARGET,
        }

    def _persist_event(self, decl: BankruptcyDeclaration) -> None:
        import dataclasses
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(decl)) + "\n")

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        for line in self.state_path.read_text().splitlines():
            try:
                d = json.loads(line)
                if d.get("status") in ("active", "remediation"):
                    self._active_declaration = BankruptcyDeclaration(**d)
            except Exception:
                pass


__all__ = ["GovernanceBankruptcyProtocol", "BankruptcyDeclaration",
           "BANKRUPTCY_THRESHOLD", "REMEDIATION_CLEAN_STREAK"]
