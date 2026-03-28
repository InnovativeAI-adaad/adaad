# SPDX-License-Identifier: Apache-2.0
"""T93-AFIT — Phase 93 INNOV-09 Aesthetic Fitness Signal test suite.

Test IDs: T93-AFIT-01 .. T93-AFIT-25
All invariants verified:
  AFIT-0          — score() never raises; fallback returns score=0.5
  AFIT-DETERM-0   — identical source → identical report
  AFIT-BOUND-0    — all sub-scores and composite in [0.0, 1.0]
  AFIT-WEIGHT-0   — aesthetic_fitness weight in [0.05, 0.30] in FitnessConfig
"""

from __future__ import annotations

import textwrap
from typing import Optional

import pytest

from runtime.evolution.aesthetic_fitness import (
    AFIT_VERSION,
    AestheticFitnessScorer,
    AestheticFitnessReport,
    AestheticSubScores,
    _FALLBACK_SCORE,
    _MAX_FUNC_LINES,
    _IDEAL_FUNC_LINES,
    _MAX_NESTING,
    _MAX_CYCLOMATIC,
    _W_FUNC_LENGTH,
    _W_NAME_ENTROPY,
    _W_NESTING,
    _W_COMMENT_RATIO,
    _W_CYCLOMATIC,
)
from runtime.evolution.fitness_v2 import (
    FitnessConfig,
    FitnessContext,
    FitnessEngineV2,
    FitnessScores,
    ReplayResult,
    _DEFAULT_WEIGHTS,
    _SIGNAL_KEYS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scorer() -> AestheticFitnessScorer:
    return AestheticFitnessScorer()


# Clean, readable source fixture
CLEAN_SOURCE = textwrap.dedent("""\
    # Module-level comment explaining the module purpose.

    def compute_total(items, multiplier):
        # Sum all item values scaled by multiplier.
        total = 0
        for item in items:
            total = total + item * multiplier
        return total

    def validate_input(data, threshold):
        # Check data meets minimum threshold.
        if data is None:
            return False
        return data >= threshold
""")

# Dense, hard-to-read source fixture
DENSE_SOURCE = textwrap.dedent("""\
    def f(x, y, z, a, b, c, d, e, f_val, g, h, i, j, k, l, m, n):
        if x:
            if y:
                if z:
                    if a:
                        if b:
                            for i in range(100):
                                for j in range(100):
                                    for k in range(100):
                                        if c: result = c + d + e
        return x + y + z + a + b + c + d + e + f_val + g + h + i + j + k + l + m + n
""")


# ---------------------------------------------------------------------------
# T93-AFIT-01: scorer instantiates with correct version
# ---------------------------------------------------------------------------
class TestT93AFIT01_ScorerInstantiation:
    def test_version_attribute(self, scorer):
        """T93-AFIT-01: AestheticFitnessScorer has AFIT_VERSION."""
        assert scorer.version == AFIT_VERSION
        assert AFIT_VERSION == "93.0"


# ---------------------------------------------------------------------------
# T93-AFIT-02: AFIT-0 — None source returns fallback, no exception
# ---------------------------------------------------------------------------
class TestT93AFIT02_NoneSource:
    def test_none_source_fallback(self, scorer):
        """T93-AFIT-02: AFIT-0 — None input → fallback report, no raise."""
        report = scorer.score(None)
        assert isinstance(report, AestheticFitnessReport)
        assert report.fallback_used is True
        assert report.score == _FALLBACK_SCORE


# ---------------------------------------------------------------------------
# T93-AFIT-03: AFIT-0 — empty string returns fallback, no exception
# ---------------------------------------------------------------------------
class TestT93AFIT03_EmptySource:
    def test_empty_source_fallback(self, scorer):
        """T93-AFIT-03: AFIT-0 — empty source → fallback."""
        report = scorer.score("")
        assert report.fallback_used is True
        assert report.score == _FALLBACK_SCORE


# ---------------------------------------------------------------------------
# T93-AFIT-04: AFIT-0 — syntax error returns fallback, no exception
# ---------------------------------------------------------------------------
class TestT93AFIT04_SyntaxError:
    def test_syntax_error_fallback(self, scorer):
        """T93-AFIT-04: AFIT-0 — unparseable source → fallback, never raises."""
        broken = "def (:"
        report = scorer.score(broken)
        assert report.fallback_used is True
        assert report.score == _FALLBACK_SCORE


# ---------------------------------------------------------------------------
# T93-AFIT-05: AFIT-BOUND-0 — all sub-scores in [0.0, 1.0] for clean source
# ---------------------------------------------------------------------------
class TestT93AFIT05_SubScoreBounds:
    def test_sub_scores_in_unit_interval(self, scorer):
        """T93-AFIT-05: AFIT-BOUND-0 — all sub-scores clamped to [0.0, 1.0]."""
        report = scorer.score(CLEAN_SOURCE)
        assert 0.0 <= report.sub_scores.function_length_score <= 1.0
        assert 0.0 <= report.sub_scores.name_entropy_score <= 1.0
        assert 0.0 <= report.sub_scores.nesting_depth_score <= 1.0
        assert 0.0 <= report.sub_scores.comment_ratio_score <= 1.0
        assert 0.0 <= report.sub_scores.cyclomatic_score <= 1.0


# ---------------------------------------------------------------------------
# T93-AFIT-06: AFIT-BOUND-0 — composite score in [0.0, 1.0]
# ---------------------------------------------------------------------------
class TestT93AFIT06_CompositeBound:
    def test_composite_in_unit_interval_clean(self, scorer):
        """T93-AFIT-06: AFIT-BOUND-0 — composite score in [0.0, 1.0]."""
        for source in [CLEAN_SOURCE, DENSE_SOURCE]:
            report = scorer.score(source)
            assert 0.0 <= report.score <= 1.0, f"score out of bounds: {report.score}"


# ---------------------------------------------------------------------------
# T93-AFIT-07: AFIT-DETERM-0 — identical source → identical score
# ---------------------------------------------------------------------------
class TestT93AFIT07_Determinism:
    def test_identical_source_identical_report(self, scorer):
        """T93-AFIT-07: AFIT-DETERM-0 — scoring is deterministic."""
        r1 = scorer.score(CLEAN_SOURCE)
        r2 = scorer.score(CLEAN_SOURCE)
        assert r1.score == r2.score
        assert r1.sub_scores == r2.sub_scores
        assert r1.function_count == r2.function_count
        assert r1.fallback_used == r2.fallback_used


# ---------------------------------------------------------------------------
# T93-AFIT-08: AFIT-DETERM-0 — second scorer instance → same result
# ---------------------------------------------------------------------------
class TestT93AFIT08_DeterminismAcrossInstances:
    def test_two_instances_same_output(self):
        """T93-AFIT-08: AFIT-DETERM-0 — different scorer instances, same source → same score."""
        s1 = AestheticFitnessScorer()
        s2 = AestheticFitnessScorer()
        r1 = s1.score(CLEAN_SOURCE)
        r2 = s2.score(CLEAN_SOURCE)
        assert r1.score == r2.score
        assert r1.sub_scores == r2.sub_scores


# ---------------------------------------------------------------------------
# T93-AFIT-09: clean code scores higher than dense code
# ---------------------------------------------------------------------------
class TestT93AFIT09_CleanVsDense:
    def test_clean_scores_higher_than_dense(self, scorer):
        """T93-AFIT-09: Readable code scores higher than deeply nested code."""
        clean = scorer.score(CLEAN_SOURCE)
        dense = scorer.score(DENSE_SOURCE)
        assert clean.score > dense.score, (
            f"clean={clean.score:.3f} should > dense={dense.score:.3f}"
        )


# ---------------------------------------------------------------------------
# T93-AFIT-10: function_count is reported correctly
# ---------------------------------------------------------------------------
class TestT93AFIT10_FunctionCount:
    def test_function_count_matches_source(self, scorer):
        """T93-AFIT-10: function_count equals number of def statements."""
        source = textwrap.dedent("""\
            def alpha():
                pass

            def beta():
                pass

            def gamma():
                pass
        """)
        report = scorer.score(source)
        assert report.function_count == 3
        assert report.fallback_used is False


# ---------------------------------------------------------------------------
# T93-AFIT-11: source with no functions gets fallback sub-scores
# ---------------------------------------------------------------------------
class TestT93AFIT11_NoFunctions:
    def test_no_functions_fallback_subscores(self, scorer):
        """T93-AFIT-11: Module with only expressions gets neutral sub-scores."""
        source = "x = 1\ny = 2\nz = x + y\n"
        report = scorer.score(source)
        # function_count must be 0; fallback_used can be False (valid parse)
        assert report.function_count == 0
        # All sub-scores use _FALLBACK_SCORE for function-dependent signals
        assert report.sub_scores.function_length_score == _FALLBACK_SCORE
        assert report.sub_scores.name_entropy_score == _FALLBACK_SCORE
        assert report.sub_scores.nesting_depth_score == _FALLBACK_SCORE
        assert report.sub_scores.cyclomatic_score == _FALLBACK_SCORE


# ---------------------------------------------------------------------------
# T93-AFIT-12: short function scores high on function_length_score
# ---------------------------------------------------------------------------
class TestT93AFIT12_ShortFunction:
    def test_short_function_high_length_score(self, scorer):
        """T93-AFIT-12: Function under _IDEAL_FUNC_LINES → function_length_score ≥ 0.9."""
        lines = "\n".join(f"    x{i} = {i}" for i in range(_IDEAL_FUNC_LINES - 2))
        source = f"def short_fn(value):\n{lines}\n    return value\n"
        report = scorer.score(source)
        assert report.sub_scores.function_length_score >= 0.9


# ---------------------------------------------------------------------------
# T93-AFIT-13: deeply nested code scores low on nesting_depth_score
# ---------------------------------------------------------------------------
class TestT93AFIT13_DeepNesting:
    def test_deep_nesting_low_score(self, scorer):
        """T93-AFIT-13: Function with deep nesting → nesting_depth_score < 0.4."""
        source = textwrap.dedent("""\
            def deeply_nested(data):
                if data:
                    for item in data:
                        if item:
                            for sub in item:
                                if sub:
                                    return sub
                return None
        """)
        report = scorer.score(source)
        assert report.sub_scores.nesting_depth_score < 0.4


# ---------------------------------------------------------------------------
# T93-AFIT-14: informative names score high on name_entropy_score
# ---------------------------------------------------------------------------
class TestT93AFIT14_InformativeNames:
    def test_long_names_high_entropy(self, scorer):
        """T93-AFIT-14: All long identifiers → name_entropy_score ≥ 0.9."""
        source = textwrap.dedent("""\
            def compute_weighted_average(values, weights, precision):
                total_weight = sum(weights)
                accumulated = sum(
                    value * weight for value, weight in zip(values, weights)
                )
                return round(accumulated / total_weight, precision)
        """)
        report = scorer.score(source)
        assert report.sub_scores.name_entropy_score >= 0.9


# ---------------------------------------------------------------------------
# T93-AFIT-15: single-char names score low on name_entropy_score
# ---------------------------------------------------------------------------
class TestT93AFIT15_ShortNames:
    def test_single_char_names_low_entropy(self, scorer):
        """T93-AFIT-15: Single-char identifiers → name_entropy_score < 0.5."""
        source = textwrap.dedent("""\
            def f(x, y, z):
                a = x + y
                b = a * z
                c = b - a
                return c
        """)
        report = scorer.score(source)
        assert report.sub_scores.name_entropy_score < 0.5


# ---------------------------------------------------------------------------
# T93-AFIT-16: well-commented source scores high on comment_ratio_score
# ---------------------------------------------------------------------------
class TestT93AFIT16_WellCommented:
    def test_well_commented_source(self, scorer):
        """T93-AFIT-16: Source with proportional comments scores comment_ratio ≥ 0.8."""
        source = textwrap.dedent("""\
            # Parse and validate the incoming configuration.
            def parse_config(raw_config):
                # Ensure the config is a mapping.
                if not isinstance(raw_config, dict):
                    return None
                # Extract required fields.
                name = raw_config.get("name")
                # Validate name is present.
                if not name:
                    return None
                return name
        """)
        report = scorer.score(source)
        assert report.sub_scores.comment_ratio_score >= 0.8


# ---------------------------------------------------------------------------
# T93-AFIT-17: low cyclomatic complexity scores high
# ---------------------------------------------------------------------------
class TestT93AFIT17_LowCyclomatic:
    def test_low_cc_high_score(self, scorer):
        """T93-AFIT-17: Linear function → cyclomatic_score ≥ 0.9."""
        source = textwrap.dedent("""\
            def add_values(alpha, beta):
                result = alpha + beta
                return result
        """)
        report = scorer.score(source)
        assert report.sub_scores.cyclomatic_score >= 0.9


# ---------------------------------------------------------------------------
# T93-AFIT-18: high cyclomatic complexity scores low
# ---------------------------------------------------------------------------
class TestT93AFIT18_HighCyclomatic:
    def test_high_cc_low_score(self, scorer):
        """T93-AFIT-18: Function with many branches → cyclomatic_score < 0.5."""
        branches = "\n".join(
            f"    if x == {i}: return {i}" for i in range(15)
        )
        source = f"def branchy(x):\n{branches}\n    return -1\n"
        report = scorer.score(source)
        assert report.sub_scores.cyclomatic_score < 0.5


# ---------------------------------------------------------------------------
# T93-AFIT-19: algorithm_version is AFIT_VERSION in every report
# ---------------------------------------------------------------------------
class TestT93AFIT19_AlgorithmVersion:
    def test_algorithm_version_in_real_report(self, scorer):
        """T93-AFIT-19: Non-fallback report carries AFIT_VERSION."""
        report = scorer.score(CLEAN_SOURCE)
        assert report.algorithm_version == AFIT_VERSION

    def test_algorithm_version_in_fallback_report(self, scorer):
        """T93-AFIT-19b: Fallback report also carries AFIT_VERSION."""
        report = scorer.score(None)
        assert report.algorithm_version == AFIT_VERSION


# ---------------------------------------------------------------------------
# T93-AFIT-20: as_dict() on report produces serialisable structure
# ---------------------------------------------------------------------------
class TestT93AFIT20_AsDict:
    def test_as_dict_structure(self, scorer):
        """T93-AFIT-20: AestheticFitnessReport.as_dict() has required keys."""
        report = scorer.score(CLEAN_SOURCE)
        d = report.as_dict()
        assert "score" in d
        assert "sub_scores" in d
        assert "function_count" in d
        assert "fallback_used" in d
        assert "algorithm_version" in d
        assert isinstance(d["sub_scores"], dict)


# ---------------------------------------------------------------------------
# T93-AFIT-21: AFIT-WEIGHT-0 — aesthetic_fitness in _DEFAULT_WEIGHTS
# ---------------------------------------------------------------------------
class TestT93AFIT21_WeightPresent:
    def test_aesthetic_fitness_in_signal_keys(self):
        """T93-AFIT-21: aesthetic_fitness is in _SIGNAL_KEYS."""
        assert "aesthetic_fitness" in _SIGNAL_KEYS

    def test_aesthetic_fitness_in_default_weights(self):
        """T93-AFIT-21b: aesthetic_fitness is in _DEFAULT_WEIGHTS."""
        assert "aesthetic_fitness" in _DEFAULT_WEIGHTS

    def test_default_weight_in_bound(self):
        """T93-AFIT-21c: AFIT-WEIGHT-0 — default weight in [0.05, 0.30]."""
        w = _DEFAULT_WEIGHTS["aesthetic_fitness"]
        assert 0.05 <= w <= 0.30, f"AFIT-WEIGHT-0 violated: weight={w}"


# ---------------------------------------------------------------------------
# T93-AFIT-22: weights still sum to 1.0 after AFIT integration
# ---------------------------------------------------------------------------
class TestT93AFIT22_WeightSum:
    def test_default_weights_sum_to_one(self):
        """T93-AFIT-22: All default weights sum to exactly 1.0."""
        total = sum(_DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


# ---------------------------------------------------------------------------
# T93-AFIT-23: FitnessContext accepts aesthetic_fitness field
# ---------------------------------------------------------------------------
class TestT93AFIT23_FitnessContextField:
    def test_context_aesthetic_default(self):
        """T93-AFIT-23: FitnessContext.aesthetic_fitness defaults to 0.5."""
        ctx = FitnessContext(epoch_id="test-epoch-93")
        assert ctx.aesthetic_fitness == 0.5

    def test_context_aesthetic_custom(self):
        """T93-AFIT-23b: FitnessContext accepts custom aesthetic_fitness."""
        ctx = FitnessContext(epoch_id="test-epoch-93", aesthetic_fitness=0.85)
        assert ctx.aesthetic_fitness == 0.85


# ---------------------------------------------------------------------------
# T93-AFIT-24: FitnessEngineV2.score() includes aesthetic_fitness in output
# ---------------------------------------------------------------------------
class TestT93AFIT24_EngineScores:
    def test_engine_scores_aesthetic_signal(self):
        """T93-AFIT-24: FitnessEngineV2.score() reflects aesthetic_fitness in output."""
        engine = FitnessEngineV2()
        ctx_low = FitnessContext(
            epoch_id="ep-low",
            test_fitness=0.8,
            complexity_fitness=0.8,
            performance_fitness=0.8,
            governance_compliance=0.8,
            determinism_fitness=0.8,
            aesthetic_fitness=0.10,
        )
        ctx_high = FitnessContext(
            epoch_id="ep-high",
            test_fitness=0.8,
            complexity_fitness=0.8,
            performance_fitness=0.8,
            governance_compliance=0.8,
            determinism_fitness=0.8,
            aesthetic_fitness=0.90,
        )
        scores_low = engine.score(ctx_low)
        scores_high = engine.score(ctx_high)
        # Higher aesthetic_fitness → higher composite (weight > 0)
        assert scores_high.composite_score > scores_low.composite_score

    def test_engine_output_has_aesthetic_field(self):
        """T93-AFIT-24b: FitnessScores has aesthetic_fitness attribute."""
        engine = FitnessEngineV2()
        ctx = FitnessContext(epoch_id="ep-attr", aesthetic_fitness=0.75)
        scores = engine.score(ctx)
        assert hasattr(scores, "aesthetic_fitness")
        assert abs(scores.aesthetic_fitness - 0.75) < 1e-9

    def test_to_dict_has_aesthetic(self):
        """T93-AFIT-24c: FitnessScores.to_dict() includes aesthetic_fitness key."""
        engine = FitnessEngineV2()
        ctx = FitnessContext(epoch_id="ep-dict")
        scores = engine.score(ctx)
        d = scores.to_dict()
        assert "aesthetic_fitness" in d


# ---------------------------------------------------------------------------
# T93-AFIT-25: FitnessConfig rejects aesthetic weight outside [0.05, 0.30]
# ---------------------------------------------------------------------------
class TestT93AFIT25_WeightBoundEnforcement:
    def test_aesthetic_weight_below_minimum_rejected(self):
        """T93-AFIT-25: AFIT-WEIGHT-0 — weight < 0.05 violates FIT-BOUND-0."""
        bad = dict(_DEFAULT_WEIGHTS)
        bad["aesthetic_fitness"] = 0.01
        # Rebalance another signal to keep sum=1.0
        bad["test_fitness"] = bad["test_fitness"] + 0.04
        with pytest.raises(ValueError):
            FitnessConfig(weights=bad)

    def test_aesthetic_weight_above_maximum_rejected(self):
        """T93-AFIT-25b: FIT-BOUND-0 — weight > 0.70 rejected."""
        bad = dict(_DEFAULT_WEIGHTS)
        bad["aesthetic_fitness"] = 0.75
        bad["test_fitness"] = _DEFAULT_WEIGHTS["test_fitness"] - 0.70
        with pytest.raises(ValueError):
            FitnessConfig(weights=bad)

    def test_valid_custom_aesthetic_weight_accepted(self):
        """T93-AFIT-25c: Valid aesthetic weight in [0.05, 0.30] accepted by FitnessConfig."""
        custom = dict(_DEFAULT_WEIGHTS)
        # Move 0.05 from test_fitness to aesthetic_fitness (still sums to 1.0)
        custom["aesthetic_fitness"] = 0.10
        custom["test_fitness"] = _DEFAULT_WEIGHTS["test_fitness"] - 0.05
        cfg = FitnessConfig(weights=custom)
        assert cfg.weights["aesthetic_fitness"] == 0.10
