# SPDX-License-Identifier: Apache-2.0
"""Phase 81 — ConstitutionalSelfDiscoveryLoop (CSDL).

Top-level orchestrator for the Constitutional Self-Discovery Loop.

Wires together:
  1. FailurePatternMiner       — mines gate rejection patterns
  2. InvariantCandidateProposer — converts clusters → invariant candidates
  3. InvariantRatificationGate — HUMAN-0 presentation and decision recording

This is the entry point for Phase 81 autonomous invariant discovery.

Constitutional Invariants (Phase 81)
─────────────────────────────────────
  CSDL-0           No auto-discovered invariant enters constitution.yaml
                   without HUMAN-0 ratification.
  CSDL-0-AGENT     DEVADAAD generates and presents; governor decides and patches.
  CSDL-CLUSTER-0   Cluster membership is deterministic given identical input.
  CSDL-CANDIDATE-0 Candidate IDs are stable and deterministic.
  CSDL-CANDIDATE-ADVISORY-0  All candidates are disabled until ratified.
  CSDL-CANDIDATE-DEDUP-0  Same cluster → same candidate_id (idempotent).
  CSDL-MIN-FREQ-0  Only clusters meeting MIN_CLUSTER_FREQUENCY are proposed.
  CSDL-IMMUTABLE-0 Mining is read-only; ledger is never modified.
  CSDL-AUDIT-0     Every ratification decision is recorded.
  CSDL-REPLAY-0    Ratification records are deterministically replayable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from runtime.evolution.failure_pattern_miner import (
    FailureCluster,
    FailurePatternMiner,
    MIN_CLUSTER_FREQUENCY,
)
from runtime.evolution.invariant_candidate_proposer import (
    InvariantCandidate,
    InvariantCandidateProposer,
)
from runtime.evolution.invariant_ratification_gate import (
    InvariantRatificationGate,
    RatificationPackage,
)

log = logging.getLogger(__name__)

_PHASE = 81
_CSDL_VERSION = "81.0"


# ---------------------------------------------------------------------------
# Discovery run result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveryRunResult:
    """Complete output of one CSDL run.

    Attributes
    ----------
    run_id:            SHA-256 of the canonical discovery inputs.
    clusters_found:    Number of FailureCluster objects mined.
    candidates_proposed: Number of InvariantCandidate objects proposed.
    ratification_packages: RatificationPackage list (one per candidate, verdict=defer).
    preview_text:      Human-readable YAML patch preview for governor review.
    run_digest:        SHA-256 of all candidate IDs + cluster digests.
    phase:             ADAAD phase.
    schema_version:    CSDL schema version.
    """

    run_id: str
    clusters_found: int
    candidates_proposed: int
    ratification_packages: List[RatificationPackage]
    preview_text: str
    run_digest: str
    phase: int
    schema_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "clusters_found": self.clusters_found,
            "candidates_proposed": self.candidates_proposed,
            "ratification_packages": [p.to_dict() for p in self.ratification_packages],
            "preview_text": self.preview_text,
            "run_digest": self.run_digest,
            "phase": self.phase,
            "schema_version": self.schema_version,
        }

    @property
    def approved_count(self) -> int:
        return sum(1 for p in self.ratification_packages if p.record.verdict == "approve")

    @property
    def deferred_count(self) -> int:
        return sum(1 for p in self.ratification_packages if p.record.verdict == "defer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_id(ledger_path: Optional[Path], min_freq: int) -> str:
    payload = json.dumps(
        {"ledger_path": str(ledger_path), "min_freq": min_freq},
        sort_keys=True, separators=(",", ":"),
    )
    return "csdl-run-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _run_digest(clusters: Sequence[FailureCluster], candidates: Sequence[InvariantCandidate]) -> str:
    entries = (
        [c.cluster_digest for c in clusters]
        + [c.evidence_digest for c in candidates]
    )
    payload = json.dumps(sorted(entries), separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# ConstitutionalSelfDiscoveryLoop
# ---------------------------------------------------------------------------


class ConstitutionalSelfDiscoveryLoop:
    """Phase 81 — Constitutional Self-Discovery Loop orchestrator.

    Runs a complete CSDL cycle:
      mine → propose → present

    Ratification is always deferred to HUMAN-0. Use
    InvariantRatificationGate.ratify() for explicit decisions.

    Example
    -------
    csdl = ConstitutionalSelfDiscoveryLoop(
        ledger_path=Path("security/ledger/gate_decision_audit.jsonl"),
        artifact_dir=Path("artifacts/governance/phase81"),
    )
    result = csdl.run()
    print(result.preview_text)   # present to governor
    """

    def __init__(
        self,
        *,
        ledger_path: Optional[Path] = None,
        artifact_dir: Optional[Path] = None,
        governor: str = "Dustin L. Reid",
        min_cluster_frequency: int = MIN_CLUSTER_FREQUENCY,
        llm_client: Optional[Any] = None,
        use_llm_enhancement: bool = False,
    ) -> None:
        self._ledger_path = ledger_path
        self._artifact_dir = artifact_dir
        self._governor = governor
        self._min_freq = min_cluster_frequency
        self._miner = FailurePatternMiner(
            ledger_path=ledger_path,
            min_frequency=min_cluster_frequency,
        )
        self._proposer = InvariantCandidateProposer(
            llm_client=llm_client,
            use_llm_enhancement=use_llm_enhancement,
        )
        self._gate = InvariantRatificationGate(
            governor=governor,
            artifact_dir=artifact_dir,
        )

    def run(
        self,
        records: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> DiscoveryRunResult:
        """Execute one full CSDL cycle.

        Parameters
        ----------
        records : Optional pre-loaded raw ledger record list. If None,
                  reads from self._ledger_path.

        Returns
        -------
        DiscoveryRunResult with all mined clusters, proposed candidates,
        and deferred ratification packages ready for governor review.
        """
        log.info("CSDL: starting Phase 81 discovery run (min_freq=%d)", self._min_freq)

        # Step 1 — Mine failure patterns (CSDL-CLUSTER-0, CSDL-IMMUTABLE-0)
        clusters = self._miner.mine(records)
        log.info("CSDL: mined %d clusters", len(clusters))

        # Step 2 — Propose invariant candidates (CSDL-CANDIDATE-0)
        candidates = self._proposer.propose(clusters)
        log.info("CSDL: proposed %d invariant candidates", len(candidates))

        # Step 3 — Present to governor (CSDL-0, CSDL-AUDIT-0)
        packages = self._gate.present_batch(candidates)
        preview = self._gate.generate_constitution_patch_preview(candidates)

        rid = _run_id(self._ledger_path, self._min_freq)
        digest = _run_digest(clusters, candidates)

        result = DiscoveryRunResult(
            run_id=rid,
            clusters_found=len(clusters),
            candidates_proposed=len(candidates),
            ratification_packages=packages,
            preview_text=preview,
            run_digest=digest,
            phase=_PHASE,
            schema_version=_CSDL_VERSION,
        )

        # Write run artifact if dir configured
        if self._artifact_dir:
            self._write_run_artifact(result)

        log.info(
            "CSDL: discovery run complete — %d clusters, %d candidates, run_id=%s",
            result.clusters_found, result.candidates_proposed, result.run_id,
        )
        return result

    def run_with_injected_records(
        self, records: Sequence[Dict[str, Any]]
    ) -> DiscoveryRunResult:
        """Hermetic run with explicitly provided records (for testing/replay)."""
        return self.run(records=records)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _write_run_artifact(self, result: DiscoveryRunResult) -> None:
        if self._artifact_dir is None:
            return
        try:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            path = self._artifact_dir / f"csdl_run_{result.run_id}.json"
            summary = {
                "run_id": result.run_id,
                "clusters_found": result.clusters_found,
                "candidates_proposed": result.candidates_proposed,
                "run_digest": result.run_digest,
                "phase": result.phase,
                "schema_version": result.schema_version,
                "deferred_count": result.deferred_count,
                "approved_count": result.approved_count,
                "candidate_ids": [
                    p.record.candidate_id for p in result.ratification_packages
                ],
            }
            path.write_text(json.dumps(summary, indent=2))
            log.info("CSDL: wrote run artifact %s", path)
        except OSError as exc:
            log.warning("CSDL: failed to write run artifact: %s", exc)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "ConstitutionalSelfDiscoveryLoop",
    "DiscoveryRunResult",
    "FailurePatternMiner",
    "FailureCluster",
    "RejectionRecord",
    "InvariantCandidateProposer",
    "InvariantCandidate",
    "InvariantRatificationGate",
    "RatificationPackage",
    "RatificationRecord",
]

# re-exports for convenience
from runtime.evolution.failure_pattern_miner import RejectionRecord  # noqa: E402
from runtime.evolution.invariant_ratification_gate import RatificationRecord  # noqa: E402
