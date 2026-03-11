# SPDX-License-Identifier: Apache-2.0
"""Tests for runtime.evolution.fast_path_scorer."""

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.fast_path_scorer import (
    FAST_PATH_VERSION,
    fast_path_score,
    is_fast_path_score,
)


def test_fast_path_score_structure_zero_loc():
    score = fast_path_score(
        mutation_id="mut_001",
        reason="zero_loc_delta",
        loc_added=0,
        loc_deleted=0,
    )
    assert score["passed_syntax"] is True
    assert score["passed_tests"] is True
    assert score["passed_constitution"] is True
    assert 0.0 < score["score"] <= 1.0
    assert score["mutation_id"] == "mut_001"
    assert score["fast_path_score_version"] == FAST_PATH_VERSION
    assert "score_digest" in score


def test_fast_path_score_structure_doc_only():
    score = fast_path_score(
        mutation_id="mut_002",
        reason="doc_only_ops",
        loc_added=5,
        loc_deleted=2,
    )
    assert score["fast_path_reason"] == "doc_only_ops"
    assert is_fast_path_score(score) is True


def test_fast_path_score_structure_metadata():
    score = fast_path_score(
        mutation_id="mut_003",
        reason="metadata_only_ops",
    )
    assert score["fast_path_reason"] == "metadata_only_ops"


def test_identical_inputs_produce_identical_digest():
    s1 = fast_path_score(mutation_id="mut_x", reason="zero_loc_delta")
    s2 = fast_path_score(mutation_id="mut_x", reason="zero_loc_delta")
    assert s1["score_digest"] == s2["score_digest"]


def test_different_mutation_ids_produce_different_digest():
    s1 = fast_path_score(mutation_id="mut_a", reason="zero_loc_delta")
    s2 = fast_path_score(mutation_id="mut_b", reason="zero_loc_delta")
    assert s1["score_digest"] != s2["score_digest"]


def test_loc_fields_recorded_in_payload():
    score = fast_path_score(
        mutation_id="mut_y", reason="zero_loc_delta", loc_added=7, loc_deleted=3
    )
    assert score["loc_added"] == 7
    assert score["loc_deleted"] == 3


def test_is_fast_path_score_false_for_normal_payload():
    assert is_fast_path_score({"score": 0.8, "passed_syntax": True}) is False


def test_is_fast_path_score_true_for_fast_path_payload():
    score = fast_path_score(mutation_id="m", reason="zero_loc_delta")
    assert is_fast_path_score(score) is True
