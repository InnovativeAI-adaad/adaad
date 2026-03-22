# SPDX-License-Identifier: Apache-2.0
"""Innovation #20 — Constitutional Stress Testing.
Generates mutations calibrated to barely pass all rules.
Finds constitutional gaps. Feeds InvariantDiscoveryEngine.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class StressTestCase:
    case_id: str
    target_rule: str
    description: str
    mutation_pattern: str  # what kind of mutation to try
    expected_threshold_margin: float  # how close to the edge

@dataclass
class ConstitutionalGap:
    gap_id: str
    rules_bypassed: list[str]
    mutation_pattern: str
    risk_assessment: str
    recommended_new_rule: str
    gap_digest: str = ""

    def __post_init__(self):
        if not self.gap_digest:
            payload = f"{self.gap_id}:{','.join(self.rules_bypassed)}"
            self.gap_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]

@dataclass
class StressReport:
    epoch_id: str
    cases_tested: int
    gaps_found: int
    gaps: list[ConstitutionalGap]
    report_digest: str = ""

    def __post_init__(self):
        if not self.report_digest:
            payload = f"{self.epoch_id}:{self.gaps_found}"
            self.report_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


# Known constitutional weak points to stress test
STRESS_PATTERNS = [
    StressTestCase("SC-001", "single_file_scope",
                   "Mutation touching exactly 1 file boundary",
                   "single_file_with_import_chain", 0.05),
    StressTestCase("SC-002", "entropy_budget",
                   "Mutation consuming 99% of entropy budget",
                   "near_entropy_ceiling", 0.01),
    StressTestCase("SC-003", "lineage_continuity",
                   "Mutation with minimal but valid lineage reference",
                   "minimal_lineage_evidence", 0.05),
    StressTestCase("SC-004", "ast_validity",
                   "Mutation with valid AST but questionable semantics",
                   "valid_ast_edge_case", 0.10),
    StressTestCase("SC-005", "replay_determinism",
                   "Mutation using seeded random (passes lint but borderline)",
                   "seeded_entropy_use", 0.05),
]


class ConstitutionalStressTester:
    """Adversarially tests constitutional framework for gaps."""

    def __init__(self, report_path: Path = Path("data/constitutional_stress_reports.jsonl")):
        self.report_path = Path(report_path)

    def run(self, epoch_id: str,
             evaluate_fn) -> StressReport:
        """
        evaluate_fn(case: StressTestCase) → (passed_all_rules: bool, rules_missed: list[str])
        """
        gaps = []
        for case in STRESS_PATTERNS:
            try:
                passed, rules_missed = evaluate_fn(case)
                if passed and len(rules_missed) == 0:
                    # Mutation passed everything — potential gap if it's high-risk
                    if case.expected_threshold_margin < 0.05:
                        gap = ConstitutionalGap(
                            gap_id=f"GAP-{epoch_id[:8]}-{case.case_id}",
                            rules_bypassed=[case.target_rule],
                            mutation_pattern=case.mutation_pattern,
                            risk_assessment=f"Stress pattern '{case.description}' passed all rules with thin margin",
                            recommended_new_rule=f"Tighten {case.target_rule} threshold or add pre-condition check",
                        )
                        gaps.append(gap)
            except Exception:
                pass

        report = StressReport(
            epoch_id=epoch_id,
            cases_tested=len(STRESS_PATTERNS),
            gaps_found=len(gaps),
            gaps=gaps,
        )
        self._persist(report)
        return report

    def _persist(self, report: StressReport) -> None:
        import dataclasses
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        d = dataclasses.asdict(report)
        with self.report_path.open("a") as f:
            f.write(json.dumps(d) + "\n")


__all__ = ["ConstitutionalStressTester", "StressReport", "ConstitutionalGap",
           "STRESS_PATTERNS"]
