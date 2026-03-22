# SPDX-License-Identifier: Apache-2.0
"""Innovation #27 — Mutation Blast Radius Modeling.
Formal reversal cost estimation before acceptance.
"""
from __future__ import annotations
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class BlastRadiusReport:
    mutation_id: str
    changed_files: list[str]
    direct_dependents: int     # files that directly import changed files
    transitive_dependents: int # files that transitively depend on changed files
    blast_score: float         # 0–1 normalized reversal cost
    risk_tier: str             # "low" | "medium" | "high" | "critical"
    reversal_cost_estimate: str
    report_digest: str = ""

    def __post_init__(self):
        if not self.report_digest:
            import hashlib
            payload = f"{self.mutation_id}:{self.blast_score:.4f}:{self.risk_tier}"
            self.report_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


BLAST_THRESHOLDS = {
    "critical": 50,
    "high": 20,
    "medium": 5,
    "low": 0,
}


class BlastRadiusModeler:
    """Estimates the blast radius of a mutation for reversal cost assessment."""

    def __init__(self, repo_root: Path = Path(".")):
        self.repo_root = Path(repo_root)

    def model(self, mutation_id: str, changed_files: list[str]) -> BlastRadiusReport:
        direct = 0
        transitive = 0

        for f in changed_files:
            stem = Path(f).stem
            # Find files importing this module
            r = subprocess.run(
                ['grep', '-rl', '--include=*.py', stem, str(self.repo_root)],
                capture_output=True, text=True
            )
            importers = [l for l in r.stdout.splitlines()
                          if l and f not in l and '__pycache__' not in l]
            direct += len(importers)
            transitive += len(importers) * 2  # rough estimate

        # Normalize
        blast_score = min(1.0, (direct + transitive * 0.3) / 100.0)
        risk_tier = "low"
        for tier, threshold in sorted(BLAST_THRESHOLDS.items(),
                                       key=lambda x: x[1], reverse=True):
            if direct >= threshold:
                risk_tier = tier
                break

        reversal_cost = {
            "critical": "CRITICAL: >50 dependent files. Multi-day rollback. Requires migration plan.",
            "high": "HIGH: >20 dependent files. Coordinate downstream teams before rollback.",
            "medium": "MEDIUM: >5 dependent files. Same-day rollback feasible with testing.",
            "low": "LOW: <5 dependent files. Rollback in under 1 hour.",
        }[risk_tier]

        return BlastRadiusReport(
            mutation_id=mutation_id,
            changed_files=changed_files,
            direct_dependents=direct,
            transitive_dependents=transitive,
            blast_score=round(blast_score, 4),
            risk_tier=risk_tier,
            reversal_cost_estimate=reversal_cost,
        )


__all__ = ["BlastRadiusModeler", "BlastRadiusReport", "BLAST_THRESHOLDS"]
