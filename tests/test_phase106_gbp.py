# SPDX-License-Identifier: Apache-2.0
"""Phase 106 — INNOV-21 Governance Bankruptcy Protocol (GBP) acceptance tests.

T106-GBP-01 … T106-GBP-30  — 30/30 must pass.
"""
from __future__ import annotations
import json, pathlib, tempfile
import pytest
from runtime.innovations30.governance_bankruptcy import (
    BankruptcyDeclaration, GovernanceBankruptcyProtocol, GBPViolation,
    RemediationStep, GBP_VERSION, BANKRUPTCY_THRESHOLD,
    REMEDIATION_HEALTH_TARGET, REMEDIATION_CLEAN_STREAK,
    GBP_INV_VERSION, GBP_INV_THRESH, GBP_INV_HEALTH,
    GBP_INV_PERSIST, GBP_INV_CHAIN, GBP_INV_DISCHARGE,
    GBP_INV_GATE, GBP_INV_IMMUT,
)

@pytest.fixture
def tmp_gbp(tmp_path):
    return GovernanceBankruptcyProtocol(state_path=tmp_path / "gbp.jsonl")

@pytest.fixture
def tmp_ledger(tmp_path):
    return tmp_path / "gbp.jsonl"

def _make_discharged(ledger_path):
    gbp = GovernanceBankruptcyProtocol(state_path=ledger_path)
    gbp.evaluate("ep-disc", 0.95, 0.2)
    for _ in range(REMEDIATION_CLEAN_STREAK):
        gbp.record_remediation_epoch("ep-disc", REMEDIATION_HEALTH_TARGET + 0.01)
    return gbp

def test_T106_GBP_01_import(): assert GovernanceBankruptcyProtocol is not None
def test_T106_GBP_02_version(): assert GBP_VERSION == "1.0.0"
def test_T106_GBP_03_inv_codes():
    codes = [GBP_INV_VERSION,GBP_INV_THRESH,GBP_INV_HEALTH,GBP_INV_PERSIST,GBP_INV_CHAIN,GBP_INV_DISCHARGE,GBP_INV_GATE,GBP_INV_IMMUT]
    assert len(codes)==8 and all(c.startswith("GBP") for c in codes)
def test_T106_GBP_04_violation_is_runtime(): assert issubclass(GBPViolation, RuntimeError)
def test_T106_GBP_05_thresh_zero(tmp_path):
    with pytest.raises(GBPViolation, match="GBP-THRESH-0"):
        GovernanceBankruptcyProtocol(tmp_path/"g.jsonl", bankruptcy_threshold=0.0)
def test_T106_GBP_06_thresh_one(tmp_path):
    with pytest.raises(GBPViolation, match="GBP-THRESH-0"):
        GovernanceBankruptcyProtocol(tmp_path/"g.jsonl", bankruptcy_threshold=1.0)
def test_T106_GBP_07_thresh_valid(tmp_path):
    assert GovernanceBankruptcyProtocol(tmp_path/"g.jsonl", bankruptcy_threshold=0.85)
def test_T106_GBP_08_health_equal_thresh(tmp_path):
    with pytest.raises(GBPViolation, match="GBP-HEALTH-0"):
        GovernanceBankruptcyProtocol(tmp_path/"g.jsonl", bankruptcy_threshold=0.80, remediation_health_target=0.80)
def test_T106_GBP_09_health_above_thresh(tmp_path):
    with pytest.raises(GBPViolation, match="GBP-HEALTH-0"):
        GovernanceBankruptcyProtocol(tmp_path/"g.jsonl", bankruptcy_threshold=0.80, remediation_health_target=0.85)
def test_T106_GBP_10_no_bankruptcy_below(tmp_gbp):
    assert tmp_gbp.evaluate("e1", 0.89, 0.50) is None
    assert not tmp_gbp.in_bankruptcy
def test_T106_GBP_11_bankruptcy_at_threshold(tmp_gbp):
    decl = tmp_gbp.evaluate("e1", 0.90, 0.30)
    assert decl is not None and tmp_gbp.in_bankruptcy and decl.status=="active"
def test_T106_GBP_12_repeated_evaluate(tmp_gbp):
    d1 = tmp_gbp.evaluate("e1",0.95,0.2); d2 = tmp_gbp.evaluate("e1",0.97,0.1)
    assert d1 is d2
def test_T106_GBP_13_declaration_has_digest(tmp_gbp):
    assert tmp_gbp.evaluate("e1",0.95,0.2).declaration_digest.startswith("sha256:")
def test_T106_GBP_14_chain_genesis(tmp_gbp):
    assert tmp_gbp.evaluate("e1",0.95,0.2).prev_digest == "genesis"
def test_T106_GBP_15_persist_on_evaluate(tmp_path):
    p = tmp_path/"gbp.jsonl"
    gbp = GovernanceBankruptcyProtocol(state_path=p)
    gbp.evaluate("e1",0.95,0.2)
    assert p.exists() and len([l for l in p.read_text().splitlines() if l.strip()])==1
def test_T106_GBP_16_streak(tmp_gbp):
    tmp_gbp.evaluate("e1",0.95,0.2)
    for _ in range(3): tmp_gbp.record_remediation_epoch("e1",0.70)
    assert tmp_gbp._clean_epoch_streak==3
def test_T106_GBP_17_streak_reset(tmp_gbp):
    tmp_gbp.evaluate("e1",0.95,0.2)
    tmp_gbp.record_remediation_epoch("e1",0.70)
    tmp_gbp.record_remediation_epoch("e1",0.70)
    tmp_gbp.record_remediation_epoch("e1",0.40)
    assert tmp_gbp._clean_epoch_streak==0
def test_T106_GBP_18_discharge(tmp_gbp):
    tmp_gbp.evaluate("e1",0.95,0.2)
    result=False
    for _ in range(REMEDIATION_CLEAN_STREAK): result = tmp_gbp.record_remediation_epoch("e1",0.70)
    assert result is True and not tmp_gbp.in_bankruptcy
def test_T106_GBP_19_immut_discharged(tmp_ledger):
    gbp = _make_discharged(tmp_ledger)
    with pytest.raises(GBPViolation, match="GBP-IMMUT-0"):
        gbp.evaluate("ep-disc",0.95,0.2)
def test_T106_GBP_20_gate_empty(tmp_gbp):
    with pytest.raises(GBPViolation, match="GBP-GATE-0"): tmp_gbp.is_mutation_allowed("")
def test_T106_GBP_21_gate_whitespace(tmp_gbp):
    with pytest.raises(GBPViolation, match="GBP-GATE-0"): tmp_gbp.is_mutation_allowed("   ")
def test_T106_GBP_22_mutation_blocked(tmp_gbp):
    tmp_gbp.evaluate("e1",0.95,0.2)
    ok,reason = tmp_gbp.is_mutation_allowed("add new feature X")
    assert not ok and "BANKRUPTCY ACTIVE" in reason
def test_T106_GBP_23_debt_reducing_allowed(tmp_gbp):
    tmp_gbp.evaluate("e1",0.95,0.2)
    ok,_ = tmp_gbp.is_mutation_allowed("fix governance violation")
    assert ok
def test_T106_GBP_24_healthy_all_allowed(tmp_gbp):
    ok,reason = tmp_gbp.is_mutation_allowed("add new feature X")
    assert ok and reason==""
def test_T106_GBP_25_chain_empty(tmp_gbp):
    valid,_ = tmp_gbp.verify_chain(); assert valid
def test_T106_GBP_26_chain_valid_after_discharge(tmp_ledger):
    gbp = _make_discharged(tmp_ledger)
    valid,msg = gbp.verify_chain(); assert valid, msg
def test_T106_GBP_27_chain_tamper_detected(tmp_ledger):
    gbp = GovernanceBankruptcyProtocol(state_path=tmp_ledger)
    gbp.evaluate("e1",0.95,0.2)
    content=tmp_ledger.read_text(); d=json.loads(content.strip())
    d["declaration_digest"]="sha256:tampered"
    tmp_ledger.write_text(json.dumps(d)+"\n")
    gbp2 = GovernanceBankruptcyProtocol(state_path=tmp_ledger)
    valid,msg = gbp2.verify_chain()
    assert not valid
def test_T106_GBP_28_discharge_supersession(tmp_ledger):
    _make_discharged(tmp_ledger)
    gbp2 = GovernanceBankruptcyProtocol(state_path=tmp_ledger)
    assert not gbp2.in_bankruptcy and "ep-disc" in gbp2._discharged_epoch_ids
def test_T106_GBP_29_progress_keys(tmp_gbp):
    tmp_gbp.evaluate("e1",0.95,0.2)
    prog = tmp_gbp.remediation_progress()
    assert prog["in_bankruptcy"] and "epoch_id" in prog and "declaration_digest" in prog
def test_T106_GBP_30_progress_healthy(tmp_gbp):
    prog = tmp_gbp.remediation_progress()
    assert prog["status"]=="healthy" and not prog["in_bankruptcy"] and "epoch_id" not in prog
