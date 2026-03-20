# SPDX-License-Identifier: Apache-2.0
"""Phase 77 Track B — First Seed Epoch Run: constitutional tests.

Verifies the full seed lifecycle pipeline end-to-end against
SEED-LIFECYCLE-COMPLETE-0 and all constituent invariants.

All tests are hermetic: isolated queues, no global state, no external I/O.
CEL runs in sandbox mode (ADAAD_SANDBOX_ONLY=true).
"""
from __future__ import annotations

import hashlib
import os
import pytest
from datetime import timezone

os.environ.setdefault("ADAAD_CEL_ENABLED",  "true")
os.environ.setdefault("ADAAD_SANDBOX_ONLY", "true")
os.environ.setdefault("ADAAD_ENV",          "dev")

from runtime.innovations import CapabilitySeed, ADAADInnovationEngine
from runtime.seed_evolution import GRADUATION_THRESHOLD
from runtime.seed_promotion import SeedPromotionQueue
from runtime.seed_review import record_review, ReviewAuthorityError
from runtime.seed_proposal_bridge import build_proposal_request, SeedNotApprovedError
from runtime.seed_cel_injector import inject_seed_proposal_into_context
from runtime.seed_cel_outcome import record_cel_outcome, clear_outcome_registry, OUTCOME_STATUSES


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def isolated_queue():
    """Fresh SeedPromotionQueue for each test — no global state bleed."""
    return SeedPromotionQueue()


@pytest.fixture
def qualifying_seed():
    return CapabilitySeed(
        seed_id="seed-test-governance-001",
        intent="Test governed seed lifecycle",
        scaffold={"tier": "constitutional"},
        author="test-operator",
        lane="governance",
    )


@pytest.fixture
def enqueued_entry(isolated_queue, qualifying_seed):
    """Seed promoted to the queue with expansion_score >= threshold."""
    engine = ADAADInnovationEngine()
    result = engine.evolve_seed(qualifying_seed, epochs=1)
    result["expansion_score"] = GRADUATION_THRESHOLD + 0.05
    result["lineage_digest"] = "sha256:" + hashlib.sha256(
        qualifying_seed.seed_id.encode()
    ).hexdigest()
    return isolated_queue.enqueue(qualifying_seed, result, epoch_id="test-epoch-001")


@pytest.fixture
def approved_entry(isolated_queue, enqueued_entry, qualifying_seed):
    record_review(
        qualifying_seed.seed_id,
        status="approved",
        operator_id="test-governor",
        queue=isolated_queue,
    )
    return isolated_queue.get(qualifying_seed.seed_id)


@pytest.fixture(autouse=True)
def clean_outcome_registry():
    """Ensure outcome registry is empty before and after each test."""
    clear_outcome_registry()
    yield
    clear_outcome_registry()


# ── 1. Seed promotion invariants ──────────────────────────────────────────────

class TestSeedPromotion:
    """SEED-PROMO-0: only seeds with expansion_score >= threshold may be enqueued."""

    def test_qualifying_seed_enqueues(self, isolated_queue, qualifying_seed):
        engine = ADAADInnovationEngine()
        result = engine.evolve_seed(qualifying_seed, epochs=1)
        result["expansion_score"] = GRADUATION_THRESHOLD + 0.01
        entry = isolated_queue.enqueue(qualifying_seed, result, epoch_id="ep-001")
        assert entry["seed_id"] == qualifying_seed.seed_id
        assert entry["expansion_score"] >= GRADUATION_THRESHOLD

    def test_sub_threshold_seed_rejected(self, isolated_queue, qualifying_seed):
        from runtime.seed_promotion import PromotionThresholdError
        engine = ADAADInnovationEngine()
        result = engine.evolve_seed(qualifying_seed, epochs=1)
        result["expansion_score"] = GRADUATION_THRESHOLD - 0.01
        with pytest.raises(PromotionThresholdError):
            isolated_queue.enqueue(qualifying_seed, result, epoch_id="ep-001")

    def test_enqueue_is_idempotent(self, isolated_queue, enqueued_entry, qualifying_seed):
        """SEED-PROMO-IDEM-0: re-enqueue returns existing entry unchanged."""
        engine = ADAADInnovationEngine()
        result = engine.evolve_seed(qualifying_seed, epochs=1)
        result["expansion_score"] = GRADUATION_THRESHOLD + 0.1
        second = isolated_queue.enqueue(qualifying_seed, result, epoch_id="ep-002")
        assert second["enqueued_at"] == enqueued_entry["enqueued_at"]


# ── 2. Review decision invariants ─────────────────────────────────────────────

class TestSeedReview:
    """SEED-REVIEW-HUMAN-0: operator_id required — no self-approval."""

    def test_approved_review_sets_status(self, isolated_queue, enqueued_entry, qualifying_seed):
        decision = record_review(
            qualifying_seed.seed_id,
            status="approved",
            operator_id="governor-001",
            queue=isolated_queue,
        )
        assert decision["status"] == "approved"
        assert decision["operator_id"] == "governor-001"
        assert decision["decision_digest"]

    def test_blank_operator_id_raises(self, isolated_queue, enqueued_entry, qualifying_seed):
        """SEED-REVIEW-HUMAN-0: empty operator_id forbidden."""
        with pytest.raises(ReviewAuthorityError):
            record_review(
                qualifying_seed.seed_id,
                status="approved",
                operator_id="",
                queue=isolated_queue,
            )

    def test_whitespace_operator_id_raises(self, isolated_queue, enqueued_entry, qualifying_seed):
        with pytest.raises(ReviewAuthorityError):
            record_review(
                qualifying_seed.seed_id,
                status="approved",
                operator_id="   ",
                queue=isolated_queue,
            )

    def test_decision_digest_is_deterministic(self, isolated_queue, enqueued_entry, qualifying_seed):
        """SEED-REVIEW-AUDIT-0: digest is deterministic for same inputs.

        First call returns the decision dict directly.
        Idempotent second call returns the queue entry (SEED-REVIEW-IDEM-0);
        decision_digest lives inside review_decision on that return.
        """
        d1 = record_review(
            qualifying_seed.seed_id,
            status="approved",
            operator_id="gov-det",
            queue=isolated_queue,
        )
        # Idempotent second call — returns queue entry; decision_digest is nested
        d2 = record_review(
            qualifying_seed.seed_id,
            status="approved",
            operator_id="gov-det",
            queue=isolated_queue,
        )
        first_digest = d1["decision_digest"]
        idem_digest  = d2.get("decision_digest") or d2.get("review_decision", {}).get("decision_digest")
        assert first_digest == idem_digest

    def test_rejected_review_blocks_proposal(self, isolated_queue, enqueued_entry, qualifying_seed):
        record_review(
            qualifying_seed.seed_id,
            status="rejected",
            operator_id="gov-rej",
            queue=isolated_queue,
        )
        with pytest.raises(SeedNotApprovedError):
            build_proposal_request(
                qualifying_seed.seed_id,
                epoch_id="ep-001",
                queue=isolated_queue,
            )


# ── 3. Proposal bridge invariants ─────────────────────────────────────────────

class TestSeedProposalBridge:
    """SEED-PROP-0 / SEED-PROP-DETERM-0 / SEED-PROP-LEDGER-0."""

    def test_approved_seed_builds_proposal(self, isolated_queue, approved_entry, qualifying_seed):
        req = build_proposal_request(
            qualifying_seed.seed_id,
            epoch_id="ep-test-001",
            queue=isolated_queue,
        )
        assert req.cycle_id.startswith("seed-cycle-")
        assert req.strategy_id == "governance_improvement"

    def test_unapproved_seed_raises(self, isolated_queue, enqueued_entry, qualifying_seed):
        """SEED-PROP-0: non-approved seed blocked."""
        with pytest.raises(SeedNotApprovedError):
            build_proposal_request(
                qualifying_seed.seed_id,
                epoch_id="ep-test-001",
                queue=isolated_queue,
            )

    def test_proposal_is_deterministic(self, isolated_queue, approved_entry, qualifying_seed):
        """SEED-PROP-DETERM-0: equal inputs → equal cycle_id."""
        r1 = build_proposal_request(
            qualifying_seed.seed_id, epoch_id="det-epoch", queue=isolated_queue
        )
        r2 = build_proposal_request(
            qualifying_seed.seed_id, epoch_id="det-epoch", queue=isolated_queue
        )
        assert r1.cycle_id == r2.cycle_id
        assert r1.strategy_id == r2.strategy_id

    def test_lane_to_strategy_routing(self):
        """All seed lanes route to correct strategy_id."""
        from runtime.seed_proposal_bridge import _lane_to_strategy
        assert _lane_to_strategy("governance")   == "governance_improvement"
        assert _lane_to_strategy("performance")  == "performance_optimisation"
        assert _lane_to_strategy("correctness")  == "correctness_hardening"
        assert _lane_to_strategy("security")     == "security_hardening"
        assert _lane_to_strategy("unknown_lane") == "general_improvement"


# ── 4. CEL injection invariants ───────────────────────────────────────────────

class TestSeedCELInjection:
    """SEED-CEL-0 / SEED-CEL-DETERM-0 / SEED-CEL-AUDIT-0."""

    def test_injection_adds_canonical_key(self, isolated_queue, approved_entry, qualifying_seed):
        """SEED-CEL-0: seed_proposal_request is the sole injection key."""
        req = build_proposal_request(
            qualifying_seed.seed_id, epoch_id="inj-ep-001", queue=isolated_queue
        )
        ctx = inject_seed_proposal_into_context(req, base_context={"epoch_id": "inj-ep-001"})
        assert "seed_proposal_request" in ctx
        assert ctx["seed_proposal_request"]["cycle_id"] == req.cycle_id

    def test_injection_does_not_mutate_base_context(self, isolated_queue, approved_entry, qualifying_seed):
        """SEED-CEL-HUMAN-0: base_context is copied, not mutated."""
        req = build_proposal_request(
            qualifying_seed.seed_id, epoch_id="inj-ep-002", queue=isolated_queue
        )
        base = {"epoch_id": "inj-ep-002", "custom_key": "preserved"}
        inject_seed_proposal_into_context(req, base_context=base)
        assert "seed_proposal_request" not in base
        assert base["custom_key"] == "preserved"

    def test_injection_is_deterministic(self, isolated_queue, approved_entry, qualifying_seed):
        """SEED-CEL-DETERM-0: equal inputs → identical injected context."""
        req = build_proposal_request(
            qualifying_seed.seed_id, epoch_id="det-ep", queue=isolated_queue
        )
        ctx1 = inject_seed_proposal_into_context(req, base_context={"epoch_id": "det-ep"})
        ctx2 = inject_seed_proposal_into_context(req, base_context={"epoch_id": "det-ep"})
        assert ctx1["seed_proposal_request"] == ctx2["seed_proposal_request"]


# ── 5. CEL epoch run ──────────────────────────────────────────────────────────

class TestCELEpochRun:
    """CEL-ORDER-0: 14-step epoch completes and passes in sandbox mode."""

    def test_cel_runs_14_steps(self):
        from runtime.evolution.cel_wiring import build_cel
        cel = build_cel(sandbox_only=True)
        result = cel.run_epoch(epoch_id="test-epoch-cel-14", context={})
        assert hasattr(result, "step_results")
        assert len(result.step_results) == 14

    def test_cel_passes_in_sandbox(self):
        from runtime.evolution.cel_wiring import build_cel
        cel = build_cel(sandbox_only=True)
        result = cel.run_epoch(epoch_id="test-epoch-cel-pass", context={})
        assert result.completed is True

    def test_cel_accepts_injected_seed_context(self, isolated_queue, approved_entry, qualifying_seed):
        from runtime.evolution.cel_wiring import build_cel
        req = build_proposal_request(
            qualifying_seed.seed_id, epoch_id="cel-seed-ep", queue=isolated_queue
        )
        ctx = inject_seed_proposal_into_context(req, base_context={"epoch_id": "cel-seed-ep"})
        cel = build_cel(sandbox_only=True)
        result = cel.run_epoch(epoch_id="cel-seed-ep", context=ctx)
        assert result.completed is True


# ── 6. Outcome recording invariants ──────────────────────────────────────────

class TestSeedCELOutcome:
    """SEED-OUTCOME-AUDIT-0 / SEED-OUTCOME-LINK-0 / SEED-OUTCOME-IDEM-0."""

    def test_outcome_recorded_with_full_linkage(self):
        """SEED-OUTCOME-LINK-0: seed_id, cycle_id, epoch_id all required."""
        outcome = record_cel_outcome(
            "seed-link-test", "cycle-001", "epoch-001", "success"
        )
        assert outcome["seed_id"]  == "seed-link-test"
        assert outcome["cycle_id"] == "cycle-001"
        assert outcome["epoch_id"] == "epoch-001"
        assert outcome["outcome_digest"]

    def test_outcome_digest_is_deterministic(self):
        """SEED-OUTCOME-DETERM-0: equal inputs → identical digest."""
        o1 = record_cel_outcome("seed-det", "cyc-det", "ep-det", "success")
        clear_outcome_registry()
        o2 = record_cel_outcome("seed-det", "cyc-det", "ep-det", "success")
        assert o1["outcome_digest"] == o2["outcome_digest"]

    def test_invalid_outcome_status_raises(self):
        """SEED-OUTCOME-AUDIT-0: unrecognised status is rejected."""
        from runtime.seed_cel_outcome import SeedOutcomeStatusError
        with pytest.raises(SeedOutcomeStatusError):
            record_cel_outcome("s", "c", "e", "invalid_status")

    def test_all_valid_outcome_statuses_accepted(self):
        for i, status in enumerate(OUTCOME_STATUSES):
            clear_outcome_registry()
            outcome = record_cel_outcome(f"seed-{status}", f"cyc-{i}", f"ep-{i}", status)
            assert outcome["outcome_status"] == status

    def test_outcome_idempotency(self):
        """SEED-OUTCOME-IDEM-0: duplicate (seed_id, cycle_id) returns existing record."""
        o1 = record_cel_outcome("seed-idem", "cyc-idem", "ep-idem", "success")
        o2 = record_cel_outcome("seed-idem", "cyc-idem", "ep-idem-changed", "failed")
        assert o1["outcome_digest"] == o2["outcome_digest"]
        assert o2["outcome_status"] == "success"  # original, not overwritten

    def test_missing_seed_id_raises(self):
        from runtime.seed_cel_outcome import SeedOutcomeLinkError
        with pytest.raises(SeedOutcomeLinkError):
            record_cel_outcome("", "cyc", "ep", "success")

    def test_missing_cycle_id_raises(self):
        from runtime.seed_cel_outcome import SeedOutcomeLinkError
        with pytest.raises(SeedOutcomeLinkError):
            record_cel_outcome("seed", "", "ep", "success")


# ── 7. Full pipeline integration ──────────────────────────────────────────────

class TestFullSeedLifecyclePipeline:
    """SEED-LIFECYCLE-COMPLETE-0: end-to-end provenance chain is hash-linked."""

    def test_full_pipeline_produces_linked_outcome(self, isolated_queue):
        """All 7 pipeline steps produce a complete, hash-linked provenance chain."""
        from runtime.evolution.cel_wiring import build_cel

        # Step 1–2: seed + enqueue
        seed = CapabilitySeed(
            seed_id="seed-integration-test-001",
            intent="Integration test seed",
            scaffold={},
            author="test-gov",
            lane="correctness",
        )
        engine  = ADAADInnovationEngine()
        result  = engine.evolve_seed(seed, epochs=1)
        result["expansion_score"] = 0.92
        result["lineage_digest"]  = "sha256:" + hashlib.sha256(seed.seed_id.encode()).hexdigest()
        entry = isolated_queue.enqueue(seed, result, epoch_id="integ-ep-001")
        assert entry["expansion_score"] >= GRADUATION_THRESHOLD

        # Step 3: review
        decision = record_review(
            seed.seed_id, status="approved",
            operator_id="DUSTIN-L-REID-DUSTADAAD", queue=isolated_queue
        )
        assert decision["status"] == "approved"

        # Step 4: proposal
        req = build_proposal_request(
            seed.seed_id, epoch_id="integ-ep-001", queue=isolated_queue
        )
        assert req.cycle_id

        # Step 5: inject
        ctx = inject_seed_proposal_into_context(
            req, base_context={"epoch_id": "integ-ep-001"}
        )
        assert "seed_proposal_request" in ctx

        # Step 6: CEL epoch
        cel    = build_cel(sandbox_only=True)
        cel_r  = cel.run_epoch(epoch_id="integ-ep-001", context=ctx)
        assert cel_r.completed

        # Step 7: outcome
        outcome = record_cel_outcome(
            seed.seed_id, req.cycle_id, "integ-ep-001", "success",
            fitness_delta=0.05, mutation_count=14,
        )
        assert outcome["outcome_status"] == "success"
        assert outcome["seed_id"]  == seed.seed_id
        assert outcome["cycle_id"] == req.cycle_id

        # Provenance linkage — all chain elements reference the same identifiers
        assert entry["seed_id"]             == seed.seed_id
        assert decision["seed_id"]          == seed.seed_id
        assert req.cycle_id.startswith("seed-cycle-")
        assert outcome["cycle_id"]          == req.cycle_id
        assert outcome["epoch_id"]          == "integ-ep-001"

    def test_evidence_artifact_exists_and_is_valid(self):
        """Artifact produced by scripts/run_phase77_seed_epoch.py is present and valid."""
        from pathlib import Path
        import json
        artifact = Path("artifacts/governance/phase77/seed_epoch_run_evidence.json")
        assert artifact.exists(), "evidence artifact missing — run scripts/run_phase77_seed_epoch.py"
        data = json.loads(artifact.read_text())
        assert data["schema"] == "SeedEpochRunEvidence/1.0"
        assert data["outcome"] == "success"
        assert len(data["pipeline_steps"]) == 7
        assert "SEED-LIFECYCLE-COMPLETE-0" in data["invariants_demonstrated"]
        assert data["run_digest"].startswith("sha256:")
        assert data["provenance_chain"]["cel_outcome"]["outcome_status"] == "success"
