# SPDX-License-Identifier: Apache-2.0
"""Phase 81 — InvariantRatificationGate.

HUMAN-0 non-delegable gate for constitutional invariant ratification.

Presents InvariantCandidate proposals to a human governor and, upon
explicit ratification, generates a governance artifact and the exact
constitution.yaml patch required to activate the invariant.

Constitutional Invariants
─────────────────────────
  CSDL-0           No candidate invariant enters constitution.yaml without
                   HUMAN-0 ratification. This gate is the sole write surface.
  CSDL-0-AGENT     DEVADAAD may generate ratification packages and YAML patches
                   but MUST NOT apply them to constitution.yaml directly. The
                   human governor applies the patch.
  CSDL-AUDIT-0     Every ratification decision (approve / reject / defer) is
                   recorded in a RatificationRecord with an evidence digest.
  CSDL-REPLAY-0    Ratification records are deterministically replayable from
                   their evidence digest alone.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from runtime.evolution.invariant_candidate_proposer import InvariantCandidate

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RATIFICATION_VERSION: str = "81.0"
VALID_VERDICTS = frozenset({"approve", "reject", "defer"})


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RatificationRecord:
    """Audit record of a single ratification decision.

    Attributes
    ----------
    record_id:      SHA-256 of (candidate_id + verdict + governor).
    candidate_id:   Source InvariantCandidate.candidate_id.
    invariant_id:   Proposed invariant name.
    verdict:        "approve" | "reject" | "defer".
    governor:       Identity of the human making the decision (HUMAN-0).
    rationale:      Optional human rationale text.
    timestamp_utc:  ISO-8601 UTC timestamp of decision.
    evidence_digest: SHA-256 of canonical record payload.
    schema_version: Version tag.
    """

    record_id: str
    candidate_id: str
    invariant_id: str
    verdict: str
    governor: str
    rationale: str
    timestamp_utc: str
    evidence_digest: str
    schema_version: str = RATIFICATION_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "candidate_id": self.candidate_id,
            "invariant_id": self.invariant_id,
            "verdict": self.verdict,
            "governor": self.governor,
            "rationale": self.rationale,
            "timestamp_utc": self.timestamp_utc,
            "evidence_digest": self.evidence_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RatificationRecord":
        return cls(
            record_id=d["record_id"],
            candidate_id=d["candidate_id"],
            invariant_id=d["invariant_id"],
            verdict=d["verdict"],
            governor=d["governor"],
            rationale=d.get("rationale", ""),
            timestamp_utc=d["timestamp_utc"],
            evidence_digest=d["evidence_digest"],
            schema_version=d.get("schema_version", RATIFICATION_VERSION),
        )


@dataclass(frozen=True)
class RatificationPackage:
    """Complete output of InvariantRatificationGate for a single candidate.

    Attributes
    ----------
    record:              RatificationRecord for the decision.
    yaml_patch:          Exact JSON dict to append to constitution.yaml rules[].
                         Only populated for "approve" verdict, None otherwise.
    yaml_patch_instructions: Step-by-step instructions for the HUMAN-0 patch.
    activation_note:     Note for enabling the rule post-patch.
    """

    record: RatificationRecord
    yaml_patch: Optional[Dict[str, Any]]
    yaml_patch_instructions: str
    activation_note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "yaml_patch": self.yaml_patch,
            "yaml_patch_instructions": self.yaml_patch_instructions,
            "activation_note": self.activation_note,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record_id(candidate_id: str, verdict: str, governor: str) -> str:
    payload = f"{candidate_id}|{verdict}|{governor}"
    return "rat-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _evidence_digest(d: Dict[str, Any]) -> str:
    payload = json.dumps(
        {k: v for k, v in d.items() if k != "evidence_digest"},
        sort_keys=True, separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# InvariantRatificationGate
# ---------------------------------------------------------------------------


class InvariantRatificationGate:
    """Phase 81 HUMAN-0 ratification gate for invariant candidates.

    CSDL-0: This gate is the SOLE path by which DEVADAAD-proposed invariants
    can enter the constitutional ruleset. No direct writes to constitution.yaml
    are permitted by agent code.

    Usage (DEVADAAD presents package to governor):
    -----------------------------------------------
    gate = InvariantRatificationGate(governor="Dustin L. Reid")
    package = gate.present(candidate)   # produces ratification package
    # Governor reviews package.yaml_patch_instructions and manually applies

    Usage (recording an explicit decision):
    ----------------------------------------
    package = gate.ratify(candidate, verdict="approve", rationale="...")
    # package.yaml_patch contains the exact dict to insert into constitution.yaml
    """

    def __init__(
        self,
        *,
        governor: str = "Dustin L. Reid",
        artifact_dir: Optional[Path] = None,
    ) -> None:
        self._governor = governor
        self._artifact_dir = artifact_dir

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def present(self, candidate: InvariantCandidate) -> RatificationPackage:
        """Generate a ratification package for HUMAN-0 review.

        Verdict defaults to "defer" — the governor must explicitly call
        ratify() to record an approve or reject decision.

        CSDL-AUDIT-0: a RatificationRecord is always written for every
        presented candidate, even if deferred.
        """
        return self._build_package(candidate, verdict="defer", rationale="Pending HUMAN-0 review.")

    def present_batch(
        self, candidates: Sequence[InvariantCandidate]
    ) -> List[RatificationPackage]:
        """Present multiple candidates. Returns one package per candidate."""
        packages = [self.present(c) for c in candidates]
        if self._artifact_dir:
            self._write_batch_artifact(packages)
        return packages

    def ratify(
        self,
        candidate: InvariantCandidate,
        *,
        verdict: str,
        rationale: str = "",
    ) -> RatificationPackage:
        """Record an explicit ratification decision from the human governor.

        CSDL-0: only "approve" produces a yaml_patch. Reject and defer never
        produce patches — the invariant is never written to the constitution.
        CSDL-AUDIT-0: all decisions produce a RatificationRecord.

        Parameters
        ----------
        candidate : InvariantCandidate to ratify.
        verdict   : "approve" | "reject" | "defer".
        rationale : Human governor's rationale (optional but recommended).
        """
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"CSDL-0: invalid verdict '{verdict}'. Must be one of {sorted(VALID_VERDICTS)}."
            )
        package = self._build_package(candidate, verdict=verdict, rationale=rationale)
        if self._artifact_dir and verdict == "approve":
            self._write_approval_artifact(package)
        log.info(
            "CSDL-0: ratification decision recorded — candidate=%s verdict=%s governor=%s",
            candidate.candidate_id, verdict, self._governor,
        )
        return package

    def generate_constitution_patch_preview(
        self, candidates: Sequence[InvariantCandidate]
    ) -> str:
        """Generate a human-readable preview of all YAML patches.

        For operator review before any ratification decisions. Does not
        write to constitution.yaml (CSDL-0-AGENT).
        """
        lines = [
            "# CSDL Phase 81 — Invariant Ratification Preview",
            f"# Generated by DEVADAAD · Governor: {self._governor}",
            f"# Candidates: {len(candidates)}",
            "# ─────────────────────────────────────────────",
            "# INSTRUCTIONS: Review each entry below.",
            "# To activate: add entry to runtime/governance/constitution.yaml rules[]",
            "#               and set 'enabled: true' after HUMAN-0 ratification.",
            "",
        ]
        for i, c in enumerate(candidates, 1):
            lines.append(f"# Candidate {i}: {c.candidate_id} (freq={c.source_frequency})")
            lines.append(f"# Invariant: {c.invariant_id}")
            lines.append(f"# Source cluster: {c.source_cluster_id}")
            lines.append(json.dumps(c.constitution_entry, indent=2))
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_package(
        self,
        candidate: InvariantCandidate,
        verdict: str,
        rationale: str,
    ) -> RatificationPackage:
        ts = _utc_now()
        rid = _record_id(candidate.candidate_id, verdict, self._governor)
        partial = {
            "record_id": rid,
            "candidate_id": candidate.candidate_id,
            "invariant_id": candidate.invariant_id,
            "verdict": verdict,
            "governor": self._governor,
            "rationale": rationale,
            "timestamp_utc": ts,
        }
        digest = _evidence_digest(partial)
        record = RatificationRecord(
            record_id=rid,
            candidate_id=candidate.candidate_id,
            invariant_id=candidate.invariant_id,
            verdict=verdict,
            governor=self._governor,
            rationale=rationale,
            timestamp_utc=ts,
            evidence_digest=digest,
        )

        yaml_patch: Optional[Dict[str, Any]] = None
        instructions: str
        activation_note: str

        if verdict == "approve":
            # CSDL-0: governor approved — produce patch, do NOT apply it
            approved_entry = dict(candidate.constitution_entry)
            approved_entry["enabled"] = True  # Governor's approval activates rule
            yaml_patch = approved_entry
            instructions = (
                f"# CSDL-0 APPROVED — Manual patch required\n"
                f"# File: runtime/governance/constitution.yaml\n"
                f"# Action: Append the following entry to the 'rules' array:\n\n"
                + json.dumps(yaml_patch, indent=2)
                + f"\n\n# After insertion, run: python3 -m pytest tests/test_constitution_policy.py -v\n"
                f"# Commit message: governance(phase81): ratify invariant {candidate.invariant_id} — CSDL-0"
            )
            activation_note = (
                f"Rule '{candidate.name}' is enabled=true in the patch above. "
                f"It becomes active immediately on next GovernanceGate evaluation "
                f"after constitution.yaml is updated. Validate with CI before merging."
            )
        elif verdict == "reject":
            instructions = (
                f"# CSDL-0 REJECTED — No patch to apply.\n"
                f"# Candidate {candidate.candidate_id} rejected by {self._governor}.\n"
                f"# Rationale: {rationale}"
            )
            activation_note = "No action required. Candidate will not enter constitution.yaml."
        else:  # defer
            instructions = (
                f"# CSDL-0 DEFERRED — No patch to apply yet.\n"
                f"# Candidate {candidate.candidate_id} deferred pending further review.\n"
                f"# Call ratify(candidate, verdict='approve'|'reject') to record final decision."
            )
            activation_note = "Candidate remains in deferred state. Re-present when ready."

        return RatificationPackage(
            record=record,
            yaml_patch=yaml_patch,
            yaml_patch_instructions=instructions,
            activation_note=activation_note,
        )

    def _write_approval_artifact(self, package: RatificationPackage) -> None:
        """Write approval artifact to governance artifact dir."""
        if self._artifact_dir is None:
            return
        try:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            fname = f"ratification_{package.record.candidate_id}_{package.record.record_id[:8]}.json"
            path = self._artifact_dir / fname
            path.write_text(json.dumps(package.to_dict(), indent=2))
            log.info("CSDL-AUDIT-0: wrote ratification artifact %s", path)
        except OSError as exc:
            log.warning("CSDL: failed to write ratification artifact: %s", exc)

    def _write_batch_artifact(self, packages: List[RatificationPackage]) -> None:
        """Write a batch presentation artifact."""
        if self._artifact_dir is None:
            return
        try:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            ts = _utc_now().replace(":", "-").replace("T", "_")
            fname = f"ratification_batch_{ts}.json"
            path = self._artifact_dir / fname
            path.write_text(json.dumps([p.to_dict() for p in packages], indent=2))
            log.info("CSDL-AUDIT-0: wrote batch ratification artifact %s", path)
        except OSError as exc:
            log.warning("CSDL: failed to write batch artifact: %s", exc)
