import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

import ast


def _cyclomatic_complexity(source: str) -> int:
    tree = ast.parse(source)
    complexity = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.IfExp, ast.AsyncFor, ast.AsyncWith)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += max(0, len(node.values) - 1)
        elif isinstance(node, ast.comprehension):
            complexity += 1
    return complexity


def test_complexity_delta_detects_increase() -> None:
    baseline = """
def f(x):
    return x
"""
    candidate = """
def f(x):
    if x > 1:
        for i in range(x):
            if i % 2 == 0:
                return i
    return x
"""
    baseline_complexity = _cyclomatic_complexity(baseline)
    candidate_complexity = _cyclomatic_complexity(candidate)

    assert candidate_complexity > baseline_complexity
    assert (candidate_complexity - baseline_complexity) == 3
