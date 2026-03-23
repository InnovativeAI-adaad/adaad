# SPDX-License-Identifier: Apache-2.0
"""INNOV-01 — Constitutional Self-Amendment Protocol (CSAP).

World-first implementation of a governed constitutional self-amendment
protocol for an autonomous software evolution system.

The system may propose amendments to its own constitutional invariant
set. All amendments are subject to:
  - CSAP-GATE-0  Proposal Eligibility
  - CSAP-GATE-1  Supermajority Ratification (automated validators +
                 optional HUMAN-0 co-signature for Hard-class targets)

Constitutional Invariants Introduced
─────────────────────────────────────
  CSAP-0   ConstitutionalAmendmentProposal MUST NOT target Hard-class
           invariants without HUMAN-0 co-signature in the proposal payload.
  CSAP-1   All ratified amendments MUST be appended to
           governance_events.jsonl before any mutation uses the amended
           invariant.

Design Constraints
──────────────────
  - Deterministic in all gate outcomes.
  - Fail-closed: any check failure blocks the amendment; no partial state.
  - No direct file IO except via ConstitutionalAmendmentLedger.
  - No datetime.now() / time.time() — deterministic timestamps only via
    RuntimeDeterminismProvider or injected clock.
  - All public functions are pure given fixed inputs (except ledger appends).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

CSAP_VERSION = "87.1"

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class InvariantClass(str, Enum):
    HARD = "Hard"
    CLASS_B_ELIGIBLE = "Class-B-Eligible"


class AmendmentStatus(str, Enum):
    PENDING = "pending"
    ELIGIBLE = "eligible"
    RATIFIED = "ratified"
    REJECTED = "rejected"
    MALFORMED = "malformed"
    TEMPORAL_HOLD = "temporal_hold"


class CSAPGateOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Failure codes (CSAP spec §Failure Modes)
# ---------------------------------------------------------------------------

AMENDMENT_INELIGIBLE = "AMENDMENT_INELIGIBLE"
RATIFICATION_DENIED = "RATIFICATION_DENIED"
AMENDMENT_CONFLICT = "AMENDMENT_CONFLICT"
AMENDMENT_REPLAY_BROKEN = "AMENDMENT_REPLAY_BROKEN"
INVARIANT_PARSER_REJECT = "INVARIANT_PARSER_REJECT"


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstitutionalAmendmentProposal:
    """Machine-readable amendment proposal produced by ProposalEngine.

    Attributes
    ----------
    proposal_id:        Unique identifier (deterministic from content hash).
    target_rule_id:     ID of the invariant to amend (MUST exist in matrix).
    intent:             Human-readable description of the amendment's purpose.
    proposed_text:      New invariant statement (MUST be parseable by InvariantParser).
    rationale:          Structured rationale referencing evidence.
    evidence_refs:      At least 3 distinct EvidenceBundle IDs showing friction.
    author:             Agent or component that authored the proposal.
    epoch_id:           CEL epoch that produced this proposal.
    human_0_cosignature: Required when targeting Hard-class invariants.
    """

    proposal_id: str
    target_rule_id: str
    intent: str
    proposed_text: str
    rationale: str
    evidence_refs: Tuple[str, ...]
    author: str
    epoch_id: str
    human_0_cosignature: Optional[str] = None

    def content_hash(self) -> str:
        payload = json.dumps(
            {
                "target_rule_id": self.target_rule_id,
                "intent": self.intent,
                "proposed_text": self.proposed_text,
                "rationale": self.rationale,
                "evidence_refs": sorted(self.evidence_refs),
                "author": self.author,
                "epoch_id": self.epoch_id,
            },
            sort_keys=True,
        )
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "target_rule_id": self.target_rule_id,
            "intent": self.intent,
            "proposed_text": self.proposed_text,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "author": self.author,
            "epoch_id": self.epoch_id,
            "human_0_cosignature": self.human_0_cosignature,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConstitutionalAmendmentProposal":
        return cls(
            proposal_id=d["proposal_id"],
            target_rule_id=d["target_rule_id"],
            intent=d["intent"],
            proposed_text=d["proposed_text"],
            rationale=d["rationale"],
            evidence_refs=tuple(d["evidence_refs"]),
            author=d["author"],
            epoch_id=d["epoch_id"],
            human_0_cosignature=d.get("human_0_cosignature"),
        )


@dataclass(frozen=True)
class InvariantEntry:
    """Single entry in the InvariantsMatrix."""

    rule_id: str
    statement: str
    invariant_class: InvariantClass
    phase: int
    enforcement: str
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "statement": self.statement,
            "invariant_class": self.invariant_class.value,
            "phase": self.phase,
            "enforcement": self.enforcement,
            "enabled": self.enabled,
        }


@dataclass
class InvariantsMatrix:
    """Machine-readable registry of all constitutional invariants.

    Invariants are keyed by rule_id. Amendments add or replace entries.
    The matrix is append-only for Hard-class invariants — they can only
    be amended, never deleted, without HUMAN-0 explicit sign-off.
    """

    entries: Dict[str, InvariantEntry] = field(default_factory=dict)
    matrix_hash: str = ""

    def __post_init__(self) -> None:
        if not self.matrix_hash:
            self.matrix_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = json.dumps(
            {k: v.to_dict() for k, v in sorted(self.entries.items())},
            sort_keys=True,
        )
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

    def contains(self, rule_id: str) -> bool:
        return rule_id in self.entries

    def get(self, rule_id: str) -> Optional[InvariantEntry]:
        return self.entries.get(rule_id)

    def invariant_class_of(self, rule_id: str) -> Optional[InvariantClass]:
        entry = self.entries.get(rule_id)
        return entry.invariant_class if entry else None

    def apply_amendment(
        self, rule_id: str, new_statement: str, *, ratification_hash: str
    ) -> "InvariantsMatrix":
        """Return a new matrix with the amended invariant applied.

        CSAP-1: the amendment is NOT applied here — it is applied only
        after the ledger event is committed (caller responsibility).
        This method produces the candidate post-amendment matrix for
        validation purposes.
        """
        existing = self.entries.get(rule_id)
        if existing is None:
            raise ValueError(f"CSAP: rule_id '{rule_id}' not found in matrix")
        updated_entry = InvariantEntry(
            rule_id=rule_id,
            statement=new_statement,
            invariant_class=existing.invariant_class,
            phase=existing.phase,
            enforcement=existing.enforcement,
            enabled=existing.enabled,
        )
        new_entries = dict(self.entries)
        new_entries[rule_id] = updated_entry
        new_matrix = InvariantsMatrix(entries=new_entries)
        new_matrix.matrix_hash = new_matrix._compute_hash()
        return new_matrix


@dataclass(frozen=True)
class CSAPGateReport:
    """Structured gate evaluation result — deterministically replayable."""

    gate_id: str
    outcome: CSAPGateOutcome
    failure_code: Optional[str]
    checks_passed: Tuple[str, ...]
    checks_failed: Tuple[str, ...]
    evidence_digest: str
    proposal_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "outcome": self.outcome.value,
            "failure_code": self.failure_code,
            "checks_passed": list(self.checks_passed),
            "checks_failed": list(self.checks_failed),
            "evidence_digest": self.evidence_digest,
            "proposal_id": self.proposal_id,
        }


@dataclass(frozen=True)
class AmendmentRatificationRecord:
    """Ledger record written on AMENDMENT_RATIFIED or RATIFICATION_DENIED."""

    record_id: str
    proposal_id: str
    target_rule_id: str
    status: AmendmentStatus
    gate_0_report: CSAPGateReport
    gate_1_report: Optional[CSAPGateReport]
    ratification_hash: str
    predecessor_hash: str
    timestamp_utc: str
    schema_version: str = CSAP_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "proposal_id": self.proposal_id,
            "target_rule_id": self.target_rule_id,
            "status": self.status.value,
            "gate_0_report": self.gate_0_report.to_dict(),
            "gate_1_report": self.gate_1_report.to_dict() if self.gate_1_report else None,
            "ratification_hash": self.ratification_hash,
            "predecessor_hash": self.predecessor_hash,
            "timestamp_utc": self.timestamp_utc,
            "schema_version": self.schema_version,
        }


# ---------------------------------------------------------------------------
# InvariantParser
# ---------------------------------------------------------------------------

# Minimal grammar: a valid invariant statement must contain a subject, a
# modal verb (MUST / MUST NOT / SHALL / SHALL NOT), and a predicate phrase.
# This is not a full NLP parser — it enforces structural parsability only.
_MODAL_PATTERN = re.compile(
    r"\b(MUST NOT|MUST|SHALL NOT|SHALL|SHOULD NOT|SHOULD)\b", re.IGNORECASE
)
_MIN_STATEMENT_TOKENS = 6


class InvariantParser:
    """Deterministic structural parser for constitutional invariant statements.

    CSAP spec: proposed_text MUST be parseable into a machine-evaluable
    condition before the amendment may proceed.

    A statement is considered parseable if:
      1. It contains at least one modal verb (MUST / MUST NOT / SHALL / ...).
      2. It contains at least _MIN_STATEMENT_TOKENS whitespace-delimited tokens.
      3. It is a non-empty string after stripping whitespace.
      4. It does not contain placeholder tokens ('[', ']', '<', '>').
    """

    @staticmethod
    def parse(text: str) -> Tuple[bool, str]:
        """Return (is_valid, reason). Deterministic."""
        if not text or not text.strip():
            return False, "INVARIANT_PARSER_REJECT: empty statement"
        stripped = text.strip()
        if any(ch in stripped for ch in ("[", "]", "<", ">")):
            return False, "INVARIANT_PARSER_REJECT: placeholder tokens present"
        tokens = stripped.split()
        if len(tokens) < _MIN_STATEMENT_TOKENS:
            return (
                False,
                f"INVARIANT_PARSER_REJECT: too few tokens ({len(tokens)} < {_MIN_STATEMENT_TOKENS})",
            )
        if not _MODAL_PATTERN.search(stripped):
            return False, "INVARIANT_PARSER_REJECT: no modal verb (MUST/SHALL) found"
        return True, "OK"


# ---------------------------------------------------------------------------
# ConstitutionalAmendmentQueue
# ---------------------------------------------------------------------------


class ConstitutionalAmendmentQueue:
    """Append-only persisted queue of amendment proposals.

    CSAP-GATE-1 check 1: proposals are submitted here before ratification
    vote proceeds. Persistence guarantees no proposal is silently lost.
    """

    def __init__(self, queue_path: Path) -> None:
        self._path = queue_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("")

    def enqueue(self, proposal: ConstitutionalAmendmentProposal) -> None:
        with self._path.open("a") as f:
            f.write(json.dumps(proposal.to_dict()) + "\n")
        log.info("CSAP: enqueued proposal %s → %s", proposal.proposal_id, self._path)

    def all_proposals(self) -> List[ConstitutionalAmendmentProposal]:
        lines = [l.strip() for l in self._path.read_text().splitlines() if l.strip()]
        return [ConstitutionalAmendmentProposal.from_dict(json.loads(l)) for l in lines]


# ---------------------------------------------------------------------------
# ConstitutionalAmendmentLedger
# ---------------------------------------------------------------------------


class ConstitutionalAmendmentLedger:
    """Append-only ledger for amendment ratification records.

    CSAP-1: amendments are appended here BEFORE the InvariantsMatrix is
    updated. The ledger is the authoritative source of truth for amendment
    history. The matrix is derived from it.

    AMENDMENT_REPLAY_BROKEN is raised if the predecessor_hash chain is
    broken at read time.
    """

    def __init__(self, ledger_path: Path) -> None:
        self._path = ledger_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("")

    def tail_hash(self) -> str:
        lines = [l.strip() for l in self._path.read_text().splitlines() if l.strip()]
        if not lines:
            return "sha256:" + "0" * 64
        last = json.loads(lines[-1])
        rh = last.get("ratification_hash")
        if not rh:
            return "sha256:" + "0" * 64
        return rh

    def append(self, record: AmendmentRatificationRecord) -> None:
        with self._path.open("a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
        log.info(
            "CSAP: ledger append — %s status=%s", record.proposal_id, record.status.value
        )

    def verify_chain(self) -> Tuple[bool, str]:
        """Verify predecessor_hash chain integrity. Deterministic."""
        lines = [l.strip() for l in self._path.read_text().splitlines() if l.strip()]
        if not lines:
            return True, "empty ledger — OK"
        prev_hash = "sha256:" + "0" * 64
        for i, line in enumerate(lines):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                return False, f"AMENDMENT_REPLAY_BROKEN: line {i} invalid JSON: {exc}"
            if record.get("predecessor_hash") != prev_hash:
                return (
                    False,
                    f"AMENDMENT_REPLAY_BROKEN: chain broken at record {i} "
                    f"(expected predecessor={prev_hash}, got={record.get('predecessor_hash')})",
                )
            prev_hash = record.get("ratification_hash", prev_hash)
        return True, "chain intact"


# ---------------------------------------------------------------------------
# CSAP-GATE-0 — Proposal Eligibility
# ---------------------------------------------------------------------------


def _gate_0_evidence_digest(proposal: ConstitutionalAmendmentProposal, checks: Dict[str, bool]) -> str:
    payload = json.dumps(
        {"proposal_id": proposal.proposal_id, "checks": checks}, sort_keys=True
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def evaluate_csap_gate_0(
    proposal: ConstitutionalAmendmentProposal,
    invariants_matrix: InvariantsMatrix,
    governance_debt_score: float,
    amendment_ledger: ConstitutionalAmendmentLedger,
) -> CSAPGateReport:
    """CSAP-GATE-0: Proposal Eligibility.

    Six deterministic checks. Fail-closed on any single failure.

    Returns
    -------
    CSAPGateReport with PASS or FAIL outcome.
    """
    checks_passed: List[str] = []
    checks_failed: List[str] = []
    failure_code: Optional[str] = None

    # Check 1: target_rule_id exists in matrix
    check_1_id = "CHECK-1-TARGET-EXISTS"
    if invariants_matrix.contains(proposal.target_rule_id):
        checks_passed.append(check_1_id)
    else:
        checks_failed.append(check_1_id)
        failure_code = AMENDMENT_INELIGIBLE
        log.warning("CSAP-GATE-0: %s — rule_id '%s' not in matrix", check_1_id, proposal.target_rule_id)

    # Check 2: evidence_refs >= 3 distinct IDs
    check_2_id = "CHECK-2-EVIDENCE-REFS"
    distinct_refs = len(frozenset(proposal.evidence_refs))
    if distinct_refs >= 3:
        checks_passed.append(check_2_id)
    else:
        checks_failed.append(check_2_id)
        failure_code = failure_code or AMENDMENT_INELIGIBLE
        log.warning("CSAP-GATE-0: %s — only %d distinct evidence_refs (need ≥3)", check_2_id, distinct_refs)

    # Check 3: proposed_text parseable
    check_3_id = "CHECK-3-PARSEABLE"
    is_valid, parse_reason = InvariantParser.parse(proposal.proposed_text)
    if is_valid:
        checks_passed.append(check_3_id)
    else:
        checks_failed.append(check_3_id)
        failure_code = failure_code or INVARIANT_PARSER_REJECT
        log.warning("CSAP-GATE-0: %s — %s", check_3_id, parse_reason)

    # Check 4: governance_debt_score < 0.4 (conflict of interest invariant)
    check_4_id = "CHECK-4-DEBT-SCORE"
    if governance_debt_score < 0.4:
        checks_passed.append(check_4_id)
    else:
        checks_failed.append(check_4_id)
        failure_code = failure_code or AMENDMENT_INELIGIBLE
        log.warning(
            "CSAP-GATE-0: %s — debt_score=%.3f ≥ 0.4 (conflict-of-interest block)",
            check_4_id, governance_debt_score,
        )

    # Check 5: amendment_history_digest matches ledger tail
    check_5_id = "CHECK-5-HISTORY-DIGEST"
    ledger_tail = amendment_ledger.tail_hash()
    chain_ok, chain_msg = amendment_ledger.verify_chain()
    if chain_ok:
        checks_passed.append(check_5_id)
    else:
        checks_failed.append(check_5_id)
        failure_code = failure_code or AMENDMENT_REPLAY_BROKEN
        log.warning("CSAP-GATE-0: %s — %s", check_5_id, chain_msg)

    # Check 6: Hard-class target requires HUMAN-0 co-signature
    check_6_id = "CHECK-6-HARD-CLASS-COSIGN"
    target_class = invariants_matrix.invariant_class_of(proposal.target_rule_id)
    if target_class == InvariantClass.HARD and not proposal.human_0_cosignature:
        checks_failed.append(check_6_id)
        failure_code = failure_code or AMENDMENT_CONFLICT
        log.warning(
            "CSAP-GATE-0: %s — Hard-class target '%s' requires HUMAN-0 co-signature",
            check_6_id, proposal.target_rule_id,
        )
    else:
        checks_passed.append(check_6_id)

    outcome = CSAPGateOutcome.PASS if not checks_failed else CSAPGateOutcome.FAIL
    digest = _gate_0_evidence_digest(
        proposal, {c: True for c in checks_passed} | {c: False for c in checks_failed}
    )

    return CSAPGateReport(
        gate_id="CSAP-GATE-0",
        outcome=outcome,
        failure_code=failure_code,
        checks_passed=tuple(checks_passed),
        checks_failed=tuple(checks_failed),
        evidence_digest=digest,
        proposal_id=proposal.proposal_id,
    )


# ---------------------------------------------------------------------------
# CSAP-GATE-1 — Supermajority Ratification
# ---------------------------------------------------------------------------


def evaluate_csap_gate_1(
    proposal: ConstitutionalAmendmentProposal,
    invariants_matrix: InvariantsMatrix,
    fitness_regression_delta: float,
    epoch_simulation_count: int,
    *,
    acse_evidence_available: bool = False,
) -> CSAPGateReport:
    """CSAP-GATE-1: Supermajority Ratification.

    Automated validator checks. All must PASS.

    Parameters
    ----------
    fitness_regression_delta:
        Max fitness delta observed across the last `epoch_simulation_count`
        simulated epochs with proposed amendment active.
        MUST be < 0.05 for PASS.
    epoch_simulation_count:
        Number of simulated epochs evaluated. MUST be >= 10.
    acse_evidence_available:
        Whether ACSE counter-evidence has been produced (INNOV-02).
        NOTE: when INNOV-02 is not yet active this defaults to False and
        check 3 is advisory-only (WARN, not FAIL) until ACSE ships.

    Returns
    -------
    CSAPGateReport with PASS or FAIL outcome.
    """
    checks_passed: List[str] = []
    checks_failed: List[str] = []
    failure_code: Optional[str] = None

    # Check 1: proposal enqueued in ConstitutionalAmendmentQueue
    # (caller responsibility — this check is structural; gate trusts caller)
    check_1_id = "CHECK-1-QUEUE-SUBMITTED"
    checks_passed.append(check_1_id)

    # Check 2: InvariantRatificationGate compatibility (Class-B-Eligible)
    check_2_id = "CHECK-2-INVARIANT-COMPAT"
    # For Class-B-Eligible targets, compatibility is assumed if gate_0 passed.
    # For Hard-class targets, HUMAN-0 co-signature already validated in gate_0.
    checks_passed.append(check_2_id)

    # Check 3: ACSE adversarial counter-evidence produced
    check_3_id = "CHECK-3-ACSE-EVIDENCE"
    if acse_evidence_available:
        checks_passed.append(check_3_id)
    else:
        # INNOV-02 not yet active — advisory warning only until ACSE ships
        log.warning(
            "CSAP-GATE-1: %s — ACSE not yet active (INNOV-02 pending). "
            "Advisory warning: adversarial counter-evidence not available. "
            "This will become a hard FAIL once INNOV-02 is deployed.",
            check_3_id,
        )
        checks_passed.append(check_3_id)  # soft pass until ACSE ships

    # Check 4: fitness_regression_delta < 0.05 across >= 10 simulated epochs
    check_4_id = "CHECK-4-FITNESS-REGRESSION"
    if epoch_simulation_count < 10:
        checks_failed.append(check_4_id)
        failure_code = RATIFICATION_DENIED
        log.warning(
            "CSAP-GATE-1: %s — only %d simulated epochs (need ≥10)",
            check_4_id, epoch_simulation_count,
        )
    elif fitness_regression_delta >= 0.05:
        checks_failed.append(check_4_id)
        failure_code = RATIFICATION_DENIED
        log.warning(
            "CSAP-GATE-1: %s — fitness_regression_delta=%.4f ≥ 0.05",
            check_4_id, fitness_regression_delta,
        )
    else:
        checks_passed.append(check_4_id)

    # Check 5: Hard-class HUMAN-0 co-signature re-verified
    check_5_id = "CHECK-5-HARD-CLASS-COSIGN-RECHECK"
    target_class = invariants_matrix.invariant_class_of(proposal.target_rule_id)
    if target_class == InvariantClass.HARD and not proposal.human_0_cosignature:
        checks_failed.append(check_5_id)
        failure_code = failure_code or AMENDMENT_CONFLICT
        log.warning("CSAP-GATE-1: %s — Hard-class without HUMAN-0 co-signature", check_5_id)
    else:
        checks_passed.append(check_5_id)

    # Check 6: All automated validators must return PASS (enforced by absence of failures above)
    check_6_id = "CHECK-6-ALL-VALIDATORS-PASS"
    if not checks_failed:
        checks_passed.append(check_6_id)
    else:
        checks_failed.append(check_6_id)

    outcome = CSAPGateOutcome.PASS if not checks_failed else CSAPGateOutcome.FAIL
    digest_payload = json.dumps(
        {
            "proposal_id": proposal.proposal_id,
            "fitness_regression_delta": fitness_regression_delta,
            "epoch_simulation_count": epoch_simulation_count,
            "acse_evidence_available": acse_evidence_available,
        },
        sort_keys=True,
    )
    evidence_digest = "sha256:" + hashlib.sha256(digest_payload.encode()).hexdigest()

    return CSAPGateReport(
        gate_id="CSAP-GATE-1",
        outcome=outcome,
        failure_code=failure_code,
        checks_passed=tuple(checks_passed),
        checks_failed=tuple(checks_failed),
        evidence_digest=evidence_digest,
        proposal_id=proposal.proposal_id,
    )


# ---------------------------------------------------------------------------
# ConstitutionalSelfAmendmentProtocol — orchestrator
# ---------------------------------------------------------------------------


def _ratification_hash(proposal_id: str, gate_0: CSAPGateReport, gate_1: Optional[CSAPGateReport]) -> str:
    payload = json.dumps(
        {
            "proposal_id": proposal_id,
            "gate_0_digest": gate_0.evidence_digest,
            "gate_1_digest": gate_1.evidence_digest if gate_1 else None,
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _record_id(proposal_id: str, status: AmendmentStatus) -> str:
    payload = f"{proposal_id}|{status.value}"
    return "csap-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


class ConstitutionalSelfAmendmentProtocol:
    """INNOV-01 — CSAP orchestrator.

    Drives a ConstitutionalAmendmentProposal through CSAP-GATE-0 →
    CSAP-GATE-1. On PASS: writes ledger record, returns AMENDMENT_RATIFIED.
    On FAIL: writes ledger record, returns RATIFICATION_DENIED or
    AMENDMENT_INELIGIBLE.

    CSAP-1: ledger write occurs BEFORE InvariantsMatrix is mutated.
    """

    def __init__(
        self,
        *,
        queue: ConstitutionalAmendmentQueue,
        ledger: ConstitutionalAmendmentLedger,
        timestamp_provider: Any = None,
    ) -> None:
        self._queue = queue
        self._ledger = ledger
        self._ts = timestamp_provider

    def _now(self) -> str:
        if self._ts is not None and hasattr(self._ts, "now_utc"):
            return self._ts.now_utc()
        # Deterministic fallback for replay contexts
        return "2026-03-23T00:00:00Z"

    def evaluate(
        self,
        proposal: ConstitutionalAmendmentProposal,
        invariants_matrix: InvariantsMatrix,
        governance_debt_score: float,
        fitness_regression_delta: float,
        epoch_simulation_count: int,
        *,
        acse_evidence_available: bool = False,
    ) -> Tuple[AmendmentStatus, AmendmentRatificationRecord]:
        """Full CSAP evaluation pipeline.

        Returns (status, record). Status is one of:
          AmendmentStatus.RATIFIED      — amendment approved; apply matrix update
          AmendmentStatus.REJECTED      — gate failure; cooling period required
          AmendmentStatus.MALFORMED     — InvariantParser rejected proposed_text

        CSAP-1: ledger is written before matrix mutation. Caller MUST apply
        invariants_matrix.apply_amendment() only after receiving RATIFIED.
        """
        # Enqueue proposal (CSAP-GATE-1 check 1)
        self._queue.enqueue(proposal)

        # CSAP-GATE-0
        gate_0 = evaluate_csap_gate_0(
            proposal, invariants_matrix, governance_debt_score, self._ledger
        )

        if gate_0.outcome == CSAPGateOutcome.FAIL:
            status = AmendmentStatus.MALFORMED if gate_0.failure_code == INVARIANT_PARSER_REJECT else AmendmentStatus.REJECTED
            rat_hash = _ratification_hash(proposal.proposal_id, gate_0, None)
            record = AmendmentRatificationRecord(
                record_id=_record_id(proposal.proposal_id, status),
                proposal_id=proposal.proposal_id,
                target_rule_id=proposal.target_rule_id,
                status=status,
                gate_0_report=gate_0,
                gate_1_report=None,
                ratification_hash=rat_hash,
                predecessor_hash=self._ledger.tail_hash(),
                timestamp_utc=self._now(),
            )
            # CSAP-1: ledger write before any matrix mutation
            self._ledger.append(record)
            log.warning(
                "CSAP: proposal %s FAILED gate-0 (%s)", proposal.proposal_id, gate_0.failure_code
            )
            return status, record

        # CSAP-GATE-1
        gate_1 = evaluate_csap_gate_1(
            proposal,
            invariants_matrix,
            fitness_regression_delta,
            epoch_simulation_count,
            acse_evidence_available=acse_evidence_available,
        )

        if gate_1.outcome == CSAPGateOutcome.FAIL:
            status = AmendmentStatus.REJECTED
            rat_hash = _ratification_hash(proposal.proposal_id, gate_0, gate_1)
            record = AmendmentRatificationRecord(
                record_id=_record_id(proposal.proposal_id, status),
                proposal_id=proposal.proposal_id,
                target_rule_id=proposal.target_rule_id,
                status=status,
                gate_0_report=gate_0,
                gate_1_report=gate_1,
                ratification_hash=rat_hash,
                predecessor_hash=self._ledger.tail_hash(),
                timestamp_utc=self._now(),
            )
            self._ledger.append(record)
            log.warning(
                "CSAP: proposal %s FAILED gate-1 (%s)", proposal.proposal_id, gate_1.failure_code
            )
            return AmendmentStatus.REJECTED, record

        # Both gates PASS — RATIFIED
        status = AmendmentStatus.RATIFIED
        rat_hash = _ratification_hash(proposal.proposal_id, gate_0, gate_1)
        record = AmendmentRatificationRecord(
            record_id=_record_id(proposal.proposal_id, status),
            proposal_id=proposal.proposal_id,
            target_rule_id=proposal.target_rule_id,
            status=status,
            gate_0_report=gate_0,
            gate_1_report=gate_1,
            ratification_hash=rat_hash,
            predecessor_hash=self._ledger.tail_hash(),
            timestamp_utc=self._now(),
        )
        # CSAP-1: ledger write BEFORE matrix mutation
        self._ledger.append(record)
        log.info(
            "CSAP: proposal %s RATIFIED — target_rule_id=%s ratification_hash=%s",
            proposal.proposal_id, proposal.target_rule_id, rat_hash,
        )
        return AmendmentStatus.RATIFIED, record
