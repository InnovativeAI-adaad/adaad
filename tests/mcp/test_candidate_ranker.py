# SPDX-License-Identifier: Apache-2.0
import pytest
pytestmark = pytest.mark.regression_standard

from runtime.mcp.candidate_ranker import rank_candidates


def test_rank_sorted_desc_and_deterministic():
    ids = ["m3", "m1", "m2"]
    a = rank_candidates(ids)
    b = rank_candidates(ids)
    assert a == b
    scores = [row["score"] for row in a["ranked"]]
    assert scores == sorted(scores, reverse=True)


def test_empty_list_400_contract():
    with pytest.raises(ValueError):
        rank_candidates([])
