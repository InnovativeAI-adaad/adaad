# SPDX-License-Identifier: Apache-2.0
"""Phase 89 — INNOV-05 · Autonomous Organ Emergence Protocol (AOEP).

Test ID format: T89-AOEP-NN

20 tests covering:
  - T89-AOEP-01..04  Gap signal construction and CapabilityGapSignal types
  - T89-AOEP-05..08  GATE-0 pass path and OrganProposal structure
  - T89-AOEP-09..12  GATE-0 block paths (unqualified gap, addressable, insufficient)
  - T89-AOEP-13..15  GATE-0 schema validation (incomplete proposal, manifest conflict)
  - T89-AOEP-16..18  GATE-1 pass path and RatificationRecord integrity
  - T89-AOEP-19..20  GATE-1 AOEP-0 enforcement (human_0_signature non-bypassable)
"""

from __future__ import annotations

import hashlib

import pytest

from runtime.evolution.aoep_protocol import (
    AOEP_GAP_ADDRESSABLE,
    AOEP_GAP_UNQUALIFIED,
    AOEP_HUMAN_0_BLOCKED,
    AOEP_INSUFFICIENT_MEMORY,
    AOEP_INSUFFICIENT_PATTERNS,
    AOEP_MANIFEST_CONFLICT,
    AOEP_MIN_FAILURE_PATTERNS,
    AOEP_MIN_GAP_EPOCHS,
    AOEP_MIN_MEMORY_EPOCHS,
    AOEP_PROPOSAL_INCOMPLETE,
    AOEP_RATIFICATION_HASH_MISMATCH,
    AOEP_SIGNATURE_MISSING,
    AOEP_VERSION,
    AOEPCooldownTracker,
    AOEPGateResult,
    AOEPOutcome,
    CapabilityGapSignal,
    FailurePatternSummary,
    Human0RatificationPayload,
    OrganManifestEntry,
    OrganProposal,
    ProposalStatus,
    RatificationRecord,
    build_capability_gap_signal,
    evaluate_aoep_gate_0,
    evaluate_aoep_gate_1,
    gate_result_to_ledger_payload,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

GAP_DESC = (
    "Mutations that alter async runtime scheduling are never evaluated for "
    "concurrency safety — no existing organ checks thread-safety invariants "
    "across mutation boundaries."
)
ORGAN_PURPOSE = (
    "The ConcurrencySafetyOrgan evaluates all mutations that modify async "
    "runtime scheduling for thread-safety invariant violations before sandbox."
)
EPOCH_ID = "epoch-042"
OPERATOR_ID = "dustin.reid"
TIMESTAMP = "2026-03-23T00:00:00Z"


def _gap(sustained: int = AOEP_MIN_GAP_EPOCHS) -> CapabilityGapSignal:
    return build_capability_gap_signal(
        gap_description=GAP_DESC,
        sustained_epochs=sustained,
        affected_mutation_classes=frozenset({"async_mutation", "scheduling"}),
        candidate_organ_purpose=ORGAN_PURPOSE,
    )


def _patterns(gap_id: str, count: int = AOEP_MIN_FAILURE_PATTERNS) -> list:
    return [
        FailurePatternSummary(
            pattern_id=f"FP-{i:03d}",
            occurrence_count=5 + i,
            attributed_gap_id=gap_id,
            evidence_epoch_ids=(f"epoch-{i:03d}", f"epoch-{i+1:03d}"),
        )
        for i in range(count)
    ]


def _manifest(organ_ids: list | None = None) -> list:
    if organ_ids is None:
        return []
    return [
        OrganManifestEntry(
            organ_id=oid,
            purpose=f"Purpose of {oid}",
            input_types=frozenset({"MutationCandidate"}),
            output_types=frozenset({"FitnessScore"}),
            capability_ids=frozenset({"fitness_eval"}),
        )
        for oid in organ_ids
    ]


def _gate0_pass(
    organ_id: str = "concurrency_safety_organ",
    gap: CapabilityGapSignal | None = None,
    memory: int = AOEP_MIN_MEMORY_EPOCHS,
) -> AOEPGateResult:
    g = gap or _gap()
    return evaluate_aoep_gate_0(
        gap_signal=g,
        failure_patterns=_patterns(g.gap_id),
        organ_manifest=_manifest(),
        memory_epoch_count=memory,
        proposed_organ_id=organ_id,
        proposed_purpose=ORGAN_PURPOSE,
        proposed_inputs=["MutationCandidate", "SchedulingContext"],
        proposed_outputs=["ConcurrencyVerdictReport"],
        proposed_invariants=["CONC-0", "CONC-1"],
        proposed_dependencies=["SandboxOrgan"],
        epoch_id=EPOCH_ID,
    )


def _ratification_payload(proposal: OrganProposal) -> Human0RatificationPayload:
    rat_hash = hashlib.sha256(
        (proposal.proposal_id + OPERATOR_ID + TIMESTAMP).encode()
    ).hexdigest()
    return Human0RatificationPayload(
        proposal_id=proposal.proposal_id,
        ratification_hash=rat_hash,
        operator_id=OPERATOR_ID,
        timestamp=TIMESTAMP,
        human_0_signature="Dustin L. Reid — AOEP INNOV-05 ratified 2026-03-23",
        predecessor_hash="a" * 64,
    )


# ---------------------------------------------------------------------------
# T89-AOEP-01 — build_capability_gap_signal returns correct types
# ---------------------------------------------------------------------------


def test_t89_aoep_01_gap_signal_types():
    """T89-AOEP-01: build_capability_gap_signal returns CapabilityGapSignal."""
    gap = _gap()
    assert isinstance(gap, CapabilityGapSignal)
    assert gap.gap_id.startswith("GAP-")
    assert len(gap.gap_hash) == 64
    assert gap.sustained_epochs == AOEP_MIN_GAP_EPOCHS


# ---------------------------------------------------------------------------
# T89-AOEP-02 — gap_id is deterministic
# ---------------------------------------------------------------------------


def test_t89_aoep_02_gap_signal_deterministic():
    """T89-AOEP-02: identical inputs → identical gap_id and gap_hash."""
    g1 = _gap()
    g2 = _gap()
    assert g1.gap_id == g2.gap_id
    assert g1.gap_hash == g2.gap_hash


# ---------------------------------------------------------------------------
# T89-AOEP-03 — gap_hash changes with description
# ---------------------------------------------------------------------------


def test_t89_aoep_03_gap_hash_sensitive_to_description():
    """T89-AOEP-03: different gap_description → different gap_id and gap_hash."""
    g1 = build_capability_gap_signal(
        gap_description="Alpha gap description for testing purposes only.",
        sustained_epochs=10,
        affected_mutation_classes=frozenset({"A"}),
        candidate_organ_purpose="Organ alpha purpose statement here.",
    )
    g2 = build_capability_gap_signal(
        gap_description="Beta gap description — completely different text.",
        sustained_epochs=10,
        affected_mutation_classes=frozenset({"A"}),
        candidate_organ_purpose="Organ alpha purpose statement here.",
    )
    assert g1.gap_hash != g2.gap_hash
    assert g1.gap_id != g2.gap_id


# ---------------------------------------------------------------------------
# T89-AOEP-04 — FailurePatternSummary stores correct evidence
# ---------------------------------------------------------------------------


def test_t89_aoep_04_failure_pattern_summary():
    """T89-AOEP-04: FailurePatternSummary stores attribution and epoch evidence."""
    gap = _gap()
    patterns = _patterns(gap.gap_id, 3)
    assert len(patterns) == 3
    assert all(fp.attributed_gap_id == gap.gap_id for fp in patterns)
    assert len({fp.pattern_id for fp in patterns}) == 3


# ---------------------------------------------------------------------------
# T89-AOEP-05 — GATE-0 passes and returns GAP_QUALIFIED
# ---------------------------------------------------------------------------


def test_t89_aoep_05_gate0_passes_qualified():
    """T89-AOEP-05: valid inputs → GAP_QUALIFIED outcome."""
    result = _gate0_pass()
    assert result.outcome == AOEPOutcome.GAP_QUALIFIED
    assert not result.failure_codes
    assert result.proposal is not None


# ---------------------------------------------------------------------------
# T89-AOEP-06 — OrganProposal has PENDING_HUMAN_0 status
# ---------------------------------------------------------------------------


def test_t89_aoep_06_proposal_pending_human0():
    """T89-AOEP-06: OrganProposal status is PENDING_HUMAN_0 after GATE-0."""
    result = _gate0_pass()
    assert result.proposal is not None
    assert result.proposal.status == ProposalStatus.PENDING_HUMAN_0
    assert result.proposal.human_0_required is True


# ---------------------------------------------------------------------------
# T89-AOEP-07 — proposal_id and proposal_hash are deterministic
# ---------------------------------------------------------------------------


def test_t89_aoep_07_proposal_deterministic():
    """T89-AOEP-07: identical inputs → identical proposal_id and proposal_hash."""
    r1 = _gate0_pass()
    r2 = _gate0_pass()
    assert r1.proposal.proposal_id == r2.proposal.proposal_id
    assert r1.proposal.proposal_hash == r2.proposal.proposal_hash


# ---------------------------------------------------------------------------
# T89-AOEP-08 — proposal contains gap signal and failure evidence
# ---------------------------------------------------------------------------


def test_t89_aoep_08_proposal_contains_evidence():
    """T89-AOEP-08: OrganProposal embeds gap_signal and failure_evidence."""
    result = _gate0_pass()
    p = result.proposal
    assert isinstance(p.gap_signal, CapabilityGapSignal)
    assert len(p.failure_evidence) == AOEP_MIN_FAILURE_PATTERNS
    assert all(isinstance(fp, FailurePatternSummary) for fp in p.failure_evidence)


# ---------------------------------------------------------------------------
# T89-AOEP-09 — GATE-0 blocked: insufficient sustained epochs
# ---------------------------------------------------------------------------


def test_t89_aoep_09_gate0_blocked_insufficient_epochs():
    """T89-AOEP-09: sustained_epochs < AOEP_MIN_GAP_EPOCHS → AOEP_GAP_UNQUALIFIED."""
    gap = _gap(sustained=AOEP_MIN_GAP_EPOCHS - 1)
    result = evaluate_aoep_gate_0(
        gap_signal=gap,
        failure_patterns=_patterns(gap.gap_id),
        organ_manifest=_manifest(),
        memory_epoch_count=AOEP_MIN_MEMORY_EPOCHS,
        proposed_organ_id="test_organ",
        proposed_purpose=ORGAN_PURPOSE,
        proposed_inputs=["A"],
        proposed_outputs=["B"],
        proposed_invariants=["INV-0"],
        proposed_dependencies=[],
        epoch_id=EPOCH_ID,
    )
    assert result.outcome == AOEPOutcome.BLOCKED
    assert AOEP_GAP_UNQUALIFIED in result.failure_codes


# ---------------------------------------------------------------------------
# T89-AOEP-10 — GATE-0 blocked: insufficient failure patterns
# ---------------------------------------------------------------------------


def test_t89_aoep_10_gate0_blocked_insufficient_patterns():
    """T89-AOEP-10: < AOEP_MIN_FAILURE_PATTERNS patterns → AOEP_INSUFFICIENT_PATTERNS."""
    gap = _gap()
    result = evaluate_aoep_gate_0(
        gap_signal=gap,
        failure_patterns=_patterns(gap.gap_id, AOEP_MIN_FAILURE_PATTERNS - 1),
        organ_manifest=_manifest(),
        memory_epoch_count=AOEP_MIN_MEMORY_EPOCHS,
        proposed_organ_id="test_organ",
        proposed_purpose=ORGAN_PURPOSE,
        proposed_inputs=["A"],
        proposed_outputs=["B"],
        proposed_invariants=["INV-0"],
        proposed_dependencies=[],
        epoch_id=EPOCH_ID,
    )
    assert result.outcome == AOEPOutcome.BLOCKED
    assert AOEP_INSUFFICIENT_PATTERNS in result.failure_codes


# ---------------------------------------------------------------------------
# T89-AOEP-11 — GATE-0 blocked: gap addressable by existing organ
# ---------------------------------------------------------------------------


def test_t89_aoep_11_gate0_blocked_gap_addressable():
    """T89-AOEP-11: existing organ covers gap's capability surface → AOEP_GAP_ADDRESSABLE."""
    gap = _gap()
    # Create organ that covers the gap's affected mutation classes
    covering_organ = OrganManifestEntry(
        organ_id="existing_async_organ",
        purpose="Handles async mutation safety checks.",
        input_types=frozenset({"MutationCandidate"}),
        output_types=frozenset({"SafetyReport"}),
        capability_ids=frozenset({"async_mutation"}),  # overlaps with gap
    )
    result = evaluate_aoep_gate_0(
        gap_signal=gap,
        failure_patterns=_patterns(gap.gap_id),
        organ_manifest=[covering_organ],
        memory_epoch_count=AOEP_MIN_MEMORY_EPOCHS,
        proposed_organ_id="test_organ",
        proposed_purpose=ORGAN_PURPOSE,
        proposed_inputs=["A"],
        proposed_outputs=["B"],
        proposed_invariants=["INV-0"],
        proposed_dependencies=[],
        epoch_id=EPOCH_ID,
    )
    assert result.outcome == AOEPOutcome.BLOCKED
    assert AOEP_GAP_ADDRESSABLE in result.failure_codes


# ---------------------------------------------------------------------------
# T89-AOEP-12 — GATE-0 blocked: insufficient memory epochs
# ---------------------------------------------------------------------------


def test_t89_aoep_12_gate0_blocked_insufficient_memory():
    """T89-AOEP-12: memory_epoch_count < AOEP_MIN_MEMORY_EPOCHS → AOEP_INSUFFICIENT_MEMORY."""
    gap = _gap()
    result = evaluate_aoep_gate_0(
        gap_signal=gap,
        failure_patterns=_patterns(gap.gap_id),
        organ_manifest=_manifest(),
        memory_epoch_count=AOEP_MIN_MEMORY_EPOCHS - 1,
        proposed_organ_id="test_organ",
        proposed_purpose=ORGAN_PURPOSE,
        proposed_inputs=["A"],
        proposed_outputs=["B"],
        proposed_invariants=["INV-0"],
        proposed_dependencies=[],
        epoch_id=EPOCH_ID,
    )
    assert result.outcome == AOEPOutcome.BLOCKED
    assert AOEP_INSUFFICIENT_MEMORY in result.failure_codes


# ---------------------------------------------------------------------------
# T89-AOEP-13 — GATE-0 blocked: incomplete proposal (empty organ_id)
# ---------------------------------------------------------------------------


def test_t89_aoep_13_gate0_blocked_incomplete_proposal():
    """T89-AOEP-13: empty organ_id → AOEP_PROPOSAL_INCOMPLETE."""
    gap = _gap()
    result = evaluate_aoep_gate_0(
        gap_signal=gap,
        failure_patterns=_patterns(gap.gap_id),
        organ_manifest=_manifest(),
        memory_epoch_count=AOEP_MIN_MEMORY_EPOCHS,
        proposed_organ_id="",  # invalid
        proposed_purpose=ORGAN_PURPOSE,
        proposed_inputs=["A"],
        proposed_outputs=["B"],
        proposed_invariants=["INV-0"],
        proposed_dependencies=[],
        epoch_id=EPOCH_ID,
    )
    assert result.outcome == AOEPOutcome.BLOCKED
    assert AOEP_PROPOSAL_INCOMPLETE in result.failure_codes


# ---------------------------------------------------------------------------
# T89-AOEP-14 — GATE-0 blocked: manifest conflict (organ_id already exists)
# ---------------------------------------------------------------------------


def test_t89_aoep_14_gate0_blocked_manifest_conflict():
    """T89-AOEP-14: proposed organ_id matches existing organ → AOEP_MANIFEST_CONFLICT."""
    gap = _gap()
    result = evaluate_aoep_gate_0(
        gap_signal=gap,
        failure_patterns=_patterns(gap.gap_id),
        organ_manifest=_manifest(["existing_organ"]),
        memory_epoch_count=AOEP_MIN_MEMORY_EPOCHS,
        proposed_organ_id="existing_organ",  # conflict
        proposed_purpose=ORGAN_PURPOSE,
        proposed_inputs=["A"],
        proposed_outputs=["B"],
        proposed_invariants=["INV-0"],
        proposed_dependencies=[],
        epoch_id=EPOCH_ID,
    )
    assert result.outcome == AOEPOutcome.BLOCKED
    assert AOEP_MANIFEST_CONFLICT in result.failure_codes


# ---------------------------------------------------------------------------
# T89-AOEP-15 — GATE-0 result is always an AOEPGateResult
# ---------------------------------------------------------------------------


def test_t89_aoep_15_gate0_always_returns_gate_result():
    """T89-AOEP-15: evaluate_aoep_gate_0 always returns AOEPGateResult."""
    result = _gate0_pass()
    assert isinstance(result, AOEPGateResult)
    assert result.gate_id == "AOEP-GATE-0"
    assert isinstance(result.failure_codes, tuple)
    assert len(result.result_hash) == 64


# ---------------------------------------------------------------------------
# T89-AOEP-16 — GATE-1 passes with valid HUMAN-0 payload
# ---------------------------------------------------------------------------


def test_t89_aoep_16_gate1_approved():
    """T89-AOEP-16: valid Human0RatificationPayload → AOEP_APPROVED."""
    gate0 = _gate0_pass()
    proposal = gate0.proposal
    payload = _ratification_payload(proposal)
    result = evaluate_aoep_gate_1(proposal, payload)
    assert result.outcome == AOEPOutcome.APPROVED
    assert not result.failure_codes
    assert result.ratification_record is not None


# ---------------------------------------------------------------------------
# T89-AOEP-17 — RatificationRecord has correct structure
# ---------------------------------------------------------------------------


def test_t89_aoep_17_ratification_record_structure():
    """T89-AOEP-17: RatificationRecord fields are correct after GATE-1 pass."""
    gate0 = _gate0_pass()
    proposal = gate0.proposal
    payload = _ratification_payload(proposal)
    result = evaluate_aoep_gate_1(proposal, payload)
    rec = result.ratification_record
    assert isinstance(rec, RatificationRecord)
    assert rec.proposal_id == proposal.proposal_id
    assert rec.organ_id == proposal.organ_id
    assert rec.outcome == AOEPOutcome.APPROVED
    assert rec.operator_id == OPERATOR_ID
    assert len(rec.record_hash) == 64


# ---------------------------------------------------------------------------
# T89-AOEP-18 — RatificationRecord.record_hash is deterministic
# ---------------------------------------------------------------------------


def test_t89_aoep_18_record_hash_deterministic():
    """T89-AOEP-18: identical inputs → identical record_hash."""
    gate0 = _gate0_pass()
    proposal = gate0.proposal
    payload = _ratification_payload(proposal)
    r1 = evaluate_aoep_gate_1(proposal, payload)
    r2 = evaluate_aoep_gate_1(proposal, payload)
    assert r1.ratification_record.record_hash == r2.ratification_record.record_hash


# ---------------------------------------------------------------------------
# T89-AOEP-19 — AOEP-0: empty human_0_signature → HUMAN_0_BLOCKED (non-bypassable)
# ---------------------------------------------------------------------------


def test_t89_aoep_19_gate1_human0_non_bypassable_empty_sig():
    """T89-AOEP-19: AOEP-0 — empty human_0_signature always → AOEP_HUMAN_0_BLOCKED."""
    gate0 = _gate0_pass()
    proposal = gate0.proposal
    rat_hash = __import__("hashlib").sha256(
        (proposal.proposal_id + OPERATOR_ID + TIMESTAMP).encode()
    ).hexdigest()
    bad_payload = Human0RatificationPayload(
        proposal_id=proposal.proposal_id,
        ratification_hash=rat_hash,
        operator_id=OPERATOR_ID,
        timestamp=TIMESTAMP,
        human_0_signature="",  # empty — AOEP-0 violation
        predecessor_hash="a" * 64,
    )
    result = evaluate_aoep_gate_1(proposal, bad_payload)
    assert result.outcome == AOEPOutcome.HUMAN_0_BLOCKED
    assert AOEP_SIGNATURE_MISSING in result.failure_codes
    assert result.ratification_record is None


# ---------------------------------------------------------------------------
# T89-AOEP-20 — GATE-1 blocked on ratification_hash mismatch
# ---------------------------------------------------------------------------


def test_t89_aoep_20_gate1_blocked_hash_mismatch():
    """T89-AOEP-20: wrong ratification_hash → AOEP_RATIFICATION_HASH_MISMATCH."""
    gate0 = _gate0_pass()
    proposal = gate0.proposal
    bad_payload = Human0RatificationPayload(
        proposal_id=proposal.proposal_id,
        ratification_hash="0" * 64,  # wrong hash
        operator_id=OPERATOR_ID,
        timestamp=TIMESTAMP,
        human_0_signature="Dustin L. Reid — signed",
        predecessor_hash="a" * 64,
    )
    result = evaluate_aoep_gate_1(proposal, bad_payload)
    assert result.outcome == AOEPOutcome.BLOCKED
    assert AOEP_RATIFICATION_HASH_MISMATCH in result.failure_codes
    assert result.ratification_record is None
