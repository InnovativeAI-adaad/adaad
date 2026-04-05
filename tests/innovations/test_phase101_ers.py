# SPDX-License-Identifier: Apache-2.0
"""T101-ERS-01..30 — Phase 101 INNOV-16 Emergent Role Specialization acceptance tests.

Invariants under test:
  ERS-0         discover_roles() is the sole role-assignment authority
  ERS-WINDOW-0  Roles not discovered before SPECIALIZATION_WINDOW (50) epochs
  ERS-THRESHOLD-0 Roles not discovered below SPECIALIZATION_THRESHOLD (0.65) spec score
  ERS-DETERM-0  Classification is deterministic; no entropy
  ERS-PERSIST-0 _save() uses Path.open("w") with sort_keys=True; _load() fail-open
"""
from __future__ import annotations
import json, dataclasses
from unittest.mock import patch, mock_open
import pytest

from runtime.innovations30.emergent_roles import (
    EmergentRoleSpecializer, EmergentRole, AgentBehaviorProfile,
    ROLE_ARCHETYPES, SPECIALIZATION_WINDOW, SPECIALIZATION_THRESHOLD,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fill_agent(spec: EmergentRoleSpecializer, agent_id: str,
                strategy: str = "structural_refactor",
                target: str = "runtime_module",
                risk: float = 0.2, n: int = SPECIALIZATION_WINDOW) -> None:
    for _ in range(n):
        spec.record_behavior(agent_id, target, strategy, risk, 0.05)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def spec(tmp_path):
    return EmergentRoleSpecializer(tmp_path / "roles.json")

@pytest.fixture()
def qualified_spec(tmp_path):
    s = EmergentRoleSpecializer(tmp_path / "roles.json")
    _fill_agent(s, "agent-A")
    return s

# ─────────────────────────────────────────────────────────────────────────────
# ERS-0 — Sole assignment authority (T101-ERS-01..05)
# ─────────────────────────────────────────────────────────────────────────────

def test_ers_01_discover_roles_returns_emergent_role(qualified_spec):
    """ERS-0: discover_roles() returns EmergentRole for qualified agent."""
    roles = qualified_spec.discover_roles()
    assert "agent-A" in roles
    assert isinstance(roles["agent-A"], EmergentRole)

def test_ers_02_get_role_none_before_discovery(spec):
    """ERS-0: get_role() returns None before discover_roles() is called."""
    _fill_agent(spec, "agent-A")
    assert spec.get_role("agent-A") is None

def test_ers_03_get_role_populated_after_discovery(qualified_spec):
    """ERS-0: get_role() returns role after discover_roles()."""
    qualified_spec.discover_roles()
    assert qualified_spec.get_role("agent-A") is not None

def test_ers_04_discovered_role_has_correct_agent_id(qualified_spec):
    """ERS-0: EmergentRole.agent_id matches the agent that was observed."""
    roles = qualified_spec.discover_roles()
    assert roles["agent-A"].agent_id == "agent-A"

def test_ers_05_unspecialized_agents_listed(spec):
    """ERS-0: agents not yet meeting criteria appear in unspecialized_agents()."""
    spec.record_behavior("agent-Z","tgt","strategy",0.5,0.0)
    assert "agent-Z" in spec.unspecialized_agents()

# ─────────────────────────────────────────────────────────────────────────────
# ERS-WINDOW-0 — Minimum epoch gate (T101-ERS-06..10)
# ─────────────────────────────────────────────────────────────────────────────

def test_ers_06_window_blocks_under_threshold(spec):
    """ERS-WINDOW-0: agent with < SPECIALIZATION_WINDOW epochs not discovered."""
    _fill_agent(spec, "agent-B", n=SPECIALIZATION_WINDOW - 1)
    roles = spec.discover_roles()
    assert "agent-B" not in roles

def test_ers_07_window_passes_at_exactly_threshold(spec):
    """ERS-WINDOW-0: agent with exactly SPECIALIZATION_WINDOW epochs qualifies."""
    _fill_agent(spec, "agent-C", n=SPECIALIZATION_WINDOW)
    roles = spec.discover_roles()
    assert "agent-C" in roles

def test_ers_08_epochs_active_increments_correctly(spec):
    """ERS-WINDOW-0: epochs_active tracks each record_behavior call."""
    for i in range(10):
        spec.record_behavior("agent-D","t","s",0.3,0.0)
    assert spec.profile("agent-D").epochs_active == 10

def test_ers_09_window_constant_is_fifty():
    """ERS-WINDOW-0: SPECIALIZATION_WINDOW == 50."""
    assert SPECIALIZATION_WINDOW == 50

def test_ers_10_unspecialized_includes_under_window_agent(spec):
    """ERS-WINDOW-0: under-window agents appear in unspecialized_agents()."""
    _fill_agent(spec, "agent-E", n=5)
    assert "agent-E" in spec.unspecialized_agents()

# ─────────────────────────────────────────────────────────────────────────────
# ERS-THRESHOLD-0 — Specialization score gate (T101-ERS-11..16)
# ─────────────────────────────────────────────────────────────────────────────

def test_ers_11_threshold_blocks_mixed_agent(spec):
    """ERS-THRESHOLD-0: agent that spreads equally across targets not discovered."""
    targets = ["alpha","beta","gamma","delta"]
    for i in range(SPECIALIZATION_WINDOW):
        spec.record_behavior("agent-F", targets[i % len(targets)],
                             "structural_refactor", 0.2, 0.0)
    roles = spec.discover_roles()
    assert "agent-F" not in roles

def test_ers_12_threshold_passes_dominant_agent(spec):
    """ERS-THRESHOLD-0: agent with 70% dominance on one target qualifies."""
    for i in range(SPECIALIZATION_WINDOW):
        t = "main_target" if i < 35 else "other"
        spec.record_behavior("agent-G", t, "structural_refactor", 0.2, 0.0)
    roles = spec.discover_roles()
    assert "agent-G" in roles

def test_ers_13_specialization_score_correct(spec):
    """ERS-THRESHOLD-0: specialization_score = max_count / total."""
    p = AgentBehaviorProfile("x")
    for _ in range(7):
        p.record_action("A","s",0.5,0.0)
    for _ in range(3):
        p.record_action("B","s",0.5,0.0)
    assert p.specialization_score == pytest.approx(0.7)

def test_ers_14_threshold_constant_value():
    """ERS-THRESHOLD-0: SPECIALIZATION_THRESHOLD == 0.65."""
    assert SPECIALIZATION_THRESHOLD == pytest.approx(0.65)

def test_ers_15_score_zero_on_empty_profile():
    """ERS-THRESHOLD-0: empty profile returns specialization_score=0.0."""
    p = AgentBehaviorProfile("empty")
    assert p.specialization_score == pytest.approx(0.0)

def test_ers_16_profile_none_for_unknown_agent(spec):
    """ERS-THRESHOLD-0: profile() returns None for unobserved agent."""
    assert spec.profile("nobody") is None

# ─────────────────────────────────────────────────────────────────────────────
# ERS-DETERM-0 — Determinism (T101-ERS-17..23)
# ─────────────────────────────────────────────────────────────────────────────

def test_ers_17_same_observations_same_role(tmp_path):
    """ERS-DETERM-0: identical observation sequences produce identical EmergentRole."""
    def build(path):
        s = EmergentRoleSpecializer(path)
        _fill_agent(s,"agent-H")
        return s.discover_roles()["agent-H"]
    r1 = build(tmp_path/"a.json")
    r2 = build(tmp_path/"b.json")
    assert dataclasses.asdict(r1) == dataclasses.asdict(r2)

def test_ers_18_dominant_target_is_max_by_count(spec):
    """ERS-DETERM-0: dominant_target returns the most-observed target type."""
    p = AgentBehaviorProfile("q")
    for _ in range(5): p.record_action("A","s",0.5,0.0)
    for _ in range(3): p.record_action("B","s",0.5,0.0)
    assert p.dominant_target == "A"

def test_ers_19_dominant_strategy_deterministic_on_tie(spec):
    """ERS-DETERM-0: tie in strategy counts resolved alphabetically."""
    p = AgentBehaviorProfile("q")
    p.record_action("t","zebra",0.5,0.0)
    p.record_action("t","alpha",0.5,0.0)
    assert p.dominant_strategy == "alpha"

def test_ers_20_avg_risk_deterministic(spec):
    """ERS-DETERM-0: avg_risk is reproducible from fixed risk_scores."""
    p = AgentBehaviorProfile("r")
    p.record_action("t","s",0.2,0.0)
    p.record_action("t","s",0.4,0.0)
    assert p.avg_risk == pytest.approx(0.3)

def test_ers_21_role_archetypes_iteration_sorted(spec, qualified_spec):
    """ERS-DETERM-0: archetype matching iterates in sorted order — stable output."""
    roles_1 = qualified_spec.discover_roles()
    roles_2 = qualified_spec.discover_roles()
    assert roles_1["agent-A"].discovered_role == roles_2["agent-A"].discovered_role

def test_ers_22_avg_fitness_delta_correct(spec):
    """ERS-DETERM-0: avg_fitness_delta computed correctly."""
    p = AgentBehaviorProfile("f")
    p.record_action("t","s",0.5,0.1)
    p.record_action("t","s",0.5,0.3)
    assert p.avg_fitness_delta == pytest.approx(0.2)

def test_ers_23_undifferentiated_role_on_no_archetype_match(spec):
    """ERS-DETERM-0: agent with no archetype match gets 'emergent_' prefix role."""
    for _ in range(SPECIALIZATION_WINDOW):
        spec.record_behavior("agent-I","tgt","totally_novel_strategy_xyz",0.5,0.0)
    roles = spec.discover_roles()
    assert "agent-I" in roles
    assert roles["agent-I"].discovered_role.startswith("emergent_")

# ─────────────────────────────────────────────────────────────────────────────
# ERS-PERSIST-0 — State persistence (T101-ERS-24..28)
# ─────────────────────────────────────────────────────────────────────────────

def test_ers_24_save_uses_path_open(spec, qualified_spec):
    """ERS-PERSIST-0: _save uses Path.open not builtins.open."""
    with patch("runtime.innovations30.emergent_roles.Path.open",
               mock_open()) as mocked:
        qualified_spec._save()
        mocked.assert_called()

def test_ers_25_state_file_has_sorted_keys(qualified_spec):
    """ERS-PERSIST-0: saved JSON has sort_keys=True."""
    qualified_spec.discover_roles()
    raw = qualified_spec.state_path.read_text()
    data = json.loads(raw)
    keys = list(data.keys())
    assert keys == sorted(keys)

def test_ers_26_load_fail_open_on_corrupt_file(tmp_path):
    """ERS-PERSIST-0: corrupt state file results in empty dicts, no exception."""
    p = tmp_path / "roles.json"
    p.write_text("NOT_JSON")
    s = EmergentRoleSpecializer(p)
    assert s._profiles == {}
    assert s._discovered_roles == {}

def test_ers_27_roundtrip_preserves_role(tmp_path):
    """ERS-PERSIST-0: save then reload preserves discovered roles."""
    path = tmp_path / "roles.json"
    s1 = EmergentRoleSpecializer(path)
    _fill_agent(s1, "agent-J")
    s1.discover_roles()
    s2 = EmergentRoleSpecializer(path)
    assert s2.get_role("agent-J") is not None
    assert s2.get_role("agent-J").discovered_role == s1.get_role("agent-J").discovered_role

def test_ers_28_missing_state_file_loads_empty(tmp_path):
    """ERS-PERSIST-0: missing state file on load returns empty state, no exception."""
    s = EmergentRoleSpecializer(tmp_path / "nonexistent.json")
    assert s._profiles == {}

# ─────────────────────────────────────────────────────────────────────────────
# Integration (T101-ERS-29..30)
# ─────────────────────────────────────────────────────────────────────────────

def test_ers_29_all_five_archetypes_discoverable(tmp_path):
    """Integration: each ROLE_ARCHETYPES entry can be discovered from matching behavior."""
    archetype_configs = [
        ("structural_refactor",       0.2),
        ("test_coverage_expansion",   0.25),
        ("performance_optimization",  0.5),
        ("safety_hardening",          0.15),
        ("adaptive_self_mutate",      0.7),
    ]
    s = EmergentRoleSpecializer(tmp_path/"roles.json")
    for idx, (strategy, risk) in enumerate(archetype_configs):
        aid = f"agent-{idx}"
        for _ in range(SPECIALIZATION_WINDOW):
            s.record_behavior(aid,"tgt",strategy,risk,0.05)
    roles = s.discover_roles()
    discovered_role_names = {r.discovered_role for r in roles.values()}
    for archetype in ROLE_ARCHETYPES:
        assert archetype in discovered_role_names, f"Archetype {archetype} not discovered"

def test_ers_30_multi_agent_independent_classification(tmp_path):
    """Integration: multiple agents classified independently and correctly."""
    s = EmergentRoleSpecializer(tmp_path/"roles.json")
    _fill_agent(s,"agent-K","structural_refactor","module",0.2)
    _fill_agent(s,"agent-L","adaptive_self_mutate","runtime",0.7)
    roles = s.discover_roles()
    assert roles["agent-K"].discovered_role == "structural_architect"
    assert roles["agent-L"].discovered_role == "adaptive_explorer"
    assert roles["agent-K"].agent_id != roles["agent-L"].agent_id
