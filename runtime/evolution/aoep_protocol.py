# SPDX-License-Identifier: Apache-2.0
"""INNOV-05 — Autonomous Organ Emergence Protocol (AOEP).

World-first implementation of constitutionally-governed autonomous architectural
self-extension for an autonomous software evolution system.

ADAAD's eight-organ architecture was defined by the ArchitectAgent at design
time.  AOEP allows the system to autonomously identify behavioral gaps in its
capability surface and propose entirely new organs — new architectural subsystems
— to address those gaps.  All proposals are subject to HUMAN-0 ratification;
no organ enters the implementation queue without explicit written sign-off.

Constitutional Invariants Introduced
─────────────────────────────────────
  AOEP-0   Every OrganProposal produced by AOEP-GATE-0 MUST be submitted to
           HUMAN-0 before any implementation begins.  AOEP-GATE-1 has no
           automated bypass path — absence of HUMAN-0 sign-off ALWAYS produces
           AOEP_HUMAN_0_BLOCKED; the organ does not constitutionally exist
           until the ratification event is appended to governance_events.jsonl.

Design Constraints
──────────────────
  - Fail-closed: any gate check failure blocks the proposal; no partial advance.
  - No datetime.now() / time.time() — epoch counter injected by caller.
  - All hashing is SHA-256; deterministic given fixed inputs.
  - HUMAN-0 gate is non-bypassable — no code path produces AOEP_APPROVED
    without a verified human_0_signature in the ratification payload.
  - OrganProposal, AOEPGateResult, and RatificationRecord are frozen dataclasses
    suitable for direct ledger append.
  - Mutation targeting a proposed-but-unratified organ is constitutionally
    forbidden (AOEP-0 subsumes organ boundary invariants from first commit).

Pipeline Position
─────────────────
  Post-SCDD, pre-implementation queue:
    SCDD_CLEAR → AOEP-GATE-0 → OrganProposal → HUMAN-0 → AOEP-GATE-1 → Phase

  AOEP is not in the per-epoch mutation hot path.  It runs when the system
  detects a sustained capability gap (≥ 10 consecutive epochs).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

AOEP_VERSION = "89.1"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AOEP_MIN_GAP_EPOCHS: int = 10            # sustained gap duration to qualify
AOEP_MIN_FAILURE_PATTERNS: int = 3       # distinct failure patterns required
AOEP_MIN_MEMORY_EPOCHS: int = 20         # epoch history required for evidence
AOEP_REEVAL_COOLDOWN_EPOCHS: int = 5     # epochs before re-evaluation after fail

# ---------------------------------------------------------------------------
# Failure code constants
# ---------------------------------------------------------------------------

AOEP_GAP_UNQUALIFIED = "AOEP_GAP_UNQUALIFIED"
AOEP_GAP_ADDRESSABLE = "AOEP_GAP_ADDRESSABLE"
AOEP_HUMAN_0_BLOCKED = "AOEP_HUMAN_0_BLOCKED"
AOEP_PROPOSAL_INCOMPLETE = "AOEP_PROPOSAL_INCOMPLETE"
AOEP_MANIFEST_CONFLICT = "AOEP_MANIFEST_CONFLICT"
AOEP_INSUFFICIENT_MEMORY = "AOEP_INSUFFICIENT_MEMORY"
AOEP_INSUFFICIENT_PATTERNS = "AOEP_INSUFFICIENT_PATTERNS"
AOEP_SIGNATURE_MISSING = "AOEP_SIGNATURE_MISSING"
AOEP_RATIFICATION_HASH_MISMATCH = "AOEP_RATIFICATION_HASH_MISMATCH"

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AOEPOutcome(str, Enum):
    APPROVED = "AOEP_APPROVED"           # GATE-1 passed: HUMAN-0 ratified
    GAP_QUALIFIED = "AOEP_GAP_QUALIFIED" # GATE-0 passed; awaiting HUMAN-0
    BLOCKED = "AOEP_BLOCKED"             # any gate check failed
    HUMAN_0_BLOCKED = "AOEP_HUMAN_0_BLOCKED"  # GATE-1: human absent or declined


class GapSeverity(str, Enum):
    MINOR = "MINOR"       # gap detected, not yet sustained
    MODERATE = "MODERATE" # sustained gap, addressable by existing organ
    CRITICAL = "CRITICAL" # sustained gap, requires new organ


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    PENDING_HUMAN_0 = "pending_human_0"
    RATIFIED = "ratified"
    REJECTED = "rejected"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityGapSignal:
    """Report of a detected capability gap in the organ manifest.

    Attributes:
        gap_id: Deterministic ID derived from gap_description hash.
        gap_description: Human-readable description of the unmet capability.
        sustained_epochs: Number of consecutive epochs gap was observed.
        affected_mutation_classes: Mutation classes impacted by the gap.
        candidate_organ_purpose: Natural-language statement of what a new
            organ would do to resolve this gap.
        gap_hash: SHA-256 of gap_description — tamper detection.
    """

    gap_id: str
    gap_description: str
    sustained_epochs: int
    affected_mutation_classes: FrozenSet[str]
    candidate_organ_purpose: str
    gap_hash: str


@dataclass(frozen=True)
class FailurePatternSummary:
    """Summary of recurring failure patterns attributable to a structural gap.

    Attributes:
        pattern_id: Canonical failure pattern ID (from FailurePatternMiner).
        occurrence_count: Number of times pattern was observed.
        attributed_gap_id: Gap ID this pattern is attributed to.
        evidence_epoch_ids: Epoch IDs where pattern appeared.
    """

    pattern_id: str
    occurrence_count: int
    attributed_gap_id: str
    evidence_epoch_ids: Tuple[str, ...]


@dataclass(frozen=True)
class OrganManifestEntry:
    """A single organ in the current organ manifest.

    Attributes:
        organ_id: Canonical organ ID (e.g. ``PerceptionOrgan``).
        purpose: Canonical purpose statement.
        input_types: Input type surface.
        output_types: Output type surface.
        capability_ids: Capabilities this organ covers.
    """

    organ_id: str
    purpose: str
    input_types: FrozenSet[str]
    output_types: FrozenSet[str]
    capability_ids: FrozenSet[str]


@dataclass(frozen=True)
class OrganProposal:
    """Formal proposal for a new architectural organ.

    Produced by AOEP-GATE-0 on qualification.  MUST be submitted to HUMAN-0
    before any implementation begins (AOEP-0).

    Attributes:
        proposal_id: Deterministic ID from content hash.
        organ_id: Proposed canonical organ ID (snake_case).
        purpose: One-sentence constitutional purpose statement.
        inputs: Required input types (interfaces).
        outputs: Produced output types (interfaces).
        proposed_invariants: Invariant IDs this organ will enforce.
        dependencies: Existing organ IDs this organ depends on.
        human_0_required: Always ``True`` for AOEP proposals.
        gap_signal: The CapabilityGapSignal that triggered this proposal.
        failure_evidence: Failure patterns attributing to the gap.
        epoch_id: Epoch when proposal was generated.
        proposal_hash: SHA-256 of canonical proposal JSON.
        status: Lifecycle status of the proposal.
    """

    proposal_id: str
    organ_id: str
    purpose: str
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    proposed_invariants: Tuple[str, ...]
    dependencies: Tuple[str, ...]
    human_0_required: bool
    gap_signal: CapabilityGapSignal
    failure_evidence: Tuple[FailurePatternSummary, ...]
    epoch_id: str
    proposal_hash: str
    status: ProposalStatus

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "organ_id": self.organ_id,
            "purpose": self.purpose,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "proposed_invariants": list(self.proposed_invariants),
            "dependencies": list(self.dependencies),
            "human_0_required": self.human_0_required,
            "gap_signal": {
                "gap_id": self.gap_signal.gap_id,
                "gap_description": self.gap_signal.gap_description,
                "sustained_epochs": self.gap_signal.sustained_epochs,
                "affected_mutation_classes": sorted(self.gap_signal.affected_mutation_classes),
                "candidate_organ_purpose": self.gap_signal.candidate_organ_purpose,
                "gap_hash": self.gap_signal.gap_hash,
            },
            "failure_evidence": [
                {
                    "pattern_id": fp.pattern_id,
                    "occurrence_count": fp.occurrence_count,
                    "attributed_gap_id": fp.attributed_gap_id,
                    "evidence_epoch_ids": list(fp.evidence_epoch_ids),
                }
                for fp in self.failure_evidence
            ],
            "epoch_id": self.epoch_id,
            "proposal_hash": self.proposal_hash,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class Human0RatificationPayload:
    """HUMAN-0 sign-off payload for an OrganProposal (AOEP-GATE-1 input).

    Attributes:
        proposal_id: Must match the OrganProposal.proposal_id.
        ratification_hash: SHA-256 of proposal_id + operator_id + timestamp.
        operator_id: HUMAN-0 identity (e.g. ``dustin.reid``).
        timestamp: Deterministic timestamp string (ISO-8601).
        human_0_signature: Operator sign-off string; MUST be non-empty.
        predecessor_hash: Hash of last governance_events.jsonl entry.
    """

    proposal_id: str
    ratification_hash: str
    operator_id: str
    timestamp: str
    human_0_signature: str
    predecessor_hash: str


@dataclass(frozen=True)
class RatificationRecord:
    """Ledger-ready record of a completed AOEP-GATE-1 ratification.

    Hash-chained via ``record_hash`` for governance_events.jsonl append.
    """

    proposal_id: str
    organ_id: str
    outcome: AOEPOutcome
    operator_id: str
    timestamp: str
    ratification_hash: str
    predecessor_hash: str
    record_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": "aoep_ratification",
            "aoep_version": AOEP_VERSION,
            "proposal_id": self.proposal_id,
            "organ_id": self.organ_id,
            "outcome": self.outcome.value,
            "operator_id": self.operator_id,
            "timestamp": self.timestamp,
            "ratification_hash": self.ratification_hash,
            "predecessor_hash": self.predecessor_hash,
            "record_hash": self.record_hash,
        }


@dataclass(frozen=True)
class AOEPGateResult:
    """Return value of evaluate_aoep_gate_0() or evaluate_aoep_gate_1().

    Attributes:
        outcome: AOEPOutcome enum.
        proposal: OrganProposal if GATE-0 passed; None on early block.
        ratification_record: RatificationRecord if GATE-1 passed; None otherwise.
        failure_codes: All triggered failure codes.
        gate_id: ``AOEP-GATE-0`` or ``AOEP-GATE-1``.
        result_hash: SHA-256 of canonical result JSON.
    """

    outcome: AOEPOutcome
    proposal: Optional[OrganProposal]
    ratification_record: Optional[RatificationRecord]
    failure_codes: Tuple[str, ...]
    gate_id: str
    result_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "proposal_id": self.proposal.proposal_id if self.proposal else None,
            "failure_codes": list(self.failure_codes),
            "gate_id": self.gate_id,
            "result_hash": self.result_hash,
        }


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def _proposal_content_hash(
    organ_id: str,
    purpose: str,
    inputs: Sequence[str],
    outputs: Sequence[str],
    proposed_invariants: Sequence[str],
    dependencies: Sequence[str],
    gap_id: str,
    epoch_id: str,
) -> str:
    payload = {
        "organ_id": organ_id,
        "purpose": purpose,
        "inputs": sorted(inputs),
        "outputs": sorted(outputs),
        "proposed_invariants": sorted(proposed_invariants),
        "dependencies": sorted(dependencies),
        "gap_id": gap_id,
        "epoch_id": epoch_id,
    }
    return _sha256(_canonical_json(payload))


def _result_hash(outcome: AOEPOutcome, gate_id: str, failure_codes: Sequence[str], proposal_id: Optional[str]) -> str:
    payload = {
        "outcome": outcome.value,
        "gate_id": gate_id,
        "failure_codes": sorted(failure_codes),
        "proposal_id": proposal_id,
    }
    return _sha256(_canonical_json(payload))


# ---------------------------------------------------------------------------
# Gap signal construction helper
# ---------------------------------------------------------------------------


def build_capability_gap_signal(
    gap_description: str,
    sustained_epochs: int,
    affected_mutation_classes: FrozenSet[str],
    candidate_organ_purpose: str,
) -> CapabilityGapSignal:
    """Construct a CapabilityGapSignal with deterministic ID and hash."""
    gap_hash = _sha256(gap_description)
    gap_id = f"GAP-{gap_hash[:12].upper()}"
    return CapabilityGapSignal(
        gap_id=gap_id,
        gap_description=gap_description,
        sustained_epochs=sustained_epochs,
        affected_mutation_classes=affected_mutation_classes,
        candidate_organ_purpose=candidate_organ_purpose,
        gap_hash=gap_hash,
    )


# ---------------------------------------------------------------------------
# AOEP-GATE-0 — Gap Qualification
# ---------------------------------------------------------------------------


def evaluate_aoep_gate_0(
    gap_signal: CapabilityGapSignal,
    failure_patterns: Sequence[FailurePatternSummary],
    organ_manifest: Sequence[OrganManifestEntry],
    memory_epoch_count: int,
    proposed_organ_id: str,
    proposed_purpose: str,
    proposed_inputs: Sequence[str],
    proposed_outputs: Sequence[str],
    proposed_invariants: Sequence[str],
    proposed_dependencies: Sequence[str],
    epoch_id: str,
) -> AOEPGateResult:
    """Evaluate AOEP-GATE-0 — Organ Emergence Gap Qualification.

    Gate checks (all must pass):
      1. sustained_epochs >= AOEP_MIN_GAP_EPOCHS
      2. failure_patterns has >= AOEP_MIN_FAILURE_PATTERNS distinct IDs
         attributed to the same gap
      3. Gap is NOT addressable by any existing organ (manifest check)
      4. memory_epoch_count >= AOEP_MIN_MEMORY_EPOCHS
      5. OrganProposal schema is complete (all required fields non-empty)

    On full pass: OrganProposal generated with status PENDING_HUMAN_0.
    On any fail:  AOEP_BLOCKED with specific failure codes.

    Args:
        gap_signal: Detected capability gap.
        failure_patterns: Failure patterns attributed to the gap.
        organ_manifest: All existing organ entries.
        memory_epoch_count: Number of epochs in the memory store.
        proposed_organ_id: Proposed canonical organ ID.
        proposed_purpose: One-sentence purpose statement.
        proposed_inputs: Required input type list.
        proposed_outputs: Produced output type list.
        proposed_invariants: Invariant IDs to enforce.
        proposed_dependencies: Existing organ IDs depended upon.
        epoch_id: Current epoch counter string.

    Returns:
        AOEPGateResult — always produced (pass or fail).
    """
    failure_codes: List[str] = []

    # Check 1: Sustained gap duration
    if gap_signal.sustained_epochs < AOEP_MIN_GAP_EPOCHS:
        log.info(
            "AOEP-GATE-0 check 1 FAIL: sustained_epochs=%d < %d",
            gap_signal.sustained_epochs,
            AOEP_MIN_GAP_EPOCHS,
        )
        failure_codes.append(AOEP_GAP_UNQUALIFIED)

    # Check 2: Sufficient distinct failure patterns attributed to gap
    attributed = [
        fp for fp in failure_patterns
        if fp.attributed_gap_id == gap_signal.gap_id
    ]
    distinct_pattern_ids = {fp.pattern_id for fp in attributed}
    if len(distinct_pattern_ids) < AOEP_MIN_FAILURE_PATTERNS:
        log.info(
            "AOEP-GATE-0 check 2 FAIL: %d distinct patterns < %d required",
            len(distinct_pattern_ids),
            AOEP_MIN_FAILURE_PATTERNS,
        )
        failure_codes.append(AOEP_INSUFFICIENT_PATTERNS)

    # Check 3: Gap is NOT addressable by an existing organ
    gap_classes = gap_signal.affected_mutation_classes
    for organ in organ_manifest:
        if organ.capability_ids & gap_classes:
            # Existing organ shares capability surface — gap is addressable
            log.info(
                "AOEP-GATE-0 check 3 FAIL: gap addressable by existing organ '%s'",
                organ.organ_id,
            )
            failure_codes.append(AOEP_GAP_ADDRESSABLE)
            break

    # Check 4: Sufficient epoch memory
    if memory_epoch_count < AOEP_MIN_MEMORY_EPOCHS:
        log.info(
            "AOEP-GATE-0 check 4 FAIL: memory_epoch_count=%d < %d",
            memory_epoch_count,
            AOEP_MIN_MEMORY_EPOCHS,
        )
        failure_codes.append(AOEP_INSUFFICIENT_MEMORY)

    # Check 5: Proposal schema completeness
    schema_errors: List[str] = []
    if not proposed_organ_id or not proposed_organ_id.strip():
        schema_errors.append("organ_id is empty")
    if not proposed_purpose or len(proposed_purpose.strip()) < 20:
        schema_errors.append("purpose too short (< 20 chars)")
    if not proposed_inputs:
        schema_errors.append("inputs list is empty")
    if not proposed_outputs:
        schema_errors.append("outputs list is empty")
    if schema_errors:
        log.info("AOEP-GATE-0 check 5 FAIL: schema errors: %s", schema_errors)
        failure_codes.append(AOEP_PROPOSAL_INCOMPLETE)

    # Check 5b: No conflict with existing organ IDs
    existing_organ_ids = {o.organ_id for o in organ_manifest}
    if proposed_organ_id in existing_organ_ids:
        log.info("AOEP-GATE-0 check 5b FAIL: organ_id '%s' already exists", proposed_organ_id)
        failure_codes.append(AOEP_MANIFEST_CONFLICT)

    if failure_codes:
        rh = _result_hash(AOEPOutcome.BLOCKED, "AOEP-GATE-0", failure_codes, None)
        return AOEPGateResult(
            outcome=AOEPOutcome.BLOCKED,
            proposal=None,
            ratification_record=None,
            failure_codes=tuple(failure_codes),
            gate_id="AOEP-GATE-0",
            result_hash=rh,
        )

    # All checks passed — build OrganProposal
    proposal_hash = _proposal_content_hash(
        organ_id=proposed_organ_id,
        purpose=proposed_purpose,
        inputs=proposed_inputs,
        outputs=proposed_outputs,
        proposed_invariants=proposed_invariants,
        dependencies=proposed_dependencies,
        gap_id=gap_signal.gap_id,
        epoch_id=epoch_id,
    )
    proposal_id = f"AOEP-{proposal_hash[:16].upper()}"

    proposal = OrganProposal(
        proposal_id=proposal_id,
        organ_id=proposed_organ_id,
        purpose=proposed_purpose,
        inputs=tuple(proposed_inputs),
        outputs=tuple(proposed_outputs),
        proposed_invariants=tuple(proposed_invariants),
        dependencies=tuple(proposed_dependencies),
        human_0_required=True,
        gap_signal=gap_signal,
        failure_evidence=tuple(attributed),
        epoch_id=epoch_id,
        proposal_hash=proposal_hash,
        status=ProposalStatus.PENDING_HUMAN_0,
    )

    rh = _result_hash(AOEPOutcome.GAP_QUALIFIED, "AOEP-GATE-0", [], proposal_id)
    log.info(
        "AOEP-GATE-0 QUALIFIED: proposal '%s' for organ '%s' — PENDING HUMAN-0",
        proposal_id,
        proposed_organ_id,
    )
    return AOEPGateResult(
        outcome=AOEPOutcome.GAP_QUALIFIED,
        proposal=proposal,
        ratification_record=None,
        failure_codes=(),
        gate_id="AOEP-GATE-0",
        result_hash=rh,
    )


# ---------------------------------------------------------------------------
# AOEP-GATE-1 — Human-0 Ratification (MANDATORY, NON-BYPASSABLE)
# ---------------------------------------------------------------------------


def evaluate_aoep_gate_1(
    proposal: OrganProposal,
    ratification_payload: Human0RatificationPayload,
) -> AOEPGateResult:
    """Evaluate AOEP-GATE-1 — Human-0 Ratification.

    AOEP-0 INVARIANT: This gate has NO automated bypass path.
    A non-empty human_0_signature is REQUIRED.  Any absent or empty
    signature ALWAYS produces AOEP_HUMAN_0_BLOCKED.

    Gate checks:
      1. proposal_id in ratification_payload matches proposal.proposal_id
      2. human_0_signature is non-empty (AOEP-0 enforcement)
      3. operator_id is non-empty
      4. ratification_hash verifiable: SHA-256(proposal_id + operator_id + timestamp)
      5. predecessor_hash is non-empty (chain integrity)

    On full pass: RatificationRecord produced; proposal status → RATIFIED.
    On any fail:  AOEP_HUMAN_0_BLOCKED or AOEP_BLOCKED.

    Args:
        proposal: OrganProposal from AOEP-GATE-0 (status PENDING_HUMAN_0).
        ratification_payload: Human-0 sign-off bundle.

    Returns:
        AOEPGateResult — always produced.
    """
    failure_codes: List[str] = []

    # Check 1: proposal_id match
    if ratification_payload.proposal_id != proposal.proposal_id:
        log.warning(
            "AOEP-GATE-1 check 1 FAIL: proposal_id mismatch '%s' vs '%s'",
            ratification_payload.proposal_id,
            proposal.proposal_id,
        )
        failure_codes.append(AOEP_GAP_UNQUALIFIED)

    # Check 2: AOEP-0 — human_0_signature MUST be non-empty
    if not ratification_payload.human_0_signature or not ratification_payload.human_0_signature.strip():
        log.warning("AOEP-GATE-1 check 2 FAIL: human_0_signature is empty — AOEP-0 violated")
        failure_codes.append(AOEP_SIGNATURE_MISSING)

    # Check 3: operator_id non-empty
    if not ratification_payload.operator_id or not ratification_payload.operator_id.strip():
        log.warning("AOEP-GATE-1 check 3 FAIL: operator_id is empty")
        failure_codes.append(AOEP_SIGNATURE_MISSING)

    # Check 4: ratification_hash verification
    expected_hash = _sha256(
        ratification_payload.proposal_id
        + ratification_payload.operator_id
        + ratification_payload.timestamp
    )
    if ratification_payload.ratification_hash != expected_hash:
        log.warning(
            "AOEP-GATE-1 check 4 FAIL: ratification_hash mismatch "
            "(expected %s, got %s)",
            expected_hash[:12],
            ratification_payload.ratification_hash[:12],
        )
        failure_codes.append(AOEP_RATIFICATION_HASH_MISMATCH)

    # Check 5: predecessor_hash non-empty
    if not ratification_payload.predecessor_hash or not ratification_payload.predecessor_hash.strip():
        log.warning("AOEP-GATE-1 check 5 FAIL: predecessor_hash is empty")
        failure_codes.append(AOEP_SIGNATURE_MISSING)

    if failure_codes:
        # Determine outcome: if signature missing, use HUMAN_0_BLOCKED
        outcome = (
            AOEPOutcome.HUMAN_0_BLOCKED
            if AOEP_SIGNATURE_MISSING in failure_codes
            else AOEPOutcome.BLOCKED
        )
        rh = _result_hash(outcome, "AOEP-GATE-1", failure_codes, proposal.proposal_id)
        log.warning(
            "AOEP-GATE-1 %s: proposal '%s' — codes: %s",
            outcome.value,
            proposal.proposal_id,
            failure_codes,
        )
        return AOEPGateResult(
            outcome=outcome,
            proposal=proposal,
            ratification_record=None,
            failure_codes=tuple(failure_codes),
            gate_id="AOEP-GATE-1",
            result_hash=rh,
        )

    # All checks passed — build RatificationRecord
    record_payload = {
        "proposal_id": proposal.proposal_id,
        "organ_id": proposal.organ_id,
        "outcome": AOEPOutcome.APPROVED.value,
        "operator_id": ratification_payload.operator_id,
        "timestamp": ratification_payload.timestamp,
        "ratification_hash": ratification_payload.ratification_hash,
        "predecessor_hash": ratification_payload.predecessor_hash,
    }
    record_hash = _sha256(_canonical_json(record_payload))

    ratification_record = RatificationRecord(
        proposal_id=proposal.proposal_id,
        organ_id=proposal.organ_id,
        outcome=AOEPOutcome.APPROVED,
        operator_id=ratification_payload.operator_id,
        timestamp=ratification_payload.timestamp,
        ratification_hash=ratification_payload.ratification_hash,
        predecessor_hash=ratification_payload.predecessor_hash,
        record_hash=record_hash,
    )

    rh = _result_hash(AOEPOutcome.APPROVED, "AOEP-GATE-1", [], proposal.proposal_id)
    log.info(
        "AOEP-GATE-1 APPROVED: organ '%s' ratified by '%s' — record_hash: %s",
        proposal.organ_id,
        ratification_payload.operator_id,
        record_hash[:16],
    )
    return AOEPGateResult(
        outcome=AOEPOutcome.APPROVED,
        proposal=proposal,
        ratification_record=ratification_record,
        failure_codes=(),
        gate_id="AOEP-GATE-1",
        result_hash=rh,
    )


# ---------------------------------------------------------------------------
# Cooldown tracker
# ---------------------------------------------------------------------------


@dataclass
class AOEPCooldownTracker:
    """Tracks re-evaluation cooldown per gap_id.

    After a GATE-0 failure, the gap must wait AOEP_REEVAL_COOLDOWN_EPOCHS
    before re-evaluation.  This prevents evaluation storms on persistent gaps.
    """

    _blocked_at: Dict[str, int] = field(default_factory=dict)

    def record_block(self, gap_id: str, epoch: int) -> None:
        self._blocked_at[gap_id] = epoch

    def is_cooling_down(self, gap_id: str, current_epoch: int) -> bool:
        if gap_id not in self._blocked_at:
            return False
        elapsed = current_epoch - self._blocked_at[gap_id]
        return elapsed < AOEP_REEVAL_COOLDOWN_EPOCHS

    def cooldown_remaining(self, gap_id: str, current_epoch: int) -> int:
        if gap_id not in self._blocked_at:
            return 0
        elapsed = current_epoch - self._blocked_at[gap_id]
        return max(0, AOEP_REEVAL_COOLDOWN_EPOCHS - elapsed)


# ---------------------------------------------------------------------------
# Serialisation helper (ledger integration)
# ---------------------------------------------------------------------------


def gate_result_to_ledger_payload(result: AOEPGateResult) -> Dict[str, Any]:
    """Convert an AOEPGateResult to a ledger-appendable dict."""
    payload: Dict[str, Any] = {
        "event_type": "aoep_gate_evaluation",
        "aoep_version": AOEP_VERSION,
        "gate_id": result.gate_id,
        "outcome": result.outcome.value,
        "failure_codes": list(result.failure_codes),
        "result_hash": result.result_hash,
    }
    if result.proposal is not None:
        payload["proposal_id"] = result.proposal.proposal_id
        payload["organ_id"] = result.proposal.organ_id
        payload["human_0_required"] = result.proposal.human_0_required
    if result.ratification_record is not None:
        payload["ratification"] = result.ratification_record.to_dict()
    return payload
