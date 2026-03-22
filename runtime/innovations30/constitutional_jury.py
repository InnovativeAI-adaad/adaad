# SPDX-License-Identifier: Apache-2.0
"""Innovation #14 — Constitutional Jury System.
2-of-3 independent agent evaluations for high-stakes mutations.
Dissenting verdicts feed InvariantDiscoveryEngine.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

JURY_SIZE: int = 3
MAJORITY_REQUIRED: int = 2
HIGH_STAKES_PATHS = frozenset(["runtime/", "security/", "app/main.py"])

@dataclass
class JurorVerdict:
    juror_id: str
    mutation_id: str
    verdict: str       # "approve" | "reject"
    confidence: float
    reasoning: str
    rules_fired: list[str]
    random_seed: str

@dataclass
class JuryDecision:
    mutation_id: str
    unanimous: bool
    majority_verdict: str    # "approve" | "reject"
    approve_count: int
    reject_count: int
    individual_verdicts: list[JurorVerdict]
    dissent_recorded: bool
    decision_digest: str = ""

    def __post_init__(self):
        if not self.decision_digest:
            payload = f"{self.mutation_id}:{self.majority_verdict}:{self.approve_count}"
            self.decision_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def is_high_stakes(changed_files: list[str]) -> bool:
    return any(any(p in str(f) for p in HIGH_STAKES_PATHS)
               for f in changed_files)


class ConstitutionalJury:
    """Convenes multi-juror deliberation for high-stakes mutations."""

    def __init__(self, ledger_path: Path = Path("data/jury_decisions.jsonl"),
                 jury_size: int = JURY_SIZE):
        self.ledger_path = Path(ledger_path)
        self.jury_size = jury_size

    def deliberate(self, mutation_id: str, changed_files: list[str],
                    evaluate_fn: Callable[[str, str], JurorVerdict]) -> JuryDecision:
        """Convene jury. evaluate_fn(mutation_id, seed) → JurorVerdict."""
        seeds = [f"seed-{mutation_id[:8]}-juror-{i}" for i in range(self.jury_size)]
        verdicts = [evaluate_fn(mutation_id, seed) for seed in seeds]

        approve_count = sum(1 for v in verdicts if v.verdict == "approve")
        reject_count = self.jury_size - approve_count
        majority = "approve" if approve_count >= MAJORITY_REQUIRED else "reject"
        unanimous = (approve_count == self.jury_size or reject_count == self.jury_size)

        # Record dissent
        dissent_recorded = not unanimous
        if dissent_recorded:
            self._record_dissent(mutation_id, verdicts)

        decision = JuryDecision(
            mutation_id=mutation_id,
            unanimous=unanimous,
            majority_verdict=majority,
            approve_count=approve_count,
            reject_count=reject_count,
            individual_verdicts=verdicts,
            dissent_recorded=dissent_recorded,
        )
        self._persist(decision)
        return decision

    def dissent_records(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent dissent records for InvariantDiscoveryEngine."""
        if not self.ledger_path.exists():
            return []
        records = []
        for line in self.ledger_path.read_text().splitlines():
            try:
                d = json.loads(line)
                if d.get("dissent_recorded"):
                    records.append(d)
            except Exception:
                pass
        return records[-limit:]

    def _record_dissent(self, mutation_id: str,
                         verdicts: list[JurorVerdict]) -> None:
        # Extract dissenting juror reasoning for InvariantDiscoveryEngine
        majority = "approve" if sum(1 for v in verdicts if v.verdict == "approve") >= MAJORITY_REQUIRED else "reject"
        dissenters = [v for v in verdicts if v.verdict != majority]
        for d in dissenters:
            path = self.ledger_path.with_suffix(".dissent.jsonl")
            path.parent.mkdir(parents=True, exist_ok=True)
            import dataclasses
            with path.open("a") as f:
                f.write(json.dumps({
                    "mutation_id": mutation_id,
                    "dissenter": d.juror_id,
                    "rules_fired": d.rules_fired,
                    "reasoning": d.reasoning,
                }) + "\n")

    def _persist(self, decision: JuryDecision) -> None:
        import dataclasses
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        d = dataclasses.asdict(decision)
        d.pop("individual_verdicts", None)  # don't bloat ledger
        with self.ledger_path.open("a") as f:
            f.write(json.dumps(d) + "\n")


__all__ = ["ConstitutionalJury", "JuryDecision", "JurorVerdict",
           "is_high_stakes", "JURY_SIZE", "HIGH_STAKES_PATHS"]
