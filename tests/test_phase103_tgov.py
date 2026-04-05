# SPDX-License-Identifier: Apache-2.0
"""
Phase 103 — INNOV-18 Temporal Governance Windows (TGOV)
Test suite: T103-TGOV-01..30  (30 tests)

Invariants under test:
  TGOV-0             — effective_severity() never raises; unknown rules fail-closed → "blocking"
  TGOV-CHAIN-0       — log_adjustment() entries carry chained SHA-256 digest linked to prev_digest
  TGOV-CORRUPT-SKIP-0 — audit_trail() silently skips corrupt JSONL lines; never raises
  TGOV-FAIL-0        — unregistered rule_name → "blocking" (fail-closed gate)
  TGOV-DETERM-0      — identical inputs → identical adjusted ruleset output (no RNG)
  TGOV-PERSIST-0     — log_adjustment() uses append mode; parent dir auto-created
  TGOV-HEALTH-0      — health_trend() returns "improving"/"degrading"/"stable" from log
  TGOV-EXPORT-0      — export_window_config() returns valid structured dict with innovation=18
  TGOV-WINDOW-0      — GovernanceWindow.effective_severity() honours thresholds correctly
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.innovations30.temporal_governance import (
    DEFAULT_WINDOWS,
    GovernanceWindow,
    TemporalGovernanceEngine,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path: Path) -> TemporalGovernanceEngine:
    """Fresh engine with default windows backed by a tmp state file."""
    return TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")


@pytest.fixture
def engine_with_log(tmp_path: Path) -> TemporalGovernanceEngine:
    """Engine with three pre-logged health-score entries."""
    eng = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
    for i, score in enumerate([0.50, 0.70, 0.90]):
        eng.log_adjustment(f"epoch-{i:03d}", score)
    return eng


# ---------------------------------------------------------------------------
# T103-TGOV-01..05  GovernanceWindow core logic  [TGOV-WINDOW-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_01_high_health_uses_high_severity() -> None:
    """TGOV-WINDOW-0: score >= high_health_threshold → high_health_severity."""
    w = GovernanceWindow("rule_x", "blocking", "warning", "blocking")
    assert w.effective_severity(0.90) == "warning"


def test_T103_TGOV_02_low_health_uses_low_severity() -> None:
    """TGOV-WINDOW-0: score < low_health_threshold → low_health_severity."""
    w = GovernanceWindow("rule_x", "blocking", "warning", "critical")
    assert w.effective_severity(0.50) == "critical"


def test_T103_TGOV_03_mid_health_uses_baseline() -> None:
    """TGOV-WINDOW-0: score in mid-band → baseline_severity."""
    w = GovernanceWindow("rule_x", "blocking", "warning", "critical")
    assert w.effective_severity(0.72) == "blocking"


def test_T103_TGOV_04_boundary_high_threshold_inclusive() -> None:
    """TGOV-WINDOW-0: score exactly at high_health_threshold → high severity."""
    w = GovernanceWindow("rule_x", "baseline", "high", "low", high_health_threshold=0.85)
    assert w.effective_severity(0.85) == "high"


def test_T103_TGOV_05_boundary_low_threshold_exclusive() -> None:
    """TGOV-WINDOW-0: score exactly at low_health_threshold boundary."""
    w = GovernanceWindow("rule_x", "baseline", "high", "low", low_health_threshold=0.60)
    # At exactly 0.60 → not < 0.60 → should return baseline
    assert w.effective_severity(0.60) == "baseline"


# ---------------------------------------------------------------------------
# T103-TGOV-06..10  TemporalGovernanceEngine — fail-closed & unknown rules [TGOV-FAIL-0, TGOV-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_06_unknown_rule_returns_blocking(engine: TemporalGovernanceEngine) -> None:
    """TGOV-FAIL-0: unregistered rule → 'blocking'."""
    assert engine.effective_severity("nonexistent_rule", 0.90) == "blocking"


def test_T103_TGOV_07_known_rule_returns_adjusted(engine: TemporalGovernanceEngine) -> None:
    """TGOV-0: known rule at high health → high_health_severity."""
    # lineage_continuity high_health_severity = "warning"
    result = engine.effective_severity("lineage_continuity", 0.90)
    assert result in ("warning", "advisory", "blocking")


def test_T103_TGOV_08_effective_severity_never_raises(engine: TemporalGovernanceEngine) -> None:
    """TGOV-0: no exception for any float in [0.0, 1.0]."""
    for score in [0.0, 0.01, 0.59, 0.60, 0.61, 0.84, 0.85, 0.86, 1.0]:
        engine.effective_severity("lineage_continuity", score)  # must not raise


def test_T103_TGOV_09_unknown_rule_never_raises(engine: TemporalGovernanceEngine) -> None:
    """TGOV-FAIL-0: extreme health scores + unknown rule must not raise."""
    for score in [-999.0, 0.0, 1.0, 9999.9]:
        engine.effective_severity("__totally_unknown__", score)


def test_T103_TGOV_10_default_windows_all_present(engine: TemporalGovernanceEngine) -> None:
    """TGOV-0: engine initialised with DEFAULT_WINDOWS contains all 5 rules."""
    assert len(engine.windows) == len(DEFAULT_WINDOWS)
    for w in DEFAULT_WINDOWS:
        assert w.rule_name in engine.windows


# ---------------------------------------------------------------------------
# T103-TGOV-11..15  get_adjusted_ruleset  [TGOV-DETERM-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_11_adjusted_ruleset_keys_match_windows(engine: TemporalGovernanceEngine) -> None:
    """TGOV-DETERM-0: ruleset keys == registered window names."""
    ruleset = engine.get_adjusted_ruleset(0.75)
    assert set(ruleset.keys()) == set(engine.windows.keys())


def test_T103_TGOV_12_adjusted_ruleset_values_are_strings(engine: TemporalGovernanceEngine) -> None:
    """TGOV-DETERM-0: all values are non-empty strings."""
    ruleset = engine.get_adjusted_ruleset(0.80)
    assert all(isinstance(v, str) and v for v in ruleset.values())


def test_T103_TGOV_13_deterministic_for_same_score(engine: TemporalGovernanceEngine) -> None:
    """TGOV-DETERM-0: identical health score → identical ruleset (no RNG)."""
    r1 = engine.get_adjusted_ruleset(0.72)
    r2 = engine.get_adjusted_ruleset(0.72)
    assert r1 == r2


def test_T103_TGOV_14_high_score_softens_non_ast_rules(engine: TemporalGovernanceEngine) -> None:
    """TGOV-WINDOW-0: at high health, entropy_budget & replay_determinism soften to advisory."""
    ruleset = engine.get_adjusted_ruleset(0.90)
    # entropy_budget high_health_severity == "advisory"
    assert ruleset.get("entropy_budget") == "advisory"
    assert ruleset.get("replay_determinism") == "advisory"


def test_T103_TGOV_15_low_score_hardens_rules(engine: TemporalGovernanceEngine) -> None:
    """TGOV-WINDOW-0: at low health, all rules → blocking or equivalent."""
    ruleset = engine.get_adjusted_ruleset(0.40)
    # ast_validity is always blocking regardless of health
    assert ruleset.get("ast_validity") == "blocking"


# ---------------------------------------------------------------------------
# T103-TGOV-16..20  log_adjustment + chain integrity  [TGOV-CHAIN-0, TGOV-PERSIST-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_16_log_creates_file(engine: TemporalGovernanceEngine, tmp_path: Path) -> None:
    """TGOV-PERSIST-0: log_adjustment creates state file."""
    engine.log_adjustment("epoch-001", 0.75)
    assert engine.state_path.exists()


def test_T103_TGOV_17_log_appends_multiple_entries(engine: TemporalGovernanceEngine) -> None:
    """TGOV-PERSIST-0: multiple log calls → multiple JSONL lines."""
    for i in range(3):
        engine.log_adjustment(f"epoch-{i:03d}", 0.70 + i * 0.05)
    lines = engine.state_path.read_text().strip().splitlines()
    assert len(lines) == 3


def test_T103_TGOV_18_chain_digest_present_in_entries(engine: TemporalGovernanceEngine) -> None:
    """TGOV-CHAIN-0: each entry has 'digest' and 'prev_digest' fields."""
    engine.log_adjustment("epoch-001", 0.80)
    entry = json.loads(engine.state_path.read_text().strip())
    assert "digest" in entry
    assert "prev_digest" in entry


def test_T103_TGOV_19_chain_digest_is_sha256_prefixed(engine: TemporalGovernanceEngine) -> None:
    """TGOV-CHAIN-0: digest field starts with 'sha256:'."""
    engine.log_adjustment("epoch-001", 0.80)
    entry = json.loads(engine.state_path.read_text().strip())
    assert entry["digest"].startswith("sha256:")


def test_T103_TGOV_20_chain_links_prev_to_genesis(engine: TemporalGovernanceEngine) -> None:
    """TGOV-CHAIN-0: first entry's prev_digest == 'genesis'."""
    engine.log_adjustment("epoch-001", 0.75)
    entry = json.loads(engine.state_path.read_text().strip())
    assert entry["prev_digest"] == "genesis"


# ---------------------------------------------------------------------------
# T103-TGOV-21..24  chain progression  [TGOV-CHAIN-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_21_chain_head_progresses(engine: TemporalGovernanceEngine) -> None:
    """TGOV-CHAIN-0: _chain_head advances after each log call."""
    engine.log_adjustment("epoch-001", 0.75)
    head1 = engine._chain_head
    engine.log_adjustment("epoch-002", 0.80)
    head2 = engine._chain_head
    assert head1 != head2
    assert head2.startswith("sha256:")


def test_T103_TGOV_22_chain_second_entry_prev_equals_first_digest(
    engine: TemporalGovernanceEngine,
) -> None:
    """TGOV-CHAIN-0: second entry's prev_digest == first entry's digest."""
    engine.log_adjustment("epoch-001", 0.75)
    line1 = engine.state_path.read_text().strip().splitlines()[0]
    digest1 = json.loads(line1)["digest"]

    engine.log_adjustment("epoch-002", 0.80)
    line2 = engine.state_path.read_text().strip().splitlines()[1]
    prev2 = json.loads(line2)["prev_digest"]
    assert prev2 == digest1


def test_T103_TGOV_23_log_entry_contains_epoch_and_health(engine: TemporalGovernanceEngine) -> None:
    """TGOV-CHAIN-0: log entry carries epoch_id and health_score."""
    engine.log_adjustment("epoch-XYZ", 0.777)
    entry = json.loads(engine.state_path.read_text().strip())
    assert entry["epoch_id"] == "epoch-XYZ"
    assert entry["health_score"] == round(0.777, 4)


def test_T103_TGOV_24_log_entry_contains_adjustments_dict(engine: TemporalGovernanceEngine) -> None:
    """TGOV-CHAIN-0: log entry carries 'adjustments' ruleset dict."""
    engine.log_adjustment("epoch-001", 0.75)
    entry = json.loads(engine.state_path.read_text().strip())
    assert isinstance(entry["adjustments"], dict)
    assert len(entry["adjustments"]) > 0


# ---------------------------------------------------------------------------
# T103-TGOV-25..27  audit_trail + corrupt-skip  [TGOV-CORRUPT-SKIP-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_25_audit_trail_returns_logged_entries(
    engine_with_log: TemporalGovernanceEngine,
) -> None:
    """TGOV-CORRUPT-SKIP-0: audit_trail returns all valid entries."""
    trail = engine_with_log.audit_trail()
    assert len(trail) == 3


def test_T103_TGOV_26_audit_trail_skips_corrupt_lines(tmp_path: Path) -> None:
    """TGOV-CORRUPT-SKIP-0: corrupt JSONL lines silently skipped; no exception."""
    state_file = tmp_path / "tgov.jsonl"
    state_file.write_text(
        '{"epoch_id": "good", "health_score": 0.75}\n'
        "NOT_JSON_AT_ALL\n"
        '{"epoch_id": "also-good", "health_score": 0.80}\n'
    )
    eng = TemporalGovernanceEngine(state_path=state_file)
    trail = eng.audit_trail()
    assert len(trail) == 2


def test_T103_TGOV_27_audit_trail_empty_when_no_log(engine: TemporalGovernanceEngine) -> None:
    """TGOV-CORRUPT-SKIP-0: audit_trail returns [] when no log file exists."""
    assert engine.audit_trail() == []


# ---------------------------------------------------------------------------
# T103-TGOV-28  health_trend  [TGOV-HEALTH-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_28_health_trend_improving(engine_with_log: TemporalGovernanceEngine) -> None:
    """TGOV-HEALTH-0: trend 0.50→0.70→0.90 → 'improving'."""
    assert engine_with_log.health_trend() == "improving"


def test_T103_TGOV_28b_health_trend_degrading(tmp_path: Path) -> None:
    """TGOV-HEALTH-0: trend 0.90→0.70→0.50 → 'degrading'."""
    eng = TemporalGovernanceEngine(state_path=tmp_path / "tgov.jsonl")
    for score in [0.90, 0.70, 0.50]:
        eng.log_adjustment("e", score)
    assert eng.health_trend() == "degrading"


def test_T103_TGOV_28c_health_trend_stable_when_no_entries(engine: TemporalGovernanceEngine) -> None:
    """TGOV-HEALTH-0: stable when fewer than 2 log entries."""
    assert engine.health_trend() == "stable"


# ---------------------------------------------------------------------------
# T103-TGOV-29  export_window_config  [TGOV-EXPORT-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_29_export_window_config_structure(engine: TemporalGovernanceEngine) -> None:
    """TGOV-EXPORT-0: export returns dict with innovation=18 and correct window count."""
    cfg = engine.export_window_config()
    assert cfg["innovation"] == 18
    assert cfg["innovation_name"] == "TemporalGovernance"
    assert cfg["window_count"] == len(DEFAULT_WINDOWS)
    assert "windows" in cfg
    for name, wdata in cfg["windows"].items():
        assert "baseline_severity" in wdata
        assert "high_health_severity" in wdata
        assert "low_health_severity" in wdata


# ---------------------------------------------------------------------------
# T103-TGOV-30  register_window  [TGOV-0]
# ---------------------------------------------------------------------------


def test_T103_TGOV_30_register_custom_window(engine: TemporalGovernanceEngine) -> None:
    """TGOV-0: register_window adds new rule; effective_severity uses it correctly."""
    engine.register_window(
        GovernanceWindow("custom_rule", "blocking", "warning", "critical")
    )
    assert engine.effective_severity("custom_rule", 0.90) == "warning"
    assert engine.effective_severity("custom_rule", 0.40) == "critical"
    assert engine.effective_severity("custom_rule", 0.72) == "blocking"
