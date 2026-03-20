# SPDX-License-Identifier: Apache-2.0
"""Phase 83 — Causal Fitness Attribution Engine Tests.

Tests ID: T83-CFAE-NN

Invariants under test:
  CFAE-0        Attribution is advisory — never overrides GovernanceGate.
  CFAE-DET-0    Identical inputs → identical attribution scores.
  CFAE-BOUND-0  All attribution scores in [-1.0, 1.0].
  CFAE-LEDGER-0 CausalAttributionReport written to ledger when injected.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
from typing import Any, Dict, FrozenSet, List

import pytest

from runtime.evolution.mutation_ablator import (
    MutationAblator,
    MutationOperation,
    _extract_ast_ops,
    _extract_field_ops,
    _op_id,
)
from runtime.evolution.causal_fitness_attributor import (
    CausalFitnessAttributor,
    CausalAttributionReport,
    OperationAttribution,
    _clamp,
    _tag,
    CFAE_VERSION,
)
from runtime.evolution.lineage_v2 import LineageLedgerV2

pytestmark = pytest.mark.phase83


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


BEFORE_SRC = "x = 1\n"
AFTER_SRC = "import os\nx = 1\ny = 2\nif x:\n    pass\n"


def _ctx(correctness=0.8, efficiency=0.7) -> Dict[str, Any]:
    return {
        "epoch_id": "ep-83",
        "mutation_tier": "low",
        "correctness_score": correctness,
        "efficiency_score": efficiency,
        "policy_compliance_score": 0.9,
        "goal_alignment_score": 0.7,
        "simulated_market_score": 0.5,
    }


def _make_ledger(tmp: pathlib.Path) -> LineageLedgerV2:
    return LineageLedgerV2(ledger_path=tmp / "ledger.jsonl")


def _cand_fields() -> Dict[str, Any]:
    return {
        "expected_gain": 0.3,
        "risk_score": 0.2,
        "complexity": 0.4,
        "coverage_delta": 0.1,
    }


# ===========================================================================
# MutationOperation
# ===========================================================================


def test_T83_CFAE_01_op_id_deterministic():
    """T83-CFAE-01: CFAE-DET-0 — op_id is deterministic for same inputs."""
    assert _op_id("c-1", "key-A") == _op_id("c-1", "key-A")
    assert _op_id("c-1", "key-A") != _op_id("c-1", "key-B")
    assert _op_id("c-1", "key-A").startswith("op-")


def test_T83_CFAE_02_op_roundtrip():
    """T83-CFAE-02: MutationOperation to_dict/from_dict round-trip."""
    op = MutationOperation(
        op_id="op-abc", op_key="ast_FunctionDef_delta_+1",
        op_type="ast_node_add", description="FunctionDef: +1 nodes", weight=0.3,
    )
    assert MutationOperation.from_dict(op.to_dict()) == op


# ===========================================================================
# _extract_ast_ops
# ===========================================================================


def test_T83_CFAE_03_ast_ops_extracted_from_source():
    """T83-CFAE-03: AST ops extracted when source available."""
    ops = _extract_ast_ops("c", BEFORE_SRC, AFTER_SRC)
    assert len(ops) > 0
    op_types = {o.op_type for o in ops}
    assert "ast_node_add" in op_types or "import_change" in op_types


def test_T83_CFAE_04_ast_ops_sorted_determinism():
    """T83-CFAE-04: CFAE-DET-0 — extracted ops sorted by op_key."""
    ops = _extract_ast_ops("c", BEFORE_SRC, AFTER_SRC)
    keys = [o.op_key for o in ops]
    assert keys == sorted(keys)


def test_T83_CFAE_05_ast_ops_empty_on_parse_error():
    """T83-CFAE-05: AST ops return [] on unparseable source."""
    ops = _extract_ast_ops("c", "def broken(:", "def broken(:")
    assert ops == []


def test_T83_CFAE_06_ast_ops_unchanged_source_empty():
    """T83-CFAE-06: Identical before/after source → no ops extracted."""
    src = "x = 1\n"
    ops = _extract_ast_ops("c", src, src)
    assert ops == []


def test_T83_CFAE_07_import_change_op_detected():
    """T83-CFAE-07: Import surface delta produces import_change op."""
    before = "x = 1\n"
    after = "import os\nimport sys\nx = 1\n"
    ops = _extract_ast_ops("c", before, after)
    import_ops = [o for o in ops if o.op_type == "import_change"]
    assert len(import_ops) == 1
    assert import_ops[0].metadata["import_delta"] == 2


# ===========================================================================
# _extract_field_ops
# ===========================================================================


def test_T83_CFAE_08_field_ops_from_candidate_dict():
    """T83-CFAE-08: Field ops extracted from candidate fields dict."""
    ops = _extract_field_ops("c", _cand_fields())
    assert len(ops) > 0
    assert all(o.op_type == "field_delta" for o in ops)


def test_T83_CFAE_09_field_ops_skip_zero_values():
    """T83-CFAE-09: Zero-value fields produce no ops (noise suppression)."""
    ops = _extract_field_ops("c", {"expected_gain": 0.0, "risk_score": 0.0})
    assert ops == []


def test_T83_CFAE_10_field_ops_sorted_determinism():
    """T83-CFAE-10: CFAE-DET-0 — field ops sorted by op_key."""
    ops = _extract_field_ops("c", _cand_fields())
    keys = [o.op_key for o in ops]
    assert keys == sorted(keys)


# ===========================================================================
# MutationAblator — decompose and subsets
# ===========================================================================


def test_T83_CFAE_11_ablator_decompose_with_source():
    """T83-CFAE-11: decompose produces ops and subsets for source-rich candidate."""
    ablator = MutationAblator()
    ops, subsets = ablator.decompose("c", python_content=AFTER_SRC, before_source=BEFORE_SRC)
    assert len(ops) > 0
    assert len(subsets) > 0


def test_T83_CFAE_12_ablator_decompose_fallback_fields():
    """T83-CFAE-12: decompose falls back to field ops when no source."""
    ablator = MutationAblator()
    ops, subsets = ablator.decompose("c", candidate_fields=_cand_fields())
    assert len(ops) > 0
    assert all(o.op_type == "field_delta" for o in ops)


def test_T83_CFAE_13_ablator_exact_subsets_small_n():
    """T83-CFAE-13: n ≤ 8 ops → 2^n - 1 subsets (exact Shapley)."""
    ablator = MutationAblator()
    ops = [
        MutationOperation(op_id=f"op-{i:03d}", op_key=f"k{i}", op_type="field_delta", description="x")
        for i in range(3)
    ]
    subsets = ablator._generate_subsets(ops)
    assert len(subsets) == 7  # 2^3 - 1


def test_T83_CFAE_14_ablator_subsets_deterministic():
    """T83-CFAE-14: CFAE-DET-0 — generate_subsets identical for same ops."""
    ablator = MutationAblator()
    ops = [
        MutationOperation(op_id=f"op-{i:03d}", op_key=f"k{i}", op_type="field_delta", description="x")
        for i in range(4)
    ]
    s1 = ablator._generate_subsets(ops)
    s2 = ablator._generate_subsets(ops)
    assert [tuple(sorted(s)) for s in s1] == [tuple(sorted(s)) for s in s2]


def test_T83_CFAE_15_ablator_large_n_approximation():
    """T83-CFAE-15: n > 8 ops → approximation subsets generated."""
    ablator = MutationAblator()
    ops = [
        MutationOperation(op_id=f"op-{i:03d}", op_key=f"k{i}", op_type="field_delta", description="x")
        for i in range(10)
    ]
    subsets = ablator._generate_subsets(ops)
    # Single-op (10) + leave-one-out (10) + full (1) = at most 21, deduped
    assert len(subsets) <= 21
    assert len(subsets) >= 10


def test_T83_CFAE_16_ablator_contexts_count_matches_subsets():
    """T83-CFAE-16: generate_ablated_contexts returns one context per subset."""
    ablator = MutationAblator()
    ops = [
        MutationOperation(op_id=f"op-{i:03d}", op_key=f"k{i}", op_type="field_delta",
                          description="x", weight=0.5)
        for i in range(3)
    ]
    subsets = ablator._generate_subsets(ops)
    contexts = ablator.generate_ablated_contexts(_ctx(), ops, subsets)
    assert len(contexts) == len(subsets)


# ===========================================================================
# CFAE-BOUND-0
# ===========================================================================


def test_T83_CFAE_17_clamp_bounds():
    """T83-CFAE-17: CFAE-BOUND-0 — _clamp enforces [-1.0, 1.0]."""
    assert _clamp(5.0) == 1.0
    assert _clamp(-5.0) == -1.0
    assert _clamp(0.5) == 0.5


def test_T83_CFAE_18_tag_mapping():
    """T83-CFAE-18: _tag maps score ranges to correct tags."""
    assert _tag(0.9) == "CAUSAL-HIGH"
    assert _tag(0.08) == "CAUSAL-MED"
    assert _tag(0.02) == "CAUSAL-LOW"
    assert _tag(-0.1) == "CAUSAL-NEGATIVE"


# ===========================================================================
# CausalFitnessAttributor — full pipeline
# ===========================================================================


def test_T83_CFAE_19_attribute_returns_report():
    """T83-CFAE-19: attribute() returns CausalAttributionReport."""
    attr = CausalFitnessAttributor()
    report = attr.attribute(
        "cand-1", _ctx(),
        python_content=AFTER_SRC, before_source=BEFORE_SRC,
    )
    assert isinstance(report, CausalAttributionReport)
    assert report.candidate_id == "cand-1"
    assert report.schema_version == CFAE_VERSION


def test_T83_CFAE_20_cfae_advisory_no_gate_import():
    """T83-CFAE-20: CFAE-0 — causal_fitness_attributor never imports GovernanceGate at runtime."""
    import runtime.evolution.causal_fitness_attributor as m
    src = open(m.__file__).read()
    # Docstrings may mention GovernanceGate; what matters is no import or call
    assert "import GovernanceGate" not in src
    assert "from runtime.governance.gate" not in src
    assert "GovernanceGate(" not in src


def test_T83_CFAE_21_all_scores_bounded():
    """T83-CFAE-21: CFAE-BOUND-0 — all attribution_scores in [-1.0, 1.0]."""
    attr = CausalFitnessAttributor()
    report = attr.attribute(
        "cand-bound", _ctx(), candidate_fields=_cand_fields(),
    )
    for a in report.attributions:
        assert -1.0 <= a.attribution_score <= 1.0, f"{a.op_key}: {a.attribution_score}"


def test_T83_CFAE_22_determinism_identical_inputs():
    """T83-CFAE-22: CFAE-DET-0 — identical inputs produce identical reports."""
    attr = CausalFitnessAttributor()
    r1 = attr.attribute("c", _ctx(), candidate_fields=_cand_fields())
    r2 = attr.attribute("c", _ctx(), candidate_fields=_cand_fields())
    assert r1.report_digest == r2.report_digest
    assert [a.attribution_score for a in r1.attributions] == \
           [a.attribution_score for a in r2.attributions]


def test_T83_CFAE_23_report_roundtrip():
    """T83-CFAE-23: CausalAttributionReport to_dict/from_dict round-trip."""
    attr = CausalFitnessAttributor()
    report = attr.attribute("c", _ctx(), candidate_fields=_cand_fields())
    r2 = CausalAttributionReport.from_dict(report.to_dict())
    assert report.report_digest == r2.report_digest
    assert report.candidate_id == r2.candidate_id
    assert len(report.attributions) == len(r2.attributions)


def test_T83_CFAE_24_cfae_ledger_written():
    """T83-CFAE-24: CFAE-LEDGER-0 — report written to ledger when injected."""
    with tempfile.TemporaryDirectory() as td:
        ledger = _make_ledger(pathlib.Path(td))
        attr = CausalFitnessAttributor(ledger=ledger)
        attr.attribute("c", _ctx(), candidate_fields=_cand_fields())
        lines = ledger.ledger_path.read_text().strip().splitlines()
        events = [json.loads(l) for l in lines]
        assert any(e["type"] == "CausalAttributionReport" for e in events)


def test_T83_CFAE_25_cfae_ledger_payload_has_candidate_id():
    """T83-CFAE-25: CFAE-LEDGER-0 — ledger entry has candidate_id."""
    with tempfile.TemporaryDirectory() as td:
        ledger = _make_ledger(pathlib.Path(td))
        attr = CausalFitnessAttributor(ledger=ledger)
        attr.attribute("my-cand-99", _ctx(), candidate_fields=_cand_fields())
        events = [json.loads(l) for l in ledger.ledger_path.read_text().strip().splitlines()]
        cfae_events = [e for e in events if e["type"] == "CausalAttributionReport"]
        assert cfae_events[-1]["payload"]["candidate_id"] == "my-cand-99"


def test_T83_CFAE_26_top_ops_are_causal_high():
    """T83-CFAE-26: top_ops contain only CAUSAL-HIGH tagged attributions."""
    attr = CausalFitnessAttributor()
    report = attr.attribute("c", _ctx(), candidate_fields=_cand_fields())
    high_ids = {a.op_id for a in report.attributions if a.tag == "CAUSAL-HIGH"}
    assert set(report.top_ops) == high_ids


def test_T83_CFAE_27_negative_ops_are_causal_negative():
    """T83-CFAE-27: negative_ops contain only CAUSAL-NEGATIVE tagged attributions."""
    attr = CausalFitnessAttributor()
    report = attr.attribute("c", _ctx(), candidate_fields=_cand_fields())
    neg_ids = {a.op_id for a in report.attributions if a.tag == "CAUSAL-NEGATIVE"}
    assert set(report.negative_ops) == neg_ids


def test_T83_CFAE_28_no_source_or_fields_trivial_report():
    """T83-CFAE-28: No source or fields → trivial report (no crash, CFAE-0 safe)."""
    attr = CausalFitnessAttributor()
    report = attr.attribute("c-opaque", _ctx())
    assert isinstance(report, CausalAttributionReport)
    assert report.candidate_id == "c-opaque"
    # Either trivial (0 ops) or synthetic single op — no crash
    assert isinstance(report.total_ops_analysed, int)
