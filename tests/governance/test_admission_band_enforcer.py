# SPDX-License-Identifier: Apache-2.0
"""Tests for AdmissionBandEnforcer — ADAAD Phase 28, PR-28-01.

Coverage target: advisory/blocking mode, all four health bands,
escalation resolution, fail-safe paths, digest determinism.
"""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from runtime.governance.admission_band_enforcer import (
    AdmissionBandEnforcer,
    ENFORCER_VERSION,
)


# ---------------------------------------------------------------------------
# T28-01 — Advisory mode (default): blocked is always False
# ---------------------------------------------------------------------------

def test_T28_01_01_advisory_green_not_blocked():
    enforcer = AdmissionBandEnforcer(health_score=0.90, escalation_mode="advisory")
    v = enforcer.evaluate(0.80)
    assert v.escalation_mode == "advisory"
    assert v.blocked is False
    assert v.block_reason == ""
    assert v.decision.advisory_only is True


def test_T28_01_02_advisory_amber_not_blocked():
    enforcer = AdmissionBandEnforcer(health_score=0.70, escalation_mode="advisory")
    v = enforcer.evaluate(0.30)
    assert v.blocked is False
    assert v.decision.admission_band == "amber"


def test_T28_01_03_advisory_red_not_blocked():
    enforcer = AdmissionBandEnforcer(health_score=0.50, escalation_mode="advisory")
    v = enforcer.evaluate(0.20)
    assert v.blocked is False
    assert v.decision.admission_band == "red"


def test_T28_01_04_advisory_halt_not_blocked():
    """Even in HALT band, advisory mode never blocks."""
    enforcer = AdmissionBandEnforcer(health_score=0.20, escalation_mode="advisory")
    v = enforcer.evaluate(0.50)
    assert v.decision.admission_band == "halt"
    assert v.blocked is False
    assert v.block_reason == ""


# ---------------------------------------------------------------------------
# T28-02 — Blocking mode: only HALT triggers block
# ---------------------------------------------------------------------------

def test_T28_02_01_blocking_green_not_blocked():
    enforcer = AdmissionBandEnforcer(health_score=0.90, escalation_mode="blocking")
    v = enforcer.evaluate(0.10)
    assert v.escalation_mode == "blocking"
    assert v.blocked is False


def test_T28_02_02_blocking_amber_not_blocked():
    enforcer = AdmissionBandEnforcer(health_score=0.70, escalation_mode="blocking")
    v = enforcer.evaluate(0.10)
    assert v.decision.admission_band == "amber"
    assert v.blocked is False


def test_T28_02_03_blocking_red_not_blocked():
    enforcer = AdmissionBandEnforcer(health_score=0.50, escalation_mode="blocking")
    v = enforcer.evaluate(0.10)
    assert v.decision.admission_band == "red"
    assert v.blocked is False


def test_T28_02_04_blocking_halt_IS_blocked():
    """HALT band + blocking mode → blocked = True."""
    enforcer = AdmissionBandEnforcer(health_score=0.20, escalation_mode="blocking")
    v = enforcer.evaluate(0.50)
    assert v.decision.admission_band == "halt"
    assert v.blocked is True
    assert "catastrophic" in v.block_reason.lower()


def test_T28_02_05_blocking_halt_block_reason_nonempty():
    enforcer = AdmissionBandEnforcer(health_score=0.39, escalation_mode="blocking")
    v = enforcer.evaluate(0.99)
    assert v.blocked is True
    assert len(v.block_reason) > 20


def test_T28_02_06_advisory_only_always_true_even_when_blocked():
    """advisory_only on the underlying AdmissionDecision is structurally True."""
    enforcer = AdmissionBandEnforcer(health_score=0.10, escalation_mode="blocking")
    v = enforcer.evaluate(0.99)
    assert v.blocked is True
    assert v.decision.advisory_only is True  # structural invariant preserved


# ---------------------------------------------------------------------------
# T28-03 — Escalation resolution from env var
# ---------------------------------------------------------------------------

def test_T28_03_01_no_env_var_defaults_to_advisory(monkeypatch):
    monkeypatch.delenv("ADAAD_SEVERITY_ESCALATIONS", raising=False)
    enforcer = AdmissionBandEnforcer(health_score=0.10)
    assert enforcer.escalation_mode == "advisory"


def test_T28_03_02_env_var_advisory_explicit(monkeypatch):
    monkeypatch.setenv(
        "ADAAD_SEVERITY_ESCALATIONS",
        json.dumps({"admission_band_enforcement": "advisory"}),
    )
    enforcer = AdmissionBandEnforcer(health_score=0.10)
    assert enforcer.escalation_mode == "advisory"
    v = enforcer.evaluate(0.99)
    assert v.blocked is False


def test_T28_03_03_env_var_blocking_escalates(monkeypatch):
    monkeypatch.setenv(
        "ADAAD_SEVERITY_ESCALATIONS",
        json.dumps({"admission_band_enforcement": "blocking"}),
    )
    enforcer = AdmissionBandEnforcer(health_score=0.10)
    assert enforcer.escalation_mode == "blocking"
    v = enforcer.evaluate(0.99)
    assert v.blocked is True


def test_T28_03_04_invalid_json_env_var_defaults_to_advisory(monkeypatch):
    monkeypatch.setenv("ADAAD_SEVERITY_ESCALATIONS", "not-valid-json")
    enforcer = AdmissionBandEnforcer(health_score=0.10)
    assert enforcer.escalation_mode == "advisory"


def test_T28_03_05_env_var_other_rule_does_not_affect_mode(monkeypatch):
    monkeypatch.setenv(
        "ADAAD_SEVERITY_ESCALATIONS",
        json.dumps({"some_other_rule": "blocking"}),
    )
    enforcer = AdmissionBandEnforcer(health_score=0.10)
    assert enforcer.escalation_mode == "advisory"


def test_T28_03_06_unknown_escalation_value_defaults_to_advisory(monkeypatch):
    monkeypatch.setenv(
        "ADAAD_SEVERITY_ESCALATIONS",
        json.dumps({"admission_band_enforcement": "critical"}),
    )
    enforcer = AdmissionBandEnforcer(health_score=0.10)
    assert enforcer.escalation_mode == "advisory"


# ---------------------------------------------------------------------------
# T28-04 — Fail-safe: None / invalid health_score → GREEN (1.0)
# ---------------------------------------------------------------------------

def test_T28_04_01_none_health_score_defaults_to_green():
    enforcer = AdmissionBandEnforcer(health_score=None, escalation_mode="blocking")
    v = enforcer.evaluate(0.50)
    assert v.decision.admission_band == "green"
    assert v.blocked is False


def test_T28_04_02_health_score_above_1_clamped_to_green():
    enforcer = AdmissionBandEnforcer(health_score=1.5, escalation_mode="blocking")
    v = enforcer.evaluate(0.50)
    assert v.decision.admission_band == "green"
    assert v.blocked is False


def test_T28_04_03_health_score_below_0_clamped():
    enforcer = AdmissionBandEnforcer(health_score=-0.1, escalation_mode="blocking")
    v = enforcer.evaluate(0.99)
    assert v.decision.admission_band == "halt"
    assert v.blocked is True


# ---------------------------------------------------------------------------
# T28-05 — Digest determinism
# ---------------------------------------------------------------------------

def test_T28_05_01_identical_inputs_identical_digest():
    e1 = AdmissionBandEnforcer(health_score=0.70, escalation_mode="advisory")
    e2 = AdmissionBandEnforcer(health_score=0.70, escalation_mode="advisory")
    v1 = e1.evaluate(0.30)
    v2 = e2.evaluate(0.30)
    assert v1.verdict_digest == v2.verdict_digest


def test_T28_05_02_different_risk_scores_different_digests():
    e = AdmissionBandEnforcer(health_score=0.70, escalation_mode="advisory")
    v1 = e.evaluate(0.10)
    v2 = e.evaluate(0.80)
    assert v1.verdict_digest != v2.verdict_digest


def test_T28_05_03_different_escalation_modes_different_digests():
    e_adv = AdmissionBandEnforcer(health_score=0.10, escalation_mode="advisory")
    e_blk = AdmissionBandEnforcer(health_score=0.10, escalation_mode="blocking")
    v_adv = e_adv.evaluate(0.99)
    v_blk = e_blk.evaluate(0.99)
    assert v_adv.verdict_digest != v_blk.verdict_digest


def test_T28_05_04_digest_is_valid_sha256_hex():
    enforcer = AdmissionBandEnforcer(health_score=0.80, escalation_mode="advisory")
    v = enforcer.evaluate(0.10)
    assert len(v.verdict_digest) == 64
    int(v.verdict_digest, 16)  # raises ValueError if not valid hex


# ---------------------------------------------------------------------------
# T28-06 — as_dict serialisation
# ---------------------------------------------------------------------------

def test_T28_06_01_as_dict_contains_required_keys():
    enforcer = AdmissionBandEnforcer(health_score=0.70, escalation_mode="advisory")
    d = enforcer.evaluate(0.30).as_dict()
    for key in ("decision", "escalation_mode", "blocked", "block_reason",
                 "verdict_digest", "enforcer_version"):
        assert key in d, f"missing key: {key}"


def test_T28_06_02_as_dict_decision_contains_advisory_only():
    enforcer = AdmissionBandEnforcer(health_score=0.90, escalation_mode="advisory")
    d = enforcer.evaluate(0.10).as_dict()
    assert d["decision"]["advisory_only"] is True


def test_T28_06_03_as_dict_enforcer_version():
    enforcer = AdmissionBandEnforcer(health_score=0.90, escalation_mode="advisory")
    d = enforcer.evaluate(0.10).as_dict()
    assert d["enforcer_version"] == ENFORCER_VERSION


def test_T28_06_04_as_dict_is_json_serialisable():
    enforcer = AdmissionBandEnforcer(health_score=0.50, escalation_mode="blocking")
    d = enforcer.evaluate(0.20).as_dict()
    json.dumps(d)  # must not raise


# ---------------------------------------------------------------------------
# T28-07 — GovernanceGate authority boundary
# ---------------------------------------------------------------------------

def test_T28_07_01_enforcer_never_imports_governance_gate():
    """Structural authority boundary: AdmissionBandEnforcer must not import GovernanceGate."""
    import importlib, sys
    # Remove cached module so we get a fresh import
    mod_name = "runtime.governance.admission_band_enforcer"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    import runtime.governance.admission_band_enforcer as m
    src = open(m.__file__).read()
    # Structural check: GovernanceGate must not be imported (docs may mention it)
    import re
    imports = re.findall(r'^(?:import|from)\s+.*GovernanceGate.*', src, re.MULTILINE)
    assert not imports, (
        "AdmissionBandEnforcer must not import GovernanceGate — authority boundary violated"
    )


def test_T28_07_02_enforcer_version_constant():
    assert ENFORCER_VERSION == "28.0"
