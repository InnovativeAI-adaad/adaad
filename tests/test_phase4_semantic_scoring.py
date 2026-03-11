# SPDX-License-Identifier: Apache-2.0
"""Tests for PR-PHASE4-02: SemanticDiffEngine wired into scoring pipeline.

Coverage:
  - scoring_algorithm.py: ALGORITHM_VERSION bump, compute_semantic_penalties,
    compute_score with before/after source, algorithm_version routing,
    semantic_diff_version provenance, fallback behaviour, determinism
  - mutation_scaffold.py: MutationCandidate.python_content field,
    score_candidate semantic enrichment, semantic_scoring_active flag,
    fallback to original scores, backward compat (no python_content)
  - ai_mutation_proposer.py: python_content threaded from proposal payload
  - End-to-end: SemanticDiffEngine scores flow through to MutationScore
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.autonomy.mutation_scaffold import MutationCandidate, MutationScore, score_candidate
from runtime.evolution.scoring_algorithm import (
    ALGORITHM_VERSION,
    SEMANTIC_ALGORITHM_VERSION,
    compute_score,
    compute_semantic_penalties,
)
from runtime.evolution.semantic_diff import ALGORITHM_VERSION as SEM_VERSION_CONSTANT
from runtime.governance.foundation import SeededDeterminismProvider

# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_SRC = """\
def add(a, b):
    return a + b
"""

COMPLEX_SRC = """\
import os
import sys
import json
import hashlib

def process(data, mode, flags):
    if mode == "strict":
        for item in data:
            if flags.get("validate"):
                if not isinstance(item, dict):
                    raise ValueError("bad item")
                for k, v in item.items():
                    if k.startswith("_"):
                        continue
                    print(k, v)
    elif mode == "fast":
        return [x for x in data if x]
    return data
"""

INVALID_SRC = "def broken(:\n    pass\n"  # SyntaxError


def _sample_input(**overrides) -> dict:
    base = {
        "mutation_id": "mut-semantic-01",
        "epoch_id": "epoch-s01",
        "constitution_hash": "sha256:" + "a" * 64,
        "test_results": {"total": 10, "failed": 0},
        "static_analysis": {"issues": []},
        "code_diff": {
            "loc_added": 5,
            "loc_deleted": 2,
            "files_touched": 1,
            "risk_tags": [],
        },
    }
    base.update(overrides)
    return base


def _prov(seed: str = "sem-test") -> SeededDeterminismProvider:
    return SeededDeterminismProvider(seed=seed)


# ── ALGORITHM_VERSION ─────────────────────────────────────────────────────────


def test_algorithm_version_bumped_to_v1_2():
    assert ALGORITHM_VERSION == "v1.2.0"


def test_semantic_algorithm_version_compound():
    assert SEMANTIC_ALGORITHM_VERSION == "v1.2.0+semantic_diff_v1.0"
    assert SEM_VERSION_CONSTANT in SEMANTIC_ALGORITHM_VERSION


# ── compute_semantic_penalties ────────────────────────────────────────────────


def test_compute_semantic_penalties_simple_source():
    dp, rp, alg, fallback = compute_semantic_penalties("", SIMPLE_SRC)
    assert not fallback
    assert alg == SEMANTIC_ALGORITHM_VERSION
    assert 0 <= dp <= 500
    assert 0 <= rp <= 300


def test_compute_semantic_penalties_complex_higher_than_simple():
    dp_s, rp_s, _, _ = compute_semantic_penalties("", SIMPLE_SRC)
    dp_c, rp_c, _, _ = compute_semantic_penalties("", COMPLEX_SRC)
    # Complex source has more imports and branches → higher risk + complexity
    assert dp_c >= dp_s
    assert rp_c >= rp_s


def test_compute_semantic_penalties_invalid_source_fallback():
    dp, rp, alg, fallback = compute_semantic_penalties("", INVALID_SRC)
    assert fallback
    assert alg == ALGORITHM_VERSION
    assert dp == 0 and rp == 0  # caller falls back to LOC/tags


def test_compute_semantic_penalties_none_after_fallback():
    dp, rp, alg, fallback = compute_semantic_penalties("", None)
    assert fallback


def test_compute_semantic_penalties_before_after_delta():
    # Empty before → full after-state as delta
    dp_empty, rp_empty, _, _ = compute_semantic_penalties("", COMPLEX_SRC)
    # Same before and after → zero structural delta
    dp_same, rp_same, _, _ = compute_semantic_penalties(COMPLEX_SRC, COMPLEX_SRC)
    assert dp_empty >= dp_same
    assert rp_empty >= rp_same


def test_compute_semantic_penalties_determinism():
    for _ in range(20):
        r1 = compute_semantic_penalties("", COMPLEX_SRC)
        r2 = compute_semantic_penalties("", COMPLEX_SRC)
        assert r1 == r2


# ── compute_score — LOC fallback path ─────────────────────────────────────────


def test_compute_score_no_source_uses_loc_path():
    result = compute_score(_sample_input(), provider=_prov(), replay_mode="strict")
    assert result["algorithm_version"] == ALGORITHM_VERSION
    assert "semantic_diff_version" not in result


def test_compute_score_no_source_algorithm_version_v1_2():
    result = compute_score(_sample_input(), provider=_prov(), replay_mode="strict")
    assert result["algorithm_version"] == "v1.2.0"


def test_compute_score_loc_path_components_present():
    result = compute_score(_sample_input(), provider=_prov(), replay_mode="strict")
    for key in ("diff_penalty", "risk_penalty", "test_score", "static_penalty"):
        assert key in result["components"]


# ── compute_score — semantic path ─────────────────────────────────────────────


def test_compute_score_with_after_source_uses_semantic_path():
    result = compute_score(
        _sample_input(), provider=_prov("sem"), replay_mode="strict",
        after_source=SIMPLE_SRC,
    )
    assert result["algorithm_version"] == SEMANTIC_ALGORITHM_VERSION


def test_compute_score_semantic_provenance_fields():
    result = compute_score(
        _sample_input(), provider=_prov("prov"), replay_mode="strict",
        after_source=SIMPLE_SRC,
    )
    assert result["semantic_diff_version"] == SEMANTIC_ALGORITHM_VERSION
    assert result["semantic_fallback_used"] is False


def test_compute_score_invalid_source_falls_back_to_loc():
    result = compute_score(
        _sample_input(), provider=_prov("inv"), replay_mode="strict",
        after_source=INVALID_SRC,
    )
    # SemanticDiffEngine returns fallback=True → LOC path used
    assert result["algorithm_version"] == ALGORITHM_VERSION
    assert "semantic_diff_version" not in result


def test_compute_score_semantic_diff_penalty_bounded():
    result = compute_score(
        _sample_input(), provider=_prov("bound"), replay_mode="strict",
        after_source=COMPLEX_SRC,
    )
    comps = result["components"]
    assert 0 <= comps["diff_penalty"] <= 500
    assert 0 <= comps["risk_penalty"] <= 300


def test_compute_score_complex_vs_simple_higher_penalties():
    r_simple = compute_score(
        _sample_input(mutation_id="s"), provider=_prov("cmp-s"), replay_mode="strict",
        after_source=SIMPLE_SRC,
    )
    r_complex = compute_score(
        _sample_input(mutation_id="c"), provider=_prov("cmp-c"), replay_mode="strict",
        after_source=COMPLEX_SRC,
    )
    # Complex source has more imports and branches → higher penalties
    total_simple  = r_simple["components"]["diff_penalty"]  + r_simple["components"]["risk_penalty"]
    total_complex = r_complex["components"]["diff_penalty"] + r_complex["components"]["risk_penalty"]
    assert total_complex >= total_simple


def test_compute_score_before_and_after_source():
    result = compute_score(
        _sample_input(), provider=_prov("ba"), replay_mode="strict",
        before_source=SIMPLE_SRC,
        after_source=COMPLEX_SRC,
    )
    assert result["algorithm_version"] == SEMANTIC_ALGORITHM_VERSION


def test_compute_score_score_non_negative():
    result = compute_score(
        _sample_input(), provider=_prov("neg"), replay_mode="strict",
        after_source=COMPLEX_SRC,
    )
    assert result["score"] >= 0


def test_compute_score_required_fields_present():
    result = compute_score(
        _sample_input(), provider=_prov("req"), replay_mode="strict",
        after_source=SIMPLE_SRC,
    )
    for field in ("mutation_id", "epoch_id", "score", "input_hash",
                  "algorithm_version", "constitution_hash", "timestamp", "components"):
        assert field in result


# ── Determinism: semantic path ────────────────────────────────────────────────


def test_compute_score_semantic_determinism():
    """Same inputs → identical score + input_hash (timestamp excluded)."""
    payload = _sample_input()
    results = [
        compute_score(payload, provider=_prov("det"), replay_mode="strict", after_source=COMPLEX_SRC)
        for _ in range(5)
    ]
    scores = {r["score"] for r in results}
    hashes = {r["input_hash"] for r in results}
    algs   = {r["algorithm_version"] for r in results}
    assert len(scores) == 1
    assert len(hashes) == 1
    assert len(algs)   == 1


def test_compute_score_before_after_same_gives_zero_risk_penalty():
    """Identical before/after → risk delta = 0 → risk_penalty = 0.
    diff_penalty (complexity) uses absolute after-state metrics so remains non-zero
    for non-trivial source — that is correct and expected behaviour.
    """
    result = compute_score(
        _sample_input(), provider=_prov("zero"), replay_mode="strict",
        before_source=COMPLEX_SRC,
        after_source=COMPLEX_SRC,
    )
    # Risk formula uses deltas only — zero delta → zero risk penalty
    assert result["components"]["risk_penalty"] == 0
    # Complexity uses absolute after-state — may be non-zero for non-trivial source
    assert result["components"]["diff_penalty"] >= 0


# ── MutationCandidate.python_content ──────────────────────────────────────────


def test_mutation_candidate_python_content_default_none():
    c = MutationCandidate("m", 0.5, 0.3, 0.3, 0.2)
    assert c.python_content is None


def test_mutation_candidate_python_content_set():
    c = MutationCandidate("m", 0.5, 0.3, 0.3, 0.2, python_content=SIMPLE_SRC)
    assert c.python_content == SIMPLE_SRC


def test_mutation_candidate_python_content_keyword_only():
    # Positional fields unchanged; python_content is keyword-only
    c = MutationCandidate("m", 0.8, 0.1, 0.2, 0.5, python_content=COMPLEX_SRC)
    assert c.mutation_id == "m"
    assert c.expected_gain == 0.8


# ── score_candidate — semantic enrichment ────────────────────────────────────


def test_score_candidate_no_content_uses_candidate_fields():
    c = MutationCandidate("m_no_content", 0.8, 0.2, 0.2, 0.5)
    result = score_candidate(c)
    assert result.dimension_breakdown["semantic_scoring_active"] == 0.0


def test_score_candidate_with_valid_content_activates_semantic():
    c = MutationCandidate("m_valid", 0.8, 0.2, 0.2, 0.5, python_content=COMPLEX_SRC)
    result = score_candidate(c)
    assert result.dimension_breakdown["semantic_scoring_active"] == 1.0


def test_score_candidate_with_invalid_content_falls_back():
    c = MutationCandidate("m_bad", 0.8, 0.2, 0.2, 0.5, python_content=INVALID_SRC)
    result = score_candidate(c)
    assert result.dimension_breakdown["semantic_scoring_active"] == 0.0


def test_score_candidate_semantic_changes_penalties():
    """High-complexity python_content should penalise score relative to no-content."""
    c_no  = MutationCandidate("m_no",   0.8, 0.0, 0.0, 0.5)
    c_src = MutationCandidate("m_src",  0.8, 0.0, 0.0, 0.5, python_content=COMPLEX_SRC)
    s_no  = score_candidate(c_no)
    s_src = score_candidate(c_src)
    # Complex source raises risk/complexity → lower score
    assert s_src.score <= s_no.score


def test_score_candidate_semantic_determinism():
    """Same candidate with same python_content → identical MutationScore."""
    c = MutationCandidate("m_det", 0.7, 0.2, 0.3, 0.4, python_content=SIMPLE_SRC)
    scores = {score_candidate(c).score for _ in range(20)}
    assert len(scores) == 1


def test_score_candidate_simple_content_lower_penalty_than_complex():
    c_simple  = MutationCandidate("ms", 0.8, 0.0, 0.0, 0.5, python_content=SIMPLE_SRC)
    c_complex = MutationCandidate("mc", 0.8, 0.0, 0.0, 0.5, python_content=COMPLEX_SRC)
    s_simple  = score_candidate(c_simple)
    s_complex = score_candidate(c_complex)
    assert s_simple.score >= s_complex.score


def test_score_candidate_backward_compat_no_python_content():
    """Existing call sites without python_content work unchanged."""
    c = MutationCandidate(
        mutation_id="compat_01",
        expected_gain=0.6,
        risk_score=0.3,
        complexity=0.2,
        coverage_delta=0.4,
        agent_origin="beast",
        epoch_id="ep_01",
    )
    result = score_candidate(c)
    assert isinstance(result, MutationScore)
    assert 0.0 <= result.score <= 1.0


def test_score_candidate_semantic_scoring_active_in_breakdown():
    c = MutationCandidate("m_bd", 0.8, 0.2, 0.2, 0.5, python_content=SIMPLE_SRC)
    result = score_candidate(c)
    assert "semantic_scoring_active" in result.dimension_breakdown


# ── ai_mutation_proposer — python_content threading ──────────────────────────


def test_proposer_threads_python_content_from_payload():
    """_parse_proposals picks up python_content from the raw JSON response."""
    import json as _json
    from runtime.autonomy.ai_mutation_proposer import _parse_proposals, CodebaseContext

    ctx = CodebaseContext(
        file_summaries={},
        recent_failures=[],
        current_epoch_id="ep_test",
    )
    proposals_raw = [
        {
            "mutation_id": "prop_01",
            "expected_gain": 0.5,
            "risk_score": 0.3,
            "complexity": 0.2,
            "coverage_delta": 0.1,
            "python_content": SIMPLE_SRC,
        }
    ]
    candidates = _parse_proposals(
        _json.dumps(proposals_raw), agent="architect", context=ctx
    )
    assert len(candidates) == 1
    assert candidates[0].python_content == SIMPLE_SRC


def test_proposer_handles_missing_python_content():
    import json as _json
    from runtime.autonomy.ai_mutation_proposer import _parse_proposals, CodebaseContext

    ctx = CodebaseContext(file_summaries={}, recent_failures=[], current_epoch_id="ep2")
    proposals_raw = [{"mutation_id": "p2", "expected_gain": 0.4, "risk_score": 0.2, "complexity": 0.1, "coverage_delta": 0.1}]
    candidates = _parse_proposals(_json.dumps(proposals_raw), agent="beast", context=ctx)
    assert candidates[0].python_content is None
