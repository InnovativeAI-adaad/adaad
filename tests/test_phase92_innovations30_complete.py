# SPDX-License-Identifier: Apache-2.0
"""Phase 92 — Innovations30 Completeness & Enhancement Suite.

AUTONOMOUS_CRITICAL: True

Covers:
    INNOV-COMPLETE-0  boot_completeness_check() raises on missing module
    INNOV-COMPLETE-0  InnovationsPipeline._init() completeness gate
    MARKET-HALT-0     halt_if_unconstrained() blocks when no signals active
    SELF-AWARE-0      surface_score, summary, register_protected_module,
                      SHA-256 verdict_digest
    TGOV-CHAIN-0      temporal governance SHA-256 chain digest + audit_trail
    TGOV-FAIL-0       unknown rule → fail-closed "blocking"
    BLAST-SLA-0       reversal_timeline() constitutional SLA commitments
    #24 semver        verdict_digest, verdict_history, breaking_change_analysis
    REGISTERED_INNOVATIONS  canonical 30-entry registry completeness
    verify_all_importable() non-raising diagnostic path

Merge gate: all tests must pass before merging to main.
DET-01: All computations deterministic for equal inputs.
"""
from __future__ import annotations
import json, time
from pathlib import Path
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_DIFF_PATCH = """\
--- a/runtime/foo.py
+++ b/runtime/foo.py
-def old_fn():
-    pass
+def old_fn():
+    return 42
"""

BREAKING_DIFF = """\
--- a/runtime/bar.py
+++ b/runtime/bar.py
-def public_api(x: int) -> str:
-    return str(x)
-__all__ = ["public_api"]
+def public_api(x: int, y: int = 0) -> str:
+    return str(x + y)
+__all__ = ["public_api"]
"""

OBSERVABILITY_REMOVAL_DIFF = """\
--- a/runtime/metrics.py
+++ b/runtime/metrics.py
-metrics.log("system_health", value=health)
+# metrics removed for performance
"""


# ══════════════════════════════════════════════════════════════════════════════
# INNOV-COMPLETE-0 — __init__.py boot completeness gate
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestInnovationsBootCompletenessGate:
    """[INNOV-COMPLETE-0] boot_completeness_check() and registry invariants."""

    def test_registered_innovations_has_exactly_30_entries(self):
        from runtime.innovations30 import REGISTERED_INNOVATIONS, INNOVATION_COUNT
        assert len(REGISTERED_INNOVATIONS) == INNOVATION_COUNT == 30

    def test_registered_innovations_keys_are_1_to_30(self):
        from runtime.innovations30 import REGISTERED_INNOVATIONS
        assert set(REGISTERED_INNOVATIONS.keys()) == set(range(1, 31))

    def test_each_registry_entry_has_module_and_class(self):
        from runtime.innovations30 import REGISTERED_INNOVATIONS
        for num, (mod_path, cls_name) in REGISTERED_INNOVATIONS.items():
            assert isinstance(mod_path, str) and mod_path.startswith("runtime.innovations30."), (
                f"Innovation #{num}: unexpected module path '{mod_path}'"
            )
            assert isinstance(cls_name, str) and cls_name[0].isupper(), (
                f"Innovation #{num}: cls_name '{cls_name}' should be a class (UpperCase)"
            )

    def test_boot_completeness_check_passes_for_full_set(self):
        from runtime.innovations30 import boot_completeness_check
        report = boot_completeness_check()
        assert report["status"] == "ok"
        assert report["loaded"] == 30
        assert report["missing"] == []

    def test_verify_all_importable_returns_true_for_full_set(self):
        from runtime.innovations30 import verify_all_importable
        ok, report = verify_all_importable()
        assert ok is True
        assert report["status"] == "ok"
        assert report["loaded"] == 30

    def test_get_innovation_class_returns_correct_type(self):
        from runtime.innovations30 import get_innovation_class
        # Spot-check a few across the range
        for num, expected_name in [
            (1,  "InvariantDiscoveryEngine"),
            (22, "MarketConditionedFitness"),
            (28, "SelfAwarenessInvariant"),
            (30, "MirrorTestEngine"),
        ]:
            cls = get_innovation_class(num)
            assert cls.__name__ == expected_name, (
                f"Innovation #{num}: expected {expected_name}, got {cls.__name__}"
            )

    def test_get_innovation_class_raises_on_unknown_number(self):
        from runtime.innovations30 import get_innovation_class
        with pytest.raises(KeyError, match="31"):
            get_innovation_class(31)

    def test_innovation_version_is_bumped(self):
        from runtime.innovations30 import INNOVATION_VERSION
        major, minor, patch = (int(x) for x in INNOVATION_VERSION.split("."))
        # v1.1.0 or higher required — v1.0.0 predates boot gate
        assert (major, minor) >= (1, 1), (
            f"INNOVATION_VERSION {INNOVATION_VERSION} predates boot gate — "
            f"expected >= 1.1.0"
        )


# ══════════════════════════════════════════════════════════════════════════════
# INNOV-COMPLETE-0 — InnovationsPipeline boot gate
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestInnovationsPipelineBootGate:
    """[INNOV-COMPLETE-0] InnovationsPipeline._init() raises on missing component."""

    def test_pipeline_initialises_all_29_named_components(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        pipeline = InnovationsPipeline(data_dir=tmp_path)
        pipeline._init()
        names = pipeline.component_names()
        for name in names:
            assert name in pipeline._components, (
                f"[INNOV-COMPLETE-0] Component '{name}' absent from _components after _init()"
            )

    def test_pipeline_component_names_stable(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        names = p.component_names()
        # 29 named keys (mirror_test is the 30th innovation but pipeline
        # tracks 29 named components; integration wires all 30 innovations)
        assert len(names) >= 29

    def test_pipeline_idempotent_double_init(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        p._init()
        first_id = id(p._components["self_aware"])
        p._init()
        second_id = id(p._components["self_aware"])
        # _init is idempotent; components not recreated on second call
        assert first_id == second_id

    def test_pipeline_evaluate_returns_result(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        r = p.evaluate_mutation(
            mutation_id="m-phase92-001",
            agent_id="agent-a",
            intent="optimize performance",
            diff_text=SAMPLE_DIFF_PATCH,
            changed_files=["runtime/foo.py"],
            epoch_id="ep-phase92",
            epoch_seq=1,
        )
        assert r.mutation_id == "m-phase92-001"
        assert isinstance(r.overall_innovations_score, float)
        assert 0.0 <= r.overall_innovations_score <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# MARKET-HALT-0 — Innovation #22: Market-Conditioned Fitness
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestMarketFitnessHaltInvariant:
    """[MARKET-HALT-0] MarketConditionedFitness fail-closed when no active signals."""

    def test_halt_when_no_signals(self, tmp_path):
        from runtime.innovations30.market_fitness import MarketConditionedFitness
        m = MarketConditionedFitness(signals_path=tmp_path / "signals.jsonl")
        should_halt, reason = m.halt_if_unconstrained()
        assert should_halt is True, "[MARKET-HALT-0] Expected halt with zero signals"
        assert "MARKET-HALT-0" in reason
        assert "Insufficient" in reason

    def test_no_halt_when_active_signal_present(self, tmp_path):
        from runtime.innovations30.market_fitness import MarketConditionedFitness, ExternalSignal
        m = MarketConditionedFitness(signals_path=tmp_path / "signals.jsonl")
        m.register_signal(ExternalSignal(
            signal_id="s-001",
            source="benchmark_rank",
            value=0.80,
            direction=1.0,
            timestamp=time.time(),
            weight=0.10,
        ))
        should_halt, reason = m.halt_if_unconstrained()
        assert should_halt is False
        assert reason == "ok"

    def test_halt_when_all_signals_stale(self, tmp_path):
        from runtime.innovations30.market_fitness import MarketConditionedFitness, ExternalSignal
        m = MarketConditionedFitness(signals_path=tmp_path / "signals.jsonl")
        # Signal older than 7 days = stale
        stale_ts = time.time() - (86400 * 8)
        m.register_signal(ExternalSignal(
            signal_id="s-stale",
            source="github_stars",
            value=0.70,
            direction=0.0,
            timestamp=stale_ts,
            weight=0.10,
        ))
        should_halt, reason = m.halt_if_unconstrained()
        assert should_halt is True, "[MARKET-HALT-0] Stale signals must trigger halt"

    def test_signal_summary_structure(self, tmp_path):
        from runtime.innovations30.market_fitness import MarketConditionedFitness, ExternalSignal
        m = MarketConditionedFitness(signals_path=tmp_path / "signals.jsonl")
        summary = m.signal_summary()
        assert "total_registered" in summary
        assert "active_7d" in summary
        assert "halt_invariant_triggered" in summary
        assert "min_signals_required" in summary
        assert summary["halt_invariant_triggered"] is True   # no signals yet

    def test_direction_trend_stable_no_signals(self, tmp_path):
        from runtime.innovations30.market_fitness import MarketConditionedFitness
        m = MarketConditionedFitness(signals_path=tmp_path / "signals.jsonl")
        assert m.direction_trend() == "stable"

    def test_direction_trend_improving_with_positive_signals(self, tmp_path):
        from runtime.innovations30.market_fitness import MarketConditionedFitness, ExternalSignal
        m = MarketConditionedFitness(signals_path=tmp_path / "signals.jsonl")
        for i in range(3):
            m.register_signal(ExternalSignal(
                signal_id=f"s-{i}",
                source="benchmark_rank",
                value=0.85,
                direction=1.0,
                timestamp=time.time(),
                weight=0.20,
            ))
        assert m.direction_trend() == "improving"

    def test_market_health_score_after_signals(self, tmp_path):
        from runtime.innovations30.market_fitness import MarketConditionedFitness, ExternalSignal
        m = MarketConditionedFitness(signals_path=tmp_path / "signals.jsonl")
        m.register_signal(ExternalSignal(
            signal_id="s-h",
            source="api_latency",
            value=0.60,
            direction=0.0,
            timestamp=time.time(),
            weight=0.10,
        ))
        score = m.market_health_score()
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_min_signals_constant_is_positive(self):
        from runtime.innovations30.market_fitness import MarketConditionedFitness
        assert MarketConditionedFitness.MIN_SIGNALS >= 1, (
            "[MARKET-HALT-0] MIN_SIGNALS=0 would disable the halt invariant entirely"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SELF-AWARE-0 — Innovation #28: Self-Awareness Invariant
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestSelfAwarenessInvariantEnhanced:
    """[SELF-AWARE-0] SHA-256 digest, surface_score, summary, register_protected_module."""

    def test_verdict_digest_is_sha256_prefixed(self):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        v = inv.evaluate("m-001", SAMPLE_DIFF_PATCH, ["runtime/foo.py"])
        assert v.verdict_digest.startswith("sha256:"), (
            "SelfAwarenessVerdict.verdict_digest must be SHA-256 prefixed"
        )
        assert len(v.verdict_digest) > 15

    def test_verdict_digest_deterministic(self):
        """DET-01: same inputs → same digest."""
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        v1 = inv.evaluate("m-det", SAMPLE_DIFF_PATCH, ["runtime/foo.py"])
        v2 = inv.evaluate("m-det", SAMPLE_DIFF_PATCH, ["runtime/foo.py"])
        # Digests are stable across equal inputs
        assert v1.verdict_digest == v2.verdict_digest

    def test_surface_score_1_when_no_protected_touched(self):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        score = inv.protected_surface_score(["runtime/unrelated.py"])
        assert score == pytest.approx(1.0, abs=0.01), (
            "surface_score should be 1.0 when no protected modules are touched"
        )

    def test_surface_score_below_1_when_protected_touched(self):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        score = inv.protected_surface_score(["runtime/metrics.py"])
        assert score < 1.0, (
            "surface_score must drop below 1.0 when a protected module is touched"
        )

    def test_register_protected_module_expands_surface(self):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        before = inv.protected_surface_score(["runtime/my_new_monitor.py"])
        inv.register_protected_module("runtime/my_new_monitor.py")
        after = inv.protected_surface_score(["runtime/my_new_monitor.py"])
        assert after < before, (
            "register_protected_module must expand the protected surface"
        )

    def test_summary_structure(self):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        inv.evaluate("m-001", SAMPLE_DIFF_PATCH, ["runtime/foo.py"])
        s = inv.summary()
        assert s["rule_id"] == "SELF-AWARE-0"
        assert s["total_evaluations"] == 1
        assert isinstance(s["protected_module_count"], int)
        assert s["protected_module_count"] >= 6  # at least the 6 defaults

    def test_violation_increments_violation_count(self):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        # Diff removing a metrics call from a protected file
        inv.evaluate("m-viol", OBSERVABILITY_REMOVAL_DIFF, ["runtime/metrics.py"])
        s = inv.summary()
        assert s["total_violations"] >= 1

    def test_audit_path_persists_verdicts(self, tmp_path):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        audit = tmp_path / "sa_audit.jsonl"
        inv = SelfAwarenessInvariant(audit_path=audit)
        inv.evaluate("m-persist-001", SAMPLE_DIFF_PATCH, ["runtime/foo.py"])
        inv.evaluate("m-persist-002", SAMPLE_DIFF_PATCH, ["runtime/metrics.py"])
        lines = audit.read_text().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["mutation_id"] == "m-persist-001"
        assert "verdict_digest" in first

    def test_rule_id_constant(self):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        v = inv.evaluate("m-id", "+x=1", [])
        assert v.rule_id == "SELF-AWARE-0"

    def test_passed_true_for_clean_diff(self):
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        inv = SelfAwarenessInvariant()
        v = inv.evaluate("m-clean", "+x = 42\n", ["runtime/unrelated.py"])
        assert v.passed is True
        assert v.violations == []


# ══════════════════════════════════════════════════════════════════════════════
# TGOV-CHAIN-0 / TGOV-FAIL-0 — Innovation #18: Temporal Governance
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestTemporalGovernanceChain:
    """[TGOV-CHAIN-0] SHA-256 chain digest on every log entry.
    [TGOV-FAIL-0] Unknown rules fail-closed to 'blocking'."""

    def test_log_adjustment_writes_digest(self, tmp_path):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
        tg.log_adjustment("ep-001", 0.75)
        lines = (tmp_path / "tgov.jsonl").read_text().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert "digest" in entry
        assert entry["digest"].startswith("sha256:")

    def test_chain_prev_digest_links_entries(self, tmp_path):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
        tg.log_adjustment("ep-001", 0.75)
        tg.log_adjustment("ep-002", 0.80)
        lines = (tmp_path / "tgov.jsonl").read_text().splitlines()
        e1 = json.loads(lines[0])
        e2 = json.loads(lines[1])
        assert e2["prev_digest"] == e1["digest"], (
            "[TGOV-CHAIN-0] Second entry's prev_digest must equal first entry's digest"
        )

    def test_first_entry_prev_digest_is_genesis(self, tmp_path):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
        tg.log_adjustment("ep-001", 0.75)
        entry = json.loads((tmp_path / "tgov.jsonl").read_text())
        assert entry["prev_digest"] == "genesis"

    def test_audit_trail_returns_entries(self, tmp_path):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
        for i in range(5):
            tg.log_adjustment(f"ep-{i:03d}", 0.70 + i * 0.02)
        trail = tg.audit_trail(limit=3)
        assert len(trail) == 3
        assert trail[-1]["epoch_id"] == "ep-004"

    def test_audit_trail_empty_when_no_log(self, tmp_path):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine(state_path=tmp_path / "nonexistent.jsonl")
        assert tg.audit_trail() == []

    def test_unknown_rule_fails_closed(self):
        """[TGOV-FAIL-0] Unknown rule must return 'blocking', not 'advisory'."""
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine()
        result = tg.effective_severity("this_rule_does_not_exist", 0.90)
        assert result == "blocking", (
            "[TGOV-FAIL-0] Unknown rules must fail-closed to 'blocking'"
        )

    def test_export_window_config_structure(self):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine()
        cfg = tg.export_window_config()
        assert cfg["innovation"] == 18
        assert "windows" in cfg
        assert cfg["window_count"] == len(tg.windows)

    def test_health_trend_stable_no_log(self, tmp_path):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
        assert tg.health_trend() == "stable"

    def test_health_trend_improving(self, tmp_path):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
        for score in [0.60, 0.65, 0.70, 0.75, 0.82]:
            tg.log_adjustment("ep", score)
        assert tg.health_trend() == "improving"

    def test_health_trend_degrading(self, tmp_path):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
        for score in [0.85, 0.80, 0.72, 0.65, 0.58]:
            tg.log_adjustment("ep", score)
        assert tg.health_trend() == "degrading"

    def test_adjusted_ruleset_high_health(self):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine()
        ruleset = tg.get_adjusted_ruleset(health_score=0.90)
        # lineage_continuity: high_health_severity = "warning" per DEFAULT_WINDOWS
        assert ruleset["lineage_continuity"] == "warning"

    def test_adjusted_ruleset_low_health_blocks_all(self):
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        tg = TemporalGovernanceEngine()
        ruleset = tg.get_adjusted_ruleset(health_score=0.40)
        for rule, severity in ruleset.items():
            assert severity == "blocking", (
                f"Rule '{rule}' must be blocking at critical health 0.40, got '{severity}'"
            )


# ══════════════════════════════════════════════════════════════════════════════
# #24 Semantic Version Enforcer — audit trail + breaking_change_analysis
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestSemanticVersionEnforcerEnhanced:
    """Innovation #24 — verdict persistence, digest chain, breaking_change_analysis."""

    def test_verdict_has_sha256_digest(self):
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        sve = SemanticVersionEnforcer()
        v = sve.verify("m-001", "patch", SAMPLE_DIFF_PATCH)
        assert v.verdict_digest.startswith("sha256:")

    def test_verdict_digest_deterministic(self):
        """DET-01: identical inputs → identical digest."""
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        sve = SemanticVersionEnforcer()
        v1 = sve.verify("m-det", "patch", SAMPLE_DIFF_PATCH)
        v2 = sve.verify("m-det", "patch", SAMPLE_DIFF_PATCH)
        assert v1.verdict_digest == v2.verdict_digest

    def test_record_and_retrieve_verdict_history(self, tmp_path):
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        audit = tmp_path / "semver_audit.jsonl"
        sve = SemanticVersionEnforcer(audit_path=audit)
        sve.verify("m-h001", "patch", SAMPLE_DIFF_PATCH)
        sve.verify("m-h002", "minor", SAMPLE_DIFF_PATCH)
        history = sve.verdict_history(limit=10)
        assert len(history) == 2
        assert history[0]["mutation_id"] == "m-h001"
        assert history[1]["mutation_id"] == "m-h002"

    def test_verdict_history_empty_no_audit_path(self):
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        sve = SemanticVersionEnforcer()
        assert sve.verdict_history() == []

    def test_breaking_change_analysis_detects_major(self):
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        sve = SemanticVersionEnforcer()
        analysis = sve.breaking_change_analysis(BREAKING_DIFF)
        assert analysis["detected_impact"] == "major"
        assert "detected_impact" in analysis
        assert "breaking_signals" in analysis
        assert "feature_signals" in analysis

    def test_breaking_change_analysis_patch_for_trivial_diff(self):
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        sve = SemanticVersionEnforcer()
        trivial_diff = "+    # comment only\n-    # old comment\n"
        analysis = sve.breaking_change_analysis(trivial_diff)
        assert analysis["detected_impact"] == "patch"

    def test_declared_patch_but_major_detected_is_violation(self):
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        sve = SemanticVersionEnforcer()
        v = sve.verify("m-lied", "patch", BREAKING_DIFF)
        assert v.contract_honored is False
        assert len(v.violations) >= 1
        assert "major" in v.violations[0].lower() or "patch" in v.violations[0].lower()

    def test_declared_major_always_honored(self):
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        sve = SemanticVersionEnforcer()
        v = sve.verify("m-over", "major", SAMPLE_DIFF_PATCH)
        assert v.contract_honored is True, (
            "Declaring 'major' for a patch diff is overly conservative — "
            "but never a violation (higher > lower is acceptable)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BLAST-SLA-0 — Innovation #27: Blast Radius Model
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestBlastRadiusModelEnhanced:
    """[BLAST-SLA-0] reversal_timeline SLA commitments, dependency_graph_summary."""

    def test_reversal_sla_constants_cover_all_tiers(self):
        from runtime.innovations30.blast_radius_model import REVERSAL_SLA
        for tier in ["low", "medium", "high", "critical"]:
            assert tier in REVERSAL_SLA, f"REVERSAL_SLA missing tier '{tier}'"
            assert REVERSAL_SLA[tier] > 0

    def test_reversal_sla_ordering(self):
        from runtime.innovations30.blast_radius_model import REVERSAL_SLA
        # SLAs must be monotonically increasing: low < medium < high < critical
        assert REVERSAL_SLA["low"] < REVERSAL_SLA["medium"]
        assert REVERSAL_SLA["medium"] < REVERSAL_SLA["high"]
        assert REVERSAL_SLA["high"] < REVERSAL_SLA["critical"]

    def test_reversal_timeline_low_no_escalation(self, tmp_path):
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        m = BlastRadiusModeler(repo_root=tmp_path)
        plan = m.reversal_timeline("low")
        assert plan["risk_tier"] == "low"
        assert plan["escalation_required"] is False
        assert plan["governor_signoff_required"] is False
        assert "sla_hours" in plan
        assert plan["sla_hours"] == pytest.approx(1.0)

    def test_reversal_timeline_critical_requires_governor(self, tmp_path):
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        m = BlastRadiusModeler(repo_root=tmp_path)
        plan = m.reversal_timeline("critical")
        assert plan["escalation_required"] is True
        assert plan["governor_signoff_required"] is True
        assert "HUMAN-0" in " ".join(plan["rollback_steps"])

    def test_reversal_timeline_has_invariant_code(self, tmp_path):
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        m = BlastRadiusModeler(repo_root=tmp_path)
        for tier in ["low", "medium", "high", "critical"]:
            plan = m.reversal_timeline(tier)
            assert plan["invariant_code"] == "BLAST-SLA-0"

    def test_reversal_timeline_has_deadline_iso(self, tmp_path):
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        m = BlastRadiusModeler(repo_root=tmp_path)
        plan = m.reversal_timeline("medium")
        assert "sla_deadline_utc_estimate" in plan
        assert plan["sla_deadline_utc_estimate"].endswith("Z")

    def test_dependency_graph_summary_structure(self, tmp_path):
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        m = BlastRadiusModeler(repo_root=tmp_path)
        summary = m.dependency_graph_summary(["runtime/foo.py"])
        assert "changed_files" in summary
        assert "per_file" in summary
        assert "total_direct_importers" in summary
        assert "unique_importers" in summary
        assert "snapshot_timestamp" in summary

    def test_blast_report_digest_is_sha256(self, tmp_path):
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        m = BlastRadiusModeler(repo_root=tmp_path)
        report = m.model("m-blast-001", ["runtime/foo.py"])
        assert report.report_digest.startswith("sha256:")

    def test_blast_report_digest_deterministic(self, tmp_path):
        """DET-01: same inputs → same digest."""
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        m = BlastRadiusModeler(repo_root=tmp_path)
        r1 = m.model("m-det-blast", ["runtime/foo.py"])
        r2 = m.model("m-det-blast", ["runtime/foo.py"])
        assert r1.report_digest == r2.report_digest

    def test_blast_report_includes_sla_hours(self, tmp_path):
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        m = BlastRadiusModeler(repo_root=tmp_path)
        report = m.model("m-sla-001", ["runtime/foo.py"])
        assert hasattr(report, "reversal_sla_hours")
        assert report.reversal_sla_hours > 0


# ══════════════════════════════════════════════════════════════════════════════
# Cross-cutting: InnovationsPipeline integration for new capabilities
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestPipelineNewCapabilitiesIntegration:
    """Integration: new Phase 92 capabilities flow through InnovationsPipeline."""

    def test_pipeline_self_aware_passed_in_result(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        r = p.evaluate_mutation(
            mutation_id="m-int-001",
            agent_id="agent-b",
            intent="refactor logging",
            diff_text=SAMPLE_DIFF_PATCH,
            changed_files=["runtime/unrelated.py"],
        )
        assert isinstance(r.self_aware_passed, bool)

    def test_pipeline_blast_radius_tier_in_result(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        r = p.evaluate_mutation(
            mutation_id="m-int-002",
            agent_id="agent-b",
            intent="patch fix",
            diff_text=SAMPLE_DIFF_PATCH,
            changed_files=["runtime/foo.py"],
        )
        assert r.blast_radius_tier in {"low", "medium", "high", "critical"}

    def test_pipeline_semver_honored_in_result(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        r = p.evaluate_mutation(
            mutation_id="m-int-003",
            agent_id="agent-c",
            intent="minor feature",
            diff_text=SAMPLE_DIFF_PATCH,
            changed_files=["runtime/foo.py"],
            declared_semver="patch",
        )
        assert isinstance(r.semver_honored, bool)

    def test_pipeline_temporal_governance_ruleset_populated(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        r = p.evaluate_mutation(
            mutation_id="m-int-004",
            agent_id="agent-d",
            intent="governance tweak",
            diff_text=SAMPLE_DIFF_PATCH,
            changed_files=["runtime/governance/gate.py"],
            health_score=0.90,
        )
        assert isinstance(r.temporal_governance_ruleset, dict)
        assert len(r.temporal_governance_ruleset) >= 1

    def test_pipeline_market_adjusted_score_in_0_1(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        r = p.evaluate_mutation(
            mutation_id="m-int-005",
            agent_id="agent-e",
            intent="optimise cache",
            diff_text=SAMPLE_DIFF_PATCH,
            changed_files=["runtime/cache.py"],
        )
        assert 0.0 <= r.market_adjusted_score <= 1.0

    def test_pipeline_overall_score_in_0_1(self, tmp_path):
        from runtime.innovations30.integration import InnovationsPipeline
        p = InnovationsPipeline(data_dir=tmp_path)
        r = p.evaluate_mutation(
            mutation_id="m-int-006",
            agent_id="agent-f",
            intent="stability fix",
            diff_text=SAMPLE_DIFF_PATCH,
            changed_files=["runtime/stability.py"],
        )
        assert 0.0 <= r.overall_innovations_score <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Cross-validator: __init__ REGISTERED_INNOVATIONS vs filesystem
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.phase92
@pytest.mark.autonomous_critical
class TestRegistryFilesystemParity:
    """Cross-validator: every entry in REGISTERED_INNOVATIONS must map to
    a real .py file in runtime/innovations30/.  No phantom entries allowed.
    """

    def test_every_registered_module_file_exists(self):
        import importlib, sys
        from runtime.innovations30 import REGISTERED_INNOVATIONS
        import runtime.innovations30 as pkg
        pkg_dir = Path(pkg.__file__).parent

        for num, (mod_path, cls_name) in REGISTERED_INNOVATIONS.items():
            # Convert module path to file path
            rel = mod_path.replace("runtime.innovations30.", "")
            file = pkg_dir / f"{rel}.py"
            assert file.exists(), (
                f"Innovation #{num}: registry entry '{mod_path}' has no "
                f"corresponding file at {file}"
            )

    def test_every_registered_class_is_importable(self):
        import importlib
        from runtime.innovations30 import REGISTERED_INNOVATIONS
        for num, (mod_path, cls_name) in REGISTERED_INNOVATIONS.items():
            try:
                mod = importlib.import_module(mod_path)
            except ImportError as exc:
                pytest.fail(
                    f"Innovation #{num}: cannot import '{mod_path}': {exc}"
                )
            assert hasattr(mod, cls_name), (
                f"Innovation #{num}: module '{mod_path}' missing class '{cls_name}'"
            )

    def test_no_innovation_file_outside_registry(self):
        """Every *.py in innovations30/ (except __init__ and integration)
        should map to exactly one REGISTERED_INNOVATIONS entry."""
        import runtime.innovations30 as pkg
        from runtime.innovations30 import REGISTERED_INNOVATIONS
        pkg_dir = Path(pkg.__file__).parent

        SKIP = {"__init__", "integration"}
        registered_stems = {
            mod_path.split(".")[-1]
            for _, (mod_path, _) in REGISTERED_INNOVATIONS.items()
        }
        for py_file in sorted(pkg_dir.glob("*.py")):
            stem = py_file.stem
            if stem in SKIP:
                continue
            assert stem in registered_stems, (
                f"File '{py_file.name}' exists in innovations30/ but has no "
                f"entry in REGISTERED_INNOVATIONS. Add or remove the file."
            )
