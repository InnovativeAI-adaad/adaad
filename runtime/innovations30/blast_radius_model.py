# SPDX-License-Identifier: Apache-2.0
"""Innovation #27 — Mutation Blast Radius Modeling.
Formal reversal cost estimation before acceptance.

Additions (v1.1):
    REVERSAL_SLA              — tier-keyed SLA targets in hours
    dependency_graph_summary()— structured dep-graph snapshot for audit
    reversal_timeline()       — SLA-bound rollback plan per risk tier
    SHA-256 report digest     — tamper-detectable audit hash on every report
"""
from __future__ import annotations
import hashlib, subprocess, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ── Constitutional SLA constants [BLAST-SLA-0] ───────────────────────────────
# Reversal SLAs are constitutional commitments, not guidelines.
# Exceeding these must trigger a governance escalation.
REVERSAL_SLA: dict[str, float] = {
    "low":      1.0,    # hours — rollback in under 1 hr
    "medium":   8.0,    # same-day rollback
    "high":     48.0,   # coordinate downstream teams
    "critical": 168.0,  # migration plan, multi-day budget
}

BLAST_THRESHOLDS = {
    "critical": 50,
    "high":     20,
    "medium":   5,
    "low":      0,
}


@dataclass
class BlastRadiusReport:
    mutation_id: str
    changed_files: list[str]
    direct_dependents: int          # files that directly import changed files
    transitive_dependents: int      # files that transitively depend on changed files
    blast_score: float              # 0–1 normalised reversal cost
    risk_tier: str                  # "low" | "medium" | "high" | "critical"
    reversal_cost_estimate: str
    reversal_sla_hours: float = 1.0   # from REVERSAL_SLA[risk_tier]
    timestamp: float = field(default_factory=time.time)
    report_digest: str = ""

    def __post_init__(self) -> None:
        if not self.report_digest:
            payload = (
                f"{self.mutation_id}:{self.blast_score:.4f}:"
                f"{self.risk_tier}:{self.direct_dependents}:"
                f"{self.transitive_dependents}"
            )
            self.report_digest = (
                "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
            )


class BlastRadiusModeler:
    """Estimates the blast radius of a mutation for reversal cost assessment."""

    def __init__(self, repo_root: Path = Path(".")) -> None:
        self.repo_root = Path(repo_root)

    # ── Primary API ──────────────────────────────────────────────────────────

    def model(
        self, mutation_id: str, changed_files: list[str]
    ) -> BlastRadiusReport:
        """Compute blast radius report for a mutation.

        Args:
            mutation_id:   unique identifier for the mutation proposal
            changed_files: list of file paths modified by the mutation

        Returns:
            BlastRadiusReport with SHA-256 digest for audit chain.
        """
        direct = 0
        transitive = 0

        for f in changed_files:
            stem = Path(f).stem
            r = subprocess.run(
                ["grep", "-rl", "--include=*.py", stem, str(self.repo_root)],
                capture_output=True,
                text=True,
            )
            importers = [
                l for l in r.stdout.splitlines()
                if l and f not in l and "__pycache__" not in l
            ]
            direct += len(importers)
            transitive += len(importers) * 2  # conservative estimate

        blast_score = min(1.0, (direct + transitive * 0.3) / 100.0)
        risk_tier = "low"
        for tier, threshold in sorted(
            BLAST_THRESHOLDS.items(), key=lambda x: x[1], reverse=True
        ):
            if direct >= threshold:
                risk_tier = tier
                break

        reversal_cost = {
            "critical": (
                "CRITICAL: >50 dependent files. Multi-day rollback. "
                "Requires migration plan and governor sign-off."
            ),
            "high": (
                "HIGH: >20 dependent files. Coordinate downstream teams "
                "before rollback. SLA: 48 hours."
            ),
            "medium": (
                "MEDIUM: >5 dependent files. Same-day rollback feasible "
                "with testing. SLA: 8 hours."
            ),
            "low": (
                "LOW: <5 dependent files. Rollback in under 1 hour. "
                "SLA: 1 hour."
            ),
        }[risk_tier]

        return BlastRadiusReport(
            mutation_id=mutation_id,
            changed_files=changed_files,
            direct_dependents=direct,
            transitive_dependents=transitive,
            blast_score=round(blast_score, 4),
            risk_tier=risk_tier,
            reversal_cost_estimate=reversal_cost,
            reversal_sla_hours=REVERSAL_SLA[risk_tier],
        )

    # ── Audit & introspection ────────────────────────────────────────────────

    def dependency_graph_summary(
        self, changed_files: list[str]
    ) -> dict[str, Any]:
        """Return a structured snapshot of the dependency graph for changed files.

        Suitable for governance dashboards, audit reports, and diff tooling.

        Returns:
            {
              "changed_files": [...],
              "per_file": {
                "path": {
                  "direct_importers": [...],
                  "importer_count": N,
                }
              },
              "total_direct_importers": N,
              "unique_importers": [...],
            }
        """
        per_file: dict[str, Any] = {}
        all_importers: set[str] = set()

        for f in changed_files:
            stem = Path(f).stem
            r = subprocess.run(
                ["grep", "-rl", "--include=*.py", stem, str(self.repo_root)],
                capture_output=True,
                text=True,
            )
            importers = [
                l for l in r.stdout.splitlines()
                if l and f not in l and "__pycache__" not in l
            ]
            per_file[f] = {
                "direct_importers": importers[:20],   # cap at 20 for readability
                "importer_count": len(importers),
            }
            all_importers.update(importers)

        return {
            "changed_files": changed_files,
            "per_file": per_file,
            "total_direct_importers": sum(
                v["importer_count"] for v in per_file.values()
            ),
            "unique_importers": sorted(all_importers)[:50],  # cap at 50
            "snapshot_timestamp": round(time.time(), 3),
        }

    def reversal_timeline(self, risk_tier: str) -> dict[str, Any]:
        """Return a structured SLA-bound rollback plan for a given risk tier.

        This is the constitutional commitment [BLAST-SLA-0] to the governor.

        Args:
            risk_tier: "low" | "medium" | "high" | "critical"

        Returns:
            {
              "risk_tier": str,
              "sla_hours": float,
              "sla_deadline_utc_estimate": str,  # ISO-8601 approx
              "rollback_steps": [str, ...],
              "escalation_required": bool,
              "governor_signoff_required": bool,
            }
        """
        sla = REVERSAL_SLA.get(risk_tier, REVERSAL_SLA["critical"])
        deadline = time.time() + sla * 3600
        import datetime
        deadline_iso = datetime.datetime.fromtimestamp(deadline, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        plans: dict[str, dict[str, Any]] = {
            "low": {
                "rollback_steps": [
                    "1. Revert commit via `git revert <sha>` or `git reset --hard <sha>^`.",
                    "2. Re-run CI gate suite (< 5 min expected).",
                    "3. Deploy to staging. Verify no regressions.",
                    "4. Promote to production.",
                ],
                "escalation_required": False,
                "governor_signoff_required": False,
            },
            "medium": {
                "rollback_steps": [
                    "1. Notify affected module owners (same-day SLA).",
                    "2. Revert commit; confirm no dependent services are mid-deploy.",
                    "3. Run integration tests across all direct dependents.",
                    "4. Deploy to staging; smoke-test all affected endpoints.",
                    "5. Promote to production within 8 hours.",
                ],
                "escalation_required": False,
                "governor_signoff_required": False,
            },
            "high": {
                "rollback_steps": [
                    "1. ESCALATE: Notify downstream team leads immediately.",
                    "2. Freeze further mutations until rollback is complete.",
                    "3. Coordinate with downstream teams on reversal sequence.",
                    "4. Revert commit; check for cascading schema/API changes.",
                    "5. Full integration test suite across all 20+ dependents.",
                    "6. Staged rollout: staging → canary → production.",
                    "7. Monitor error rates for 24 hours post-rollback.",
                ],
                "escalation_required": True,
                "governor_signoff_required": False,
            },
            "critical": {
                "rollback_steps": [
                    "1. IMMEDIATE ESCALATION: Governor sign-off required [HUMAN-0].",
                    "2. Halt all mutation promotions system-wide.",
                    "3. Draft migration plan with rollback sequence for each dependent.",
                    "4. Coordinate multi-team rollback across all 50+ dependents.",
                    "5. Revert commit with full dependency audit at each step.",
                    "6. Run full constitutional test suite post-revert.",
                    "7. Multi-day stabilisation period before re-enabling mutations.",
                    "8. Post-mortem required within 72 hours [HUMAN-0 invariant].",
                ],
                "escalation_required": True,
                "governor_signoff_required": True,
            },
        }

        plan = plans.get(risk_tier, plans["critical"])
        return {
            "risk_tier": risk_tier,
            "sla_hours": sla,
            "sla_deadline_utc_estimate": deadline_iso,
            **plan,
            "invariant_code": "BLAST-SLA-0",
        }


__all__ = [
    "BlastRadiusModeler",
    "BlastRadiusReport",
    "BLAST_THRESHOLDS",
    "REVERSAL_SLA",
]
