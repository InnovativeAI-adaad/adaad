# SPDX-License-Identifier: Apache-2.0
"""Phase 63 test suite — T63-GATE-01..15.

Invariants under test:
  AST-SAFE-0         Hard; no exec/eval/os.system; syntax errors blocked.
  AST-IMPORT-0       Hard; no Tier-0 module root imports.
  AST-COMPLEX-0      Class A ceiling +2; Class B ceiling +8 via ExceptionToken.
  SANDBOX-DIV-0      Hard; diverged replay = rejected.
  SEMANTIC-INT-0     Hard; error guard removal blocked without compensating handler.
  EXCEP-SCOPE-0      Tier-0 capability ineligible; only AST-COMPLEX-0 eligible rule.
  EXCEP-HUMAN-0      human_approval_ref required for Tier-1 grant.
  EXCEP-TTL-0        Max 3-epoch TTL; hard ceiling.
  EXCEP-REVOKE-0     Immediate revocation; no grace period.
  GATE-V2-EXISTING-0 Existing rules are not replaced (structural verification).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from runtime.governance.exception_tokens import (
    EXCEPTION_TOKEN_MAX_TTL,
    ELIGIBLE_RULE_IDS,
    TIER_0_CAPABILITY_NAMES,
    ExceptionToken,
    ExceptionTokenLedger,
)
from runtime.governance.gate_v2 import (
    AST_COMPLEX_CLASS_A_CEILING,
    AST_COMPLEX_CLASS_B_CEILING,
    GovernanceGateV2,
    V2GateDecision,
    _check_ast_safe_0,
    _check_ast_import_0,
    _check_ast_complex_0,
    _check_evidence_bundle_req_0,
    _check_sandbox_div_0,
    _check_semantic_int_0,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ledger(tmp_path: Path) -> ExceptionTokenLedger:
    return ExceptionTokenLedger(ledger_path=tmp_path / "exception_tokens.jsonl")


def _grant_token(
    ledger: ExceptionTokenLedger,
    capability: str = "evolution.proposal",
    epoch_id: str = "epoch-001",
    epoch_seq: int = 1,
) -> ExceptionToken:
    token = ExceptionToken.create(
        capability_name=capability,
        rule_id="AST-COMPLEX-0",
        granted_at_epoch=epoch_id,
        granted_epoch_seq=epoch_seq,
        lineage_projection=[0.6, 0.7, 0.75],
        human_approval_ref="HUMAN-0-ref-abc123",
    )
    ledger.grant(token)
    return token


# Minimal source fragments for AST tests
_SIMPLE_SOURCE = "def foo(x):\n    return x + 1\n"
_EVAL_SOURCE = "def foo(x):\n    return eval(x)\n"
_EXEC_SOURCE = "def foo():\n    exec('pass')\n"
_OS_SYSTEM_SOURCE = "import os\ndef foo():\n    os.system('ls')\n"
_TIER0_IMPORT_SOURCE = "from runtime.governance.gate import GovernanceGate\ndef foo(): pass\n"
_TIER0_IMPORT_FROM_SOURCE = "import runtime.governance\ndef foo(): pass\n"

_COMPLEX_BEFORE = "def foo(x):\n    return x\n"
# 4 branch nodes (3 ifs + 1 for) → delta = 4 > Class A ceiling of 2
_COMPLEX_AFTER_DELTA4 = (
    "def foo(x):\n"
    "    if x > 0:\n"
    "        if x > 10:\n"
    "            if x > 100:\n"
    "                for i in range(x):\n"
    "                    pass\n"
    "    return x\n"
)
# 2 branch nodes → delta = 2 = Class A ceiling (passes)
_COMPLEX_AFTER_DELTA2 = (
    "def foo(x):\n"
    "    if x > 0:\n"
    "        if x > 10:\n"
    "            pass\n"
    "    return x\n"
)

_WITH_TRY_SOURCE = "def foo():\n    try:\n        pass\n    except Exception:\n        pass\n"
_WITHOUT_TRY_SOURCE = "def foo():\n    pass\n"


# ---------------------------------------------------------------------------
# T63-GATE-01: AST-SAFE-0 — exec/eval blocked; os.system blocked
# ---------------------------------------------------------------------------

class TestT63Gate01:
    def test_eval_blocked(self):
        result = _check_ast_safe_0(_EVAL_SOURCE)
        assert not result.passed
        assert "eval" in result.reason

    def test_exec_blocked(self):
        result = _check_ast_safe_0(_EXEC_SOURCE)
        assert not result.passed
        assert "exec" in result.reason

    def test_os_system_blocked(self):
        result = _check_ast_safe_0(_OS_SYSTEM_SOURCE)
        assert not result.passed
        assert "system" in result.reason

    def test_syntax_error_blocked(self):
        result = _check_ast_safe_0("def foo(\n    broken syntax !!!")
        assert not result.passed
        assert result.reason == "syntax_error"

    def test_clean_source_passes(self):
        result = _check_ast_safe_0(_SIMPLE_SOURCE)
        assert result.passed


# ---------------------------------------------------------------------------
# T63-GATE-02: AST-IMPORT-0 — Tier-0 module root imports blocked
# ---------------------------------------------------------------------------

class TestT63Gate02:
    def test_tier0_import_from_blocked(self):
        result = _check_ast_import_0(_TIER0_IMPORT_SOURCE)
        assert not result.passed
        assert "tier_0_import" in result.reason

    def test_tier0_direct_import_blocked(self):
        result = _check_ast_import_0(_TIER0_IMPORT_FROM_SOURCE)
        assert not result.passed

    def test_safe_import_passes(self):
        src = "import os\nimport json\ndef foo(): pass\n"
        result = _check_ast_import_0(src)
        assert result.passed

    def test_runtime_non_governance_import_passes(self):
        src = "from runtime.evolution.fitness_v2 import FitnessEngineV2\ndef foo(): pass\n"
        result = _check_ast_import_0(src)
        assert result.passed


# ---------------------------------------------------------------------------
# T63-GATE-03: AST-COMPLEX-0 — Class A ceiling enforced
# ---------------------------------------------------------------------------

class TestT63Gate03:
    def test_delta_at_class_a_ceiling_passes(self):
        result = _check_ast_complex_0(
            _COMPLEX_BEFORE, _COMPLEX_AFTER_DELTA2,
            capability_name="evolution.proposal",
            current_epoch_seq=1,
            exception_ledger=None,
        )
        assert result.passed
        assert not result.class_b_eligible

    def test_delta_zero_passes(self):
        result = _check_ast_complex_0(
            _SIMPLE_SOURCE, _SIMPLE_SOURCE,
            capability_name="evolution.proposal",
            current_epoch_seq=1,
            exception_ledger=None,
        )
        assert result.passed

    def test_delta_exceeds_class_a_no_token_fails_with_class_b_eligible(self):
        result = _check_ast_complex_0(
            _COMPLEX_BEFORE, _COMPLEX_AFTER_DELTA4,
            capability_name="evolution.proposal",
            current_epoch_seq=1,
            exception_ledger=None,
        )
        assert not result.passed
        assert result.class_b_eligible  # Class B path available


# ---------------------------------------------------------------------------
# T63-GATE-04: AST-COMPLEX-0 Class B — ExceptionToken enables approval
# ---------------------------------------------------------------------------

class TestT63Gate04:
    def test_class_b_approved_with_active_token(self, tmp_path):
        ledger = _make_ledger(tmp_path)
        _grant_token(ledger, epoch_seq=1)
        result = _check_ast_complex_0(
            _COMPLEX_BEFORE, _COMPLEX_AFTER_DELTA4,
            capability_name="evolution.proposal",
            current_epoch_seq=1,
            exception_ledger=ledger,
        )
        assert result.passed
        assert result.class_b_eligible

    def test_class_b_blocked_with_expired_token(self, tmp_path):
        ledger = _make_ledger(tmp_path)
        token = _grant_token(ledger, epoch_seq=1)
        # Expire the token
        ledger.revoke(token.token_id, "epoch_window_expires")
        result = _check_ast_complex_0(
            _COMPLEX_BEFORE, _COMPLEX_AFTER_DELTA4,
            capability_name="evolution.proposal",
            current_epoch_seq=5,  # beyond TTL
            exception_ledger=ledger,
        )
        assert not result.passed
        assert result.class_b_eligible  # still eligible; just needs a new token

    def test_delta_above_class_b_ceiling_hard_rejected(self):
        # 10 branch nodes — far exceeds Class B ceiling of 8
        huge_after = "def foo(x):\n" + "\n".join(
            f"    if x > {i}: pass" for i in range(10)
        ) + "\n    return x\n"
        result = _check_ast_complex_0(
            _COMPLEX_BEFORE, huge_after,
            capability_name="evolution.proposal",
            current_epoch_seq=1,
            exception_ledger=None,
        )
        assert not result.passed
        assert not result.class_b_eligible  # hard rejection; no Class B path


# ---------------------------------------------------------------------------
# T63-GATE-05: SANDBOX-DIV-0 — diverged replay rejected
# ---------------------------------------------------------------------------

class TestT63Gate05:
    def test_diverged_replay_fails(self):
        result = _check_sandbox_div_0(replay_diverged=True)
        assert not result.passed
        assert "divergence" in result.reason

    def test_clean_replay_passes(self):
        result = _check_sandbox_div_0(replay_diverged=False)
        assert result.passed


# ---------------------------------------------------------------------------
# T63-GATE-05B: EVIDENCE-BUNDLE-REQ-0 — scoped governance/mutation events fail closed
# ---------------------------------------------------------------------------

class TestT63Gate05B:
    def test_unscoped_event_passes_not_applicable(self):
        result = _check_evidence_bundle_req_0(
            scoped_event=False,
            evidence_bundle_present=False,
            evidence_bundle_valid=False,
        )
        assert result.passed

    def test_scoped_event_missing_bundle_fails(self):
        result = _check_evidence_bundle_req_0(
            scoped_event=True,
            evidence_bundle_present=False,
            evidence_bundle_valid=False,
        )
        assert not result.passed
        assert result.reason == "missing_evidence_bundle"

    def test_scoped_event_invalid_bundle_fails(self):
        result = _check_evidence_bundle_req_0(
            scoped_event=True,
            evidence_bundle_present=True,
            evidence_bundle_valid=False,
        )
        assert not result.passed
        assert result.reason == "invalid_evidence_bundle"

    def test_scoped_event_valid_bundle_passes(self):
        result = _check_evidence_bundle_req_0(
            scoped_event=True,
            evidence_bundle_present=True,
            evidence_bundle_valid=True,
        )
        assert result.passed


# ---------------------------------------------------------------------------
# T63-GATE-06: SEMANTIC-INT-0 — error guard removal blocked
# ---------------------------------------------------------------------------

class TestT63Gate06:
    def test_guard_removal_blocked(self):
        result = _check_semantic_int_0(_WITH_TRY_SOURCE, _WITHOUT_TRY_SOURCE)
        assert not result.passed
        assert "guard_removed" in result.reason

    def test_guard_preserved_passes(self):
        result = _check_semantic_int_0(_WITH_TRY_SOURCE, _WITH_TRY_SOURCE)
        assert result.passed

    def test_guard_added_passes(self):
        result = _check_semantic_int_0(_WITHOUT_TRY_SOURCE, _WITH_TRY_SOURCE)
        assert result.passed

    def test_no_before_source_passes(self):
        result = _check_semantic_int_0(None, _WITHOUT_TRY_SOURCE)
        assert result.passed


# ---------------------------------------------------------------------------
# T63-GATE-07: EXCEP-SCOPE-0 — Tier-0 capability ineligible
# ---------------------------------------------------------------------------

class TestT63Gate07:
    def test_tier0_capability_blocked(self):
        for cap in TIER_0_CAPABILITY_NAMES:
            with pytest.raises(ValueError, match="EXCEP-SCOPE-0"):
                ExceptionToken.create(
                    capability_name=cap,
                    rule_id="AST-COMPLEX-0",
                    granted_at_epoch="epoch-001",
                    granted_epoch_seq=1,
                    lineage_projection=[0.6, 0.7, 0.75],
                    human_approval_ref="ref-123",
                )

    def test_ineligible_rule_id_blocked(self):
        with pytest.raises(ValueError, match="EXCEP-SCOPE-0"):
            ExceptionToken.create(
                capability_name="evolution.proposal",
                rule_id="AST-SAFE-0",  # not eligible
                granted_at_epoch="epoch-001",
                granted_epoch_seq=1,
                lineage_projection=[0.6, 0.7, 0.75],
                human_approval_ref="ref-123",
            )

    def test_eligible_rule_id_accepted(self):
        for rule_id in ELIGIBLE_RULE_IDS:
            token = ExceptionToken.create(
                capability_name="evolution.proposal",
                rule_id=rule_id,
                granted_at_epoch="epoch-001",
                granted_epoch_seq=1,
                lineage_projection=[0.6, 0.7, 0.75],
                human_approval_ref="ref-123",
            )
            assert token.rule_id == rule_id


# ---------------------------------------------------------------------------
# T63-GATE-08: EXCEP-HUMAN-0 — human_approval_ref required for Tier-1
# ---------------------------------------------------------------------------

class TestT63Gate08:
    def test_missing_human_ref_blocked(self):
        with pytest.raises(ValueError, match="EXCEP-HUMAN-0"):
            ExceptionToken.create(
                capability_name="evolution.proposal",
                rule_id="AST-COMPLEX-0",
                granted_at_epoch="epoch-001",
                granted_epoch_seq=1,
                lineage_projection=[0.6, 0.7, 0.75],
                human_approval_ref=None,
            )

    def test_empty_human_ref_blocked(self):
        with pytest.raises(ValueError, match="EXCEP-HUMAN-0"):
            ExceptionToken.create(
                capability_name="evolution.proposal",
                rule_id="AST-COMPLEX-0",
                granted_at_epoch="epoch-001",
                granted_epoch_seq=1,
                lineage_projection=[0.6, 0.7, 0.75],
                human_approval_ref="   ",
            )

    def test_valid_human_ref_accepted(self):
        token = ExceptionToken.create(
            capability_name="evolution.proposal",
            rule_id="AST-COMPLEX-0",
            granted_at_epoch="epoch-001",
            granted_epoch_seq=1,
            lineage_projection=[0.6, 0.7, 0.75],
            human_approval_ref="HUMAN-0-signoff-ref-123",
        )
        assert token.human_approval_ref == "HUMAN-0-signoff-ref-123"


# ---------------------------------------------------------------------------
# T63-GATE-09: EXCEP-TTL-0 — max 3-epoch TTL enforced
# ---------------------------------------------------------------------------

class TestT63Gate09:
    def test_ttl_above_max_blocked(self):
        with pytest.raises(ValueError, match="EXCEP-TTL-0"):
            ExceptionToken.create(
                capability_name="evolution.proposal",
                rule_id="AST-COMPLEX-0",
                granted_at_epoch="epoch-001",
                granted_epoch_seq=1,
                lineage_projection=[0.6, 0.7, 0.75],
                human_approval_ref="ref-123",
                ttl_epochs=EXCEPTION_TOKEN_MAX_TTL + 1,
            )

    def test_ttl_zero_blocked(self):
        with pytest.raises(ValueError, match="EXCEP-TTL-0"):
            ExceptionToken.create(
                capability_name="evolution.proposal",
                rule_id="AST-COMPLEX-0",
                granted_at_epoch="epoch-001",
                granted_epoch_seq=1,
                lineage_projection=[0.6, 0.7, 0.75],
                human_approval_ref="ref-123",
                ttl_epochs=0,
            )

    def test_ttl_at_max_accepted(self):
        token = ExceptionToken.create(
            capability_name="evolution.proposal",
            rule_id="AST-COMPLEX-0",
            granted_at_epoch="epoch-001",
            granted_epoch_seq=5,
            lineage_projection=[0.6, 0.7, 0.75],
            human_approval_ref="ref-123",
            ttl_epochs=EXCEPTION_TOKEN_MAX_TTL,
        )
        assert token.expires_at_epoch == 5 + EXCEPTION_TOKEN_MAX_TTL

    def test_token_active_within_window(self):
        token = ExceptionToken.create(
            capability_name="evolution.proposal",
            rule_id="AST-COMPLEX-0",
            granted_at_epoch="epoch-001",
            granted_epoch_seq=10,
            lineage_projection=[0.6, 0.7, 0.75],
            human_approval_ref="ref-123",
            ttl_epochs=3,
        )
        assert token.is_active(10) is True
        assert token.is_active(13) is True
        assert token.is_active(14) is False


# ---------------------------------------------------------------------------
# T63-GATE-10: EXCEP-REVOKE-0 — immediate revocation; no grace period
# ---------------------------------------------------------------------------

class TestT63Gate10:
    def test_immediate_revocation(self, tmp_path):
        ledger = _make_ledger(tmp_path)
        token = _grant_token(ledger, epoch_seq=1)
        assert token.is_active(1)
        ledger.revoke(token.token_id, "test_failure_rate_exceeds_threshold")
        stored = ledger.get(token.token_id)
        assert stored.revoked is True
        assert stored.revocation_reason == "test_failure_rate_exceeds_threshold"

    def test_revoked_token_not_active(self, tmp_path):
        ledger = _make_ledger(tmp_path)
        token = _grant_token(ledger, epoch_seq=1)
        ledger.revoke(token.token_id, "lineage_diverges")
        active = ledger.active_tokens_for("evolution.proposal", current_epoch_seq=1)
        assert len(active) == 0

    def test_check_and_expire_auto_revokes(self, tmp_path):
        ledger = _make_ledger(tmp_path)
        token = _grant_token(ledger, epoch_seq=1)  # expires at epoch 4
        revoked = ledger.check_and_expire(current_epoch_seq=5)  # past TTL
        assert token.token_id in revoked
        stored = ledger.get(token.token_id)
        assert stored.revoked is True

    def test_idempotent_revocation(self, tmp_path):
        ledger = _make_ledger(tmp_path)
        token = _grant_token(ledger, epoch_seq=1)
        ledger.revoke(token.token_id, "reason_a")
        ledger.revoke(token.token_id, "reason_b")  # should not raise
        stored = ledger.get(token.token_id)
        assert stored.revocation_reason == "reason_a"  # first revocation wins


# ---------------------------------------------------------------------------
# T63-GATE-11: GATE-V2-EXISTING-0 — structural verification
# ---------------------------------------------------------------------------

class TestT63Gate11:
    def test_gate_v2_does_not_import_or_replace_gate(self):
        """GovernanceGateV2 must not import GovernanceGate (additive only)."""
        import ast as _ast, pathlib
        src = pathlib.Path("runtime/governance/gate_v2.py").read_text()
        tree = _ast.parse(src)
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                for alias in getattr(node, "names", []):
                    full = f"{module}.{alias.name}" if module else alias.name
                    assert "gate" not in full.lower() or "gate_v2" in full.lower() or "exception" in full.lower(), \
                        f"GovernanceGateV2 must not import GovernanceGate: found {full}"

    def test_existing_gate_still_importable(self):
        from runtime.governance.gate import GovernanceGate
        assert GovernanceGate is not None

    def test_v2_gate_is_separate_class(self):
        from runtime.governance.gate import GovernanceGate
        assert GovernanceGateV2 is not GovernanceGate


# ---------------------------------------------------------------------------
# T63-GATE-12: Full V2 gate — all five rules evaluated in canonical order
# ---------------------------------------------------------------------------

class TestT63Gate12:
    def test_clean_mutation_approved(self, tmp_path):
        gate = GovernanceGateV2(exception_ledger=_make_ledger(tmp_path))
        decision = gate.evaluate(
            mutation_id="mut-clean",
            capability_name="evolution.proposal",
            after_source=_SIMPLE_SOURCE,
            before_source=_SIMPLE_SOURCE,
            replay_diverged=False,
            current_epoch_seq=1,
            governance_or_mutation_scope_event=True,
            evidence_bundle_present=True,
            evidence_bundle_valid=True,
        )
        assert decision.approved
        assert not decision.class_b_eligible
        assert len(decision.rule_results) == 6

    def test_eval_in_source_blocked(self, tmp_path):
        gate = GovernanceGateV2(exception_ledger=_make_ledger(tmp_path))
        decision = gate.evaluate(
            mutation_id="mut-eval",
            capability_name="evolution.proposal",
            after_source=_EVAL_SOURCE,
            before_source=_SIMPLE_SOURCE,
            replay_diverged=False,
            current_epoch_seq=1,
            governance_or_mutation_scope_event=True,
            evidence_bundle_present=True,
            evidence_bundle_valid=True,
        )
        assert not decision.approved
        failed_ids = {r.rule_id for r in decision.rule_results if not r.passed}
        assert "AST-SAFE-0" in failed_ids

    def test_diverged_replay_blocked(self, tmp_path):
        gate = GovernanceGateV2(exception_ledger=_make_ledger(tmp_path))
        decision = gate.evaluate(
            mutation_id="mut-div",
            capability_name="evolution.proposal",
            after_source=_SIMPLE_SOURCE,
            before_source=_SIMPLE_SOURCE,
            replay_diverged=True,
            current_epoch_seq=1,
            governance_or_mutation_scope_event=True,
            evidence_bundle_present=True,
            evidence_bundle_valid=True,
        )
        assert not decision.approved
        failed_ids = {r.rule_id for r in decision.rule_results if not r.passed}
        assert "SANDBOX-DIV-0" in failed_ids

    def test_five_rules_present(self, tmp_path):
        gate = GovernanceGateV2(exception_ledger=_make_ledger(tmp_path))
        decision = gate.evaluate(
            mutation_id="mut-count",
            capability_name="evolution.proposal",
            after_source=_SIMPLE_SOURCE,
            current_epoch_seq=1,
        )
        rule_ids = {r.rule_id for r in decision.rule_results}
        assert rule_ids == {"AST-SAFE-0", "AST-IMPORT-0", "AST-COMPLEX-0",
                            "EVIDENCE-BUNDLE-REQ-0", "SANDBOX-DIV-0", "SEMANTIC-INT-0"}

    def test_scoped_event_without_evidence_bundle_blocked(self, tmp_path):
        gate = GovernanceGateV2(exception_ledger=_make_ledger(tmp_path))
        decision = gate.evaluate(
            mutation_id="mut-evidence-missing",
            capability_name="evolution.proposal",
            after_source=_SIMPLE_SOURCE,
            before_source=_SIMPLE_SOURCE,
            replay_diverged=False,
            current_epoch_seq=1,
            governance_or_mutation_scope_event=True,
            evidence_bundle_present=False,
            evidence_bundle_valid=False,
        )
        assert not decision.approved
        failed_ids = {r.rule_id for r in decision.rule_results if not r.passed}
        assert "EVIDENCE-BUNDLE-REQ-0" in failed_ids


# ---------------------------------------------------------------------------
# T63-GATE-13: class_b_eligible surfaced correctly on V2GateDecision
# ---------------------------------------------------------------------------

class TestT63Gate13:
    def test_class_b_eligible_surfaced_when_only_complex_fails(self, tmp_path):
        gate = GovernanceGateV2(exception_ledger=_make_ledger(tmp_path))
        decision = gate.evaluate(
            mutation_id="mut-complex",
            capability_name="evolution.proposal",
            after_source=_COMPLEX_AFTER_DELTA4,
            before_source=_COMPLEX_BEFORE,
            replay_diverged=False,
            current_epoch_seq=1,
        )
        assert not decision.approved
        assert decision.class_b_eligible

    def test_class_b_not_eligible_when_multiple_rules_fail(self, tmp_path):
        gate = GovernanceGateV2(exception_ledger=_make_ledger(tmp_path))
        # Both AST-SAFE-0 and AST-COMPLEX-0 fail
        combined = _COMPLEX_AFTER_DELTA4 + "\ndef bar(): eval('x')\n"
        decision = gate.evaluate(
            mutation_id="mut-multi-fail",
            capability_name="evolution.proposal",
            after_source=combined,
            before_source=_COMPLEX_BEFORE,
            replay_diverged=False,
            current_epoch_seq=1,
        )
        assert not decision.approved
        assert not decision.class_b_eligible


# ---------------------------------------------------------------------------
# T63-GATE-14: ExceptionToken ledger persistence roundtrip
# ---------------------------------------------------------------------------

class TestT63Gate14:
    def test_ledger_persists_and_reloads(self, tmp_path):
        ledger_path = tmp_path / "tokens.jsonl"
        ledger1 = ExceptionTokenLedger(ledger_path=ledger_path)
        token = _grant_token(ledger1, epoch_seq=5)
        # Reload from same path
        ledger2 = ExceptionTokenLedger(ledger_path=ledger_path)
        reloaded = ledger2.get(token.token_id)
        assert reloaded is not None
        assert reloaded.capability_name == token.capability_name
        assert reloaded.expires_at_epoch == token.expires_at_epoch
        assert not reloaded.revoked

    def test_revocation_persists_on_reload(self, tmp_path):
        ledger_path = tmp_path / "tokens.jsonl"
        ledger1 = ExceptionTokenLedger(ledger_path=ledger_path)
        token = _grant_token(ledger1, epoch_seq=5)
        ledger1.revoke(token.token_id, "lineage_diverges")
        ledger2 = ExceptionTokenLedger(ledger_path=ledger_path)
        reloaded = ledger2.get(token.token_id)
        assert reloaded.revoked is True


# ---------------------------------------------------------------------------
# T63-GATE-15: token_id determinism
# ---------------------------------------------------------------------------

class TestT63Gate15:
    def test_token_id_deterministic(self):
        """Same inputs → same token_id across independent constructions."""
        kwargs = dict(
            capability_name="evolution.proposal",
            rule_id="AST-COMPLEX-0",
            granted_at_epoch="epoch-det-001",
            granted_epoch_seq=7,
            lineage_projection=[0.6, 0.7, 0.75],
            human_approval_ref="ref-det-123",
        )
        t1 = ExceptionToken.create(**kwargs)
        t2 = ExceptionToken.create(**kwargs)
        assert t1.token_id == t2.token_id

    def test_different_epochs_different_token_ids(self):
        base_kwargs = dict(
            capability_name="evolution.proposal",
            rule_id="AST-COMPLEX-0",
            granted_epoch_seq=1,
            lineage_projection=[0.6, 0.7, 0.75],
            human_approval_ref="ref-123",
        )
        t1 = ExceptionToken.create(granted_at_epoch="epoch-001", **base_kwargs)
        t2 = ExceptionToken.create(granted_at_epoch="epoch-002", **base_kwargs)
        assert t1.token_id != t2.token_id

    def test_v2_gate_decision_serialises(self, tmp_path):
        gate = GovernanceGateV2(exception_ledger=_make_ledger(tmp_path))
        decision = gate.evaluate(
            mutation_id="mut-serial",
            capability_name="evolution.proposal",
            after_source=_SIMPLE_SOURCE,
            current_epoch_seq=1,
        )
        d = decision.to_dict()
        assert d["mutation_id"] == "mut-serial"
        assert isinstance(d["rule_results"], list)
        assert len(d["rule_results"]) == 6
