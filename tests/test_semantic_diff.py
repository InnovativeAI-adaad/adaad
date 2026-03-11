# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import ast
import pytest
pytestmark = pytest.mark.regression_standard
from runtime.evolution.semantic_diff import (
    SemanticDiffEngine, ASTMetrics, enrich_code_diff_with_semantic,
    ALGORITHM_VERSION, _max_ast_depth, _cyclomatic_complexity, _clamp01,
)

SIMPLE = "def foo():\n    return 1\n"
NESTED = (
    "import os\n"
    "class A:\n"
    "    def m(self, x):\n"
    "        if x:\n"
    "            for i in range(x):\n"
    "                while i > 0:\n"
    "                    try:\n"
    "                        print(i)\n"
    "                    except Exception:\n"
    "                        pass\n"
    "                    i -= 1\n"
    "        return x\n"
)


@pytest.fixture
def eng():
    return SemanticDiffEngine()


class TestASTMetrics:
    def test_simple_source(self):
        m = ASTMetrics.from_source(SIMPLE)
        assert m.node_count > 0 and m.function_count == 1 and m.cyclomatic >= 1

    def test_complex_higher(self):
        s, c = ASTMetrics.from_source(SIMPLE), ASTMetrics.from_source(NESTED)
        assert c.node_count > s.node_count and c.max_depth > s.max_depth

    def test_syntax_error_raises(self):
        with pytest.raises(SyntaxError):
            ASTMetrics.from_source("def(invalid")

    def test_class_count(self):
        assert ASTMetrics.from_source(NESTED).class_count >= 1


class TestSemanticDiff:
    def test_simple_to_complex_bounded(self, eng):
        d = eng.diff(SIMPLE, NESTED)
        assert not d.fallback_used and 0 <= d.risk_score <= 1 and 0 <= d.complexity_score <= 1

    def test_identical_zero_risk(self, eng):
        assert eng.diff(SIMPLE, SIMPLE).risk_score == pytest.approx(0.0)

    def test_none_fallback(self, eng):
        d = eng.diff(None, SIMPLE)
        assert d.fallback_used and d.risk_score == pytest.approx(0.5)

    def test_unparseable_fallback(self, eng):
        assert eng.diff("def(bad", SIMPLE).fallback_used

    def test_algorithm_version(self, eng):
        assert eng.diff(SIMPLE, SIMPLE).algorithm_version == ALGORITHM_VERSION

    def test_to_dict(self, eng):
        d = eng.diff(SIMPLE, NESTED).to_dict()
        for k in ("risk_score", "complexity_score", "algorithm_version", "fallback_used"):
            assert k in d

    def test_complex_higher_complexity(self, eng):
        assert eng.diff(SIMPLE, NESTED).complexity_score >= eng.diff(SIMPLE, SIMPLE).complexity_score

    def test_has_metrics(self, eng):
        d = eng.diff(SIMPLE, NESTED)
        assert d.before is not None and d.after is not None


class TestDiffFromCodeDiff:
    def test_empty_dict(self, eng):
        d = eng.diff_from_code_diff({})
        assert 0 <= d.risk_score <= 1 and d.fallback_used

    def test_large_loc_higher_risk(self, eng):
        lo = eng.diff_from_code_diff({"loc_added": 5, "files_touched": 1})
        hi = eng.diff_from_code_diff({"loc_added": 5000, "files_touched": 50})
        assert hi.risk_score >= lo.risk_score

    def test_deterministic(self, eng):
        cd = {"loc_added": 100, "files_touched": 3}
        assert eng.diff_from_code_diff(cd).risk_score == eng.diff_from_code_diff(cd).risk_score


class TestHelpers:
    def test_depth_nesting(self):
        flat, deep = "x = 1\n", "if True:\n    if True:\n        x = 1\n"
        assert _max_ast_depth(ast.parse(deep)) > _max_ast_depth(ast.parse(flat))

    def test_cyclomatic_branches(self):
        s = "def f(x):\n    if x > 0:\n        return True\n    return False\n"
        assert _cyclomatic_complexity(ast.parse(s)) >= 2

    def test_clamp(self):
        assert _clamp01(-1) == 0 and _clamp01(2) == 1 and _clamp01(0.5) == pytest.approx(0.5)


class TestEnrich:
    def test_adds_semantic_keys(self):
        e = enrich_code_diff_with_semantic({"loc_added": 20}, SIMPLE, NESTED)
        assert "semantic_risk_score" in e and not e["semantic_fallback_used"]

    def test_preserves_original(self):
        e = enrich_code_diff_with_semantic({"loc_added": 10})
        assert e["loc_added"] == 10

    def test_fallback_without_source(self):
        assert enrich_code_diff_with_semantic({"loc_added": 50})["semantic_fallback_used"]

    def test_deterministic(self):
        cd = {"loc_added": 30}
        e1, e2 = enrich_code_diff_with_semantic(cd, SIMPLE, NESTED), enrich_code_diff_with_semantic(cd, SIMPLE, NESTED)
        assert e1["semantic_risk_score"] == e2["semantic_risk_score"]
