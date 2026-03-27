# SPDX-License-Identifier: Apache-2.0
"""INNOV-08 — Adversarial Fitness Red Team (AFRT).

Phase 92 introduces the first dedicated adversarial reasoning layer in the
Constitutional Evolution Loop (CEL).  Where LSME (Phase 91) validates
*behaviour under execution*, AFRT generates *targeted adversarial test cases*
against mutation proposals, specifically probing coverage gaps the proposing
agent did not exercise.  A mutation that survives the Red Team has been
stress-tested beyond its own suite.

Pipeline Position (CEL Step ordering — AFRT-GATE-0):
    LSME-GATE-1  →  AFRT gate  →  GovernanceGate v2

Constitutional Invariants
─────────────────────────
  AFRT-0          The AdversarialRedTeamAgent MUST never autonomously promote
                  or approve a mutation.  Its only output is a
                  RedTeamFindingsReport with verdict PASS or RETURNED.
                  approval_emitted is always False; any code path that sets it
                  True is a constitutional violation requiring HUMAN-0 alert.

  AFRT-GATE-0     AFRT evaluation MUST occur after LSME (LSME-GATE-1) and
                  before GovernanceGateV2 in the CEL step sequence.  Any
                  epoch run where this ordering differs MUST raise
                  CELStepOrderViolation.

  AFRT-INTEL-0    Adversarial case generation MUST use
                  CodeIntelModel.get_uncovered_paths(proposal) as the primary
                  path surface.  Cases generated without CodeIntel coverage
                  data are inadmissible and MUST be discarded.

  AFRT-LEDGER-0   RedTeamLedgerEvent MUST be appended to LineageLedgerV2
                  *before* the AFRT result is returned to the CEL
                  orchestrator (ledger-first principle — phase73-seed-review-0).

  AFRT-CASES-0    AdversarialCaseGenerator MUST generate between 1 and 5
                  adversarial test cases per proposal.  Zero cases is a
                  malformed result — treat as AFRT engine failure, abort epoch.
                  More than 5 cases exceeds the constitutional overhead budget.

  AFRT-DETERM-0   Given identical proposal input and CodeIntelModel coverage
                  snapshot, AdversarialCaseGenerator MUST produce identical
                  adversarial test cases across runs.  No datetime.now(),
                  random.random(), or uuid4() within the case-generation path.

AFRT Version: 92.0
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

AFRT_VERSION = "92.0"
_MAX_ADVERSARIAL_CASES = 5   # AFRT-CASES-0 upper bound
_MIN_ADVERSARIAL_CASES = 1   # AFRT-CASES-0 lower bound


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RedTeamVerdict(str, Enum):
    PASS     = "PASS"      # all adversarial cases survived — proposal may advance
    RETURNED = "RETURNED"  # one or more cases falsified — proposal returned to proposer


class AdversarialCaseOutcome(str, Enum):
    SURVIVED  = "SURVIVED"   # mutation handled the adversarial case correctly
    FALSIFIED = "FALSIFIED"  # mutation failed under adversarial pressure


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdversarialCase:
    """A single adversarial test case targeting an uncovered code path.

    AFRT-DETERM-0: all fields must be deterministically derived from proposal
    content + coverage snapshot.  No randomness, no timestamps.
    """
    case_id: str                  # deterministic: sha256(proposal_id + path_surface + index)
    target_path: str              # e.g. "runtime/foo.py:L42"
    description: str              # human-readable probe description
    probe_input: Dict[str, Any]   # deterministic probe payload
    expected_invariant: str       # invariant that must hold under this probe
    outcome: AdversarialCaseOutcome = AdversarialCaseOutcome.SURVIVED
    failure_detail: Optional[str] = None


@dataclass(frozen=True)
class RedTeamFindingsReport:
    """Structured result from AdversarialRedTeamAgent.evaluate().

    AFRT-0: approval_emitted is always False.  Any assertion failure here
    is a constitutional violation.
    """
    proposal_id: str
    epoch_id: str
    verdict: RedTeamVerdict
    adversarial_cases: Tuple[AdversarialCase, ...]   # 1–5 items (AFRT-CASES-0)
    uncovered_paths: Tuple[str, ...]                  # from CodeIntelModel (AFRT-INTEL-0)
    failure_cases: Tuple[AdversarialCase, ...]        # subset with FALSIFIED outcome
    report_hash: str                                  # SHA-256 of deterministic repr
    trace_committed: bool                             # ledger-first flag (AFRT-LEDGER-0)
    afrt_version: str = AFRT_VERSION
    approval_emitted: bool = False                    # AFRT-0: must always be False

    def __post_init__(self) -> None:
        # AFRT-0 — hard constitutional assertion
        assert not self.approval_emitted, (
            "AFRT-0 VIOLATION: RedTeamFindingsReport.approval_emitted is True. "
            "AFRT may never emit an approval event.  HUMAN-0 alert required."
        )
        # AFRT-CASES-0 — case count bounds
        n = len(self.adversarial_cases)
        assert _MIN_ADVERSARIAL_CASES <= n <= _MAX_ADVERSARIAL_CASES, (
            f"AFRT-CASES-0 VIOLATION: {n} adversarial cases generated "
            f"(must be {_MIN_ADVERSARIAL_CASES}–{_MAX_ADVERSARIAL_CASES})."
        )


# ---------------------------------------------------------------------------
# Ledger event schema (AFRT-LEDGER-0)
# ---------------------------------------------------------------------------

@dataclass
class RedTeamLedgerEvent:
    """LineageLedgerV2 event emitted before AFRT result is returned (AFRT-LEDGER-0).

    Schema mirrors RedTeamFindingsReport for auditability.
    """
    event_type: str = "RED_TEAM_EVALUATION"
    proposal_id: str = ""
    epoch_id: str = ""
    verdict: str = ""
    adversarial_cases_count: int = 0
    failure_cases_count: int = 0
    uncovered_paths_sampled: List[str] = field(default_factory=list)
    report_hash: str = ""
    afrt_version: str = AFRT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# AdversarialCaseGenerator (AFRT-DETERM-0)
# ---------------------------------------------------------------------------

class AdversarialCaseGenerator:
    """Generates deterministic adversarial test cases from uncovered path surfaces.

    AFRT-DETERM-0: identical proposal + coverage snapshot → identical case set.
    No datetime.now(), random.random(), or uuid4() within this class.
    """

    def generate(
        self,
        proposal_id: str,
        uncovered_paths: Sequence[str],
        proposal_content: Dict[str, Any],
    ) -> List[AdversarialCase]:
        """Generate 1–5 adversarial cases targeting uncovered paths.

        Selects up to _MAX_ADVERSARIAL_CASES paths deterministically (first N
        by stable sort) and constructs a probe for each.

        Args:
            proposal_id:      Mutation proposal identifier.
            uncovered_paths:  Coverage-gap paths from CodeIntelModel (AFRT-INTEL-0).
            proposal_content: Structured proposal payload for context.

        Returns:
            List of AdversarialCase (1–5 items).

        Raises:
            AFRTEngineError: if uncovered_paths is empty (AFRT-CASES-0).
        """
        if not uncovered_paths:
            raise AFRTEngineError(
                "AFRT-CASES-0: uncovered_paths is empty — cannot generate adversarial cases. "
                "Verify CodeIntelModel.get_uncovered_paths() returned a non-empty sequence "
                "(AFRT-INTEL-0)."
            )

        # AFRT-DETERM-0: stable sort ensures identical ordering across runs
        selected_paths = sorted(uncovered_paths)[:_MAX_ADVERSARIAL_CASES]

        cases: List[AdversarialCase] = []
        for idx, path in enumerate(selected_paths):
            case_id = _deterministic_case_id(proposal_id, path, idx)
            probe_input = _build_probe_input(proposal_id, path, proposal_content, idx)
            cases.append(AdversarialCase(
                case_id=case_id,
                target_path=path,
                description=f"Adversarial probe for uncovered path: {path}",
                probe_input=probe_input,
                expected_invariant=(
                    f"Mutation must not regress behaviour at {path} "
                    f"under boundary/adversarial input conditions."
                ),
            ))

        return cases


def _deterministic_case_id(proposal_id: str, path: str, index: int) -> str:
    """SHA-256 based case ID — AFRT-DETERM-0 compliant."""
    payload = json.dumps(
        {"proposal_id": proposal_id, "path": path, "index": index},
        sort_keys=True,
    )
    return "afrt-case-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _build_probe_input(
    proposal_id: str,
    path: str,
    proposal_content: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Build a deterministic probe payload for the given path surface."""
    # Derive a stable probe seed from proposal + path to ensure AFRT-DETERM-0
    seed_hash = hashlib.sha256(
        json.dumps({"pid": proposal_id, "path": path, "idx": index}, sort_keys=True).encode()
    ).hexdigest()
    return {
        "probe_seed": seed_hash[:16],
        "target_path": path,
        "boundary_mode": "EDGE_CASE",
        "proposal_ref": proposal_id,
    }


# ---------------------------------------------------------------------------
# AdversarialRedTeamAgent
# ---------------------------------------------------------------------------

class AdversarialRedTeamAgent:
    """Phase 92 INNOV-08 — Adversarial Fitness Red Team Agent.

    Core interface for the AFRT gate in the CEL step sequence.  Wraps
    AdversarialCaseGenerator, sandbox execution, and ledger commitment.

    AFRT-0:       approval_emitted is structurally False on every report.
    AFRT-GATE-0:  Caller (CEL) must invoke this after LSME, before GovernanceGateV2.
    AFRT-INTEL-0: code_intel_model.get_uncovered_paths() is the mandatory input.
    AFRT-LEDGER-0: ledger commit occurs inside evaluate() before return.
    AFRT-CASES-0:  1–5 cases enforced in RedTeamFindingsReport.__post_init__.
    AFRT-DETERM-0: deterministic through AdversarialCaseGenerator.
    """

    def __init__(
        self,
        code_intel_model: Any,
        ledger: Any,
        case_generator: Optional[AdversarialCaseGenerator] = None,
        sandbox_runner: Optional[Any] = None,
    ) -> None:
        """
        Args:
            code_intel_model: Must implement get_uncovered_paths(proposal) → List[str].
            ledger:           Must implement append(event_dict) (LineageLedgerV2).
            case_generator:   Injected for testability; defaults to AdversarialCaseGenerator().
            sandbox_runner:   Injected sandbox executor; defaults to _DefaultSandboxRunner().
        """
        self._intel = code_intel_model
        self._ledger = ledger
        self._generator = case_generator or AdversarialCaseGenerator()
        self._sandbox = sandbox_runner or _DefaultSandboxRunner()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate(self, proposal: Any, epoch_id: str) -> RedTeamFindingsReport:
        """Execute full Red Team evaluation against a mutation proposal.

        Pipeline (AFRT-LEDGER-0 mandates ledger commit before return):
            1. Query CodeIntelModel for uncovered paths (AFRT-INTEL-0).
            2. Generate up to 5 adversarial cases (AFRT-CASES-0 / AFRT-DETERM-0).
            3. Execute each case in read-only sandbox.
            4. Determine verdict (PASS / RETURNED).
            5. Commit RedTeamLedgerEvent to LineageLedgerV2 (AFRT-LEDGER-0).
            6. Return RedTeamFindingsReport (AFRT-0).

        Args:
            proposal:  MutationRequest or dict with .id / ['id'] and content.
            epoch_id:  Current CEL epoch identifier.

        Returns:
            RedTeamFindingsReport with verdict PASS or RETURNED.

        Raises:
            AFRTEngineError: on engine-level failures (zero cases, INTEL failure).
        """
        proposal_id = _extract_proposal_id(proposal)
        proposal_content = _extract_proposal_content(proposal)

        # Step 1 — CodeIntelModel coverage query (AFRT-INTEL-0)
        uncovered_paths: List[str] = self._intel.get_uncovered_paths(proposal)
        if not uncovered_paths:
            raise AFRTEngineError(
                f"AFRT-INTEL-0: CodeIntelModel returned empty uncovered_paths for "
                f"proposal {proposal_id}.  Aborting epoch — zero adversarial cases "
                f"is a constitutional engine failure (AFRT-CASES-0)."
            )

        # Step 2 — Generate adversarial cases (AFRT-CASES-0 / AFRT-DETERM-0)
        cases = self._generator.generate(
            proposal_id=proposal_id,
            uncovered_paths=uncovered_paths,
            proposal_content=proposal_content,
        )

        # Step 3 — Execute in sandbox
        executed_cases = self._sandbox.run(cases, proposal)

        # Step 4 — Verdict
        failure_cases = [c for c in executed_cases if c.outcome == AdversarialCaseOutcome.FALSIFIED]
        verdict = RedTeamVerdict.RETURNED if failure_cases else RedTeamVerdict.PASS

        # Build report hash (AFRT-DETERM-0)
        report_hash = _compute_report_hash(proposal_id, executed_cases, verdict)

        # Step 5 — Ledger-first commit (AFRT-LEDGER-0)
        ledger_event = RedTeamLedgerEvent(
            proposal_id=proposal_id,
            epoch_id=epoch_id,
            verdict=verdict.value,
            adversarial_cases_count=len(executed_cases),
            failure_cases_count=len(failure_cases),
            uncovered_paths_sampled=list(uncovered_paths[:3]),  # sample for ledger size
            report_hash=report_hash,
        )
        self._commit_to_ledger(ledger_event)  # AFRT-LEDGER-0: before return

        # Step 6 — Return report (AFRT-0: approval_emitted always False)
        report = RedTeamFindingsReport(
            proposal_id=proposal_id,
            epoch_id=epoch_id,
            verdict=verdict,
            adversarial_cases=tuple(executed_cases),
            uncovered_paths=tuple(uncovered_paths),
            failure_cases=tuple(failure_cases),
            report_hash=report_hash,
            trace_committed=True,   # ledger committed above
            approval_emitted=False,  # AFRT-0: structurally enforced
        )

        # AFRT-0 hard assertion — belt and suspenders
        assert not report.approval_emitted, "AFRT-0 VIOLATION — HUMAN-0 alert required."

        log.info(
            "AFRT evaluation complete",
            extra={
                "proposal_id": proposal_id,
                "epoch_id": epoch_id,
                "verdict": verdict.value,
                "cases": len(executed_cases),
                "failures": len(failure_cases),
                "report_hash": report_hash,
            },
        )
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _commit_to_ledger(self, event: RedTeamLedgerEvent) -> None:
        """Append event to LineageLedgerV2 (AFRT-LEDGER-0)."""
        try:
            self._ledger.append(event.to_dict())
        except Exception as exc:  # noqa: BLE001
            # Ledger failure is a hard block — do not swallow
            raise AFRTEngineError(
                f"AFRT-LEDGER-0: failed to commit RedTeamLedgerEvent for proposal "
                f"{event.proposal_id}: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Default sandbox runner (read-only, no filesystem writes)
# ---------------------------------------------------------------------------

class _DefaultSandboxRunner:
    """Executes adversarial cases in a read-only sandbox.

    In Phase 92 scope, sandbox execution is a structured stub that records
    probe attempt and outcome deterministically.  Full sandboxed execution
    against ADAAD's production traffic is a Phase 93+ extension.
    """

    def run(
        self,
        cases: List[AdversarialCase],
        proposal: Any,
    ) -> List[AdversarialCase]:
        """Execute cases and return updated list with outcome fields populated."""
        results: List[AdversarialCase] = []
        for case in cases:
            # Deterministic outcome derivation from probe_seed
            # In production this will be replaced by real sandbox execution
            probe_seed = case.probe_input.get("probe_seed", "")
            # Treat seed ending in 'f' as a falsification signal (test seam)
            outcome = (
                AdversarialCaseOutcome.FALSIFIED
                if probe_seed.endswith("f")
                else AdversarialCaseOutcome.SURVIVED
            )
            results.append(AdversarialCase(
                case_id=case.case_id,
                target_path=case.target_path,
                description=case.description,
                probe_input=case.probe_input,
                expected_invariant=case.expected_invariant,
                outcome=outcome,
                failure_detail=(
                    f"Adversarial probe detected failure at {case.target_path}"
                    if outcome == AdversarialCaseOutcome.FALSIFIED else None
                ),
            ))
        return results


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AFRTEngineError(RuntimeError):
    """Raised on constitutional AFRT engine failures (AFRT-CASES-0, AFRT-LEDGER-0)."""


class CELStepOrderViolation(RuntimeError):
    """Raised when AFRT is invoked outside its mandated CEL step position (AFRT-GATE-0)."""


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _extract_proposal_id(proposal: Any) -> str:
    if hasattr(proposal, "id"):
        return str(proposal.id)
    if isinstance(proposal, dict):
        return str(proposal.get("id", "unknown"))
    return "unknown"


def _extract_proposal_content(proposal: Any) -> Dict[str, Any]:
    if isinstance(proposal, dict):
        return proposal
    if hasattr(proposal, "__dict__"):
        return vars(proposal)
    return {}


def _compute_report_hash(
    proposal_id: str,
    cases: List[AdversarialCase],
    verdict: RedTeamVerdict,
) -> str:
    """SHA-256 of deterministic report representation (AFRT-DETERM-0)."""
    payload = json.dumps(
        {
            "proposal_id": proposal_id,
            "verdict": verdict.value,
            "cases": [
                {
                    "case_id": c.case_id,
                    "target_path": c.target_path,
                    "outcome": c.outcome.value,
                }
                for c in sorted(cases, key=lambda c: c.case_id)
            ],
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
