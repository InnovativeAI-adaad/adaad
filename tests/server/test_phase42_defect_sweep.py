"""
Phase 42 — Critical Defect Sweep
==================================

T42-S01  environment_snapshot.py has import json
T42-S02  executor.py _record_evidence uses replay_environment_fingerprint param
T42-A01  adversarial RTN-001 passes (cryovant_legacy_static_payload_signature_rejected CRITICAL)
T42-A02  metrics.line_count() is defined in runtime/metrics.py
T42-A03  metrics.tail_after() is defined in runtime/metrics.py
T42-N01  _RegistryLedgerStub has read_all method
T42-M01  app/main.py has module-level run_replay_preflight
T42-M02  app/main.py has module-level run_mutation_cycle
T42-M03  Orchestrator._run_replay_preflight delegates to run_replay_preflight
T42-M04  Orchestrator._run_mutation_cycle delegates to run_mutation_cycle
T42-B01  BeastModeLoop has _legacy property
T42-B02  BeastModeLoop._legacy returns LegacyBeastModeCompatibilityAdapter instance
T42-C01  checkpoint_registry emits CheckpointGovernanceEvent with event_type=checkpoint_created
T42-C02  CheckpointGovernanceEvent has prior_checkpoint_event_hash field
T42-D01  DreamMode has _clamp_aggression static method
T42-D02  DreamMode._clamp_aggression(-1) == 0.0
T42-D03  DreamMode._clamp_aggression(2) == 1.0
T42-D04  DreamMode._clamp_aggression(0.5) == 0.5
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


class TestEnvironmentSnapshot:
    def test_has_import_json(self):
        """T42-S01: environment_snapshot.py imports json."""
        src = (REPO_ROOT / "runtime" / "sandbox" / "environment_snapshot.py").read_text()
        assert "import json" in src

    def test_record_evidence_uses_param(self):
        """T42-S02: executor.py _record_evidence uses replay_environment_fingerprint param."""
        src = (REPO_ROOT / "runtime" / "sandbox" / "executor.py").read_text()
        # Should use the parameter, not the undefined local variable
        assert "replay_environment_fingerprint=replay_environment_fingerprint" in src
        assert "replay_environment_fingerprint=pre_execution_snapshot" not in src.split("def _record_evidence")[1].split("def ")[0]


class TestAdversarialHarness:
    def test_metrics_line_count_defined(self):
        """T42-A02: metrics.line_count() is defined."""
        src = (REPO_ROOT / "runtime" / "metrics.py").read_text()
        assert "def line_count()" in src

    def test_metrics_tail_after_defined(self):
        """T42-A03: metrics.tail_after() is defined."""
        src = (REPO_ROOT / "runtime" / "metrics.py").read_text()
        assert "def tail_after(" in src

    def test_harness_uses_line_count(self):
        """T42-A01: adversarial harness uses line_count for delta tracking."""
        src = (REPO_ROOT / "runtime" / "analysis" / "adversarial_scenario_harness.py").read_text()
        assert "metrics.line_count()" in src
        assert "metrics.tail_after(" in src

    def test_rtn001_passes(self):
        """T42-A01: RTN-001 legacy_signature_misuse scenario passes."""
        from runtime.analysis.adversarial_scenario_harness import run_manifest
        report = run_manifest(Path("tests/security/fixtures/adversarial_governance_scenarios.json"))
        by_id = {r["scenario_id"]: r for r in report["results"]}
        assert by_id["RTN-001"]["passed"] is True


class TestNullGuards:
    def test_registry_ledger_stub_has_read_all(self):
        """T42-N01: _RegistryLedgerStub.read_all is defined."""
        src = (REPO_ROOT / "tests" / "stability" / "test_null_guards.py").read_text()
        assert "def read_all" in src


class TestAppMain:
    def test_run_replay_preflight_module_level(self):
        """T42-M01: app/main.py has module-level run_replay_preflight."""
        src = (REPO_ROOT / "app" / "main.py").read_text()
        assert "def run_replay_preflight(" in src
        # Must be at module level (0 indent)
        assert "\ndef run_replay_preflight(" in src

    def test_run_mutation_cycle_module_level(self):
        """T42-M02: app/main.py has module-level run_mutation_cycle."""
        src = (REPO_ROOT / "app" / "main.py").read_text()
        assert "\ndef run_mutation_cycle(" in src

    def test_orchestrator_delegates_replay_preflight(self):
        """T42-M03: Orchestrator._run_replay_preflight delegates to module-level."""
        src = (REPO_ROOT / "app" / "main.py").read_text()
        # Method body should call run_replay_preflight(self, ...)
        method_start = src.find("def _run_replay_preflight(self")
        method_body = src[method_start:method_start + 200]
        assert "run_replay_preflight(self," in method_body

    def test_orchestrator_delegates_mutation_cycle(self):
        """T42-M04: Orchestrator._run_mutation_cycle delegates to module-level."""
        src = (REPO_ROOT / "app" / "main.py").read_text()
        method_start = src.find("def _run_mutation_cycle(self)")
        method_body = src[method_start:method_start + 200]
        assert "run_mutation_cycle(self)" in method_body


class TestBeastModeLoop:
    def test_legacy_property_in_source(self):
        """T42-B01: BeastModeLoop._legacy property is defined."""
        src = (REPO_ROOT / "app" / "beast_mode_loop.py").read_text()
        assert "@property" in src
        assert "def _legacy(" in src

    def test_legacy_returns_adapter(self, tmp_path):
        """T42-B02: _legacy returns LegacyBeastModeCompatibilityAdapter."""
        os.environ.setdefault("ADAAD_ENV", "dev")
        agents_root = tmp_path / "agents"
        agents_root.mkdir()
        lineage_dir = tmp_path / "lineage"
        lineage_dir.mkdir()
        from app.beast_mode_loop import BeastModeLoop, LegacyBeastModeCompatibilityAdapter
        beast = BeastModeLoop(agents_root, lineage_dir)
        assert isinstance(beast._legacy, LegacyBeastModeCompatibilityAdapter)

    def test_legacy_lazy_singleton(self, tmp_path):
        """T42-B02b: _legacy returns same instance on repeated access."""
        os.environ.setdefault("ADAAD_ENV", "dev")
        agents_root = tmp_path / "agents"
        agents_root.mkdir()
        lineage_dir = tmp_path / "lineage"
        lineage_dir.mkdir()
        from app.beast_mode_loop import BeastModeLoop
        beast = BeastModeLoop(agents_root, lineage_dir)
        assert beast._legacy is beast._legacy


class TestCheckpointRegistry:
    def test_governance_event_type_in_source(self):
        """T42-C01: CheckpointGovernanceEvent is emitted by create_checkpoint."""
        src = (REPO_ROOT / "runtime" / "evolution" / "checkpoint_registry.py").read_text()
        assert '"CheckpointGovernanceEvent"' in src

    def test_governance_event_has_prior_hash_field(self):
        """T42-C02: Governance event payload includes prior_checkpoint_event_hash."""
        src = (REPO_ROOT / "runtime" / "evolution" / "checkpoint_registry.py").read_text()
        assert "prior_checkpoint_event_hash" in src

    def test_event_type_field_is_checkpoint_created(self):
        """T42-C01b: governance payload event_type is checkpoint_created."""
        src = (REPO_ROOT / "runtime" / "evolution" / "checkpoint_registry.py").read_text()
        assert '"event_type": "checkpoint_created"' in src


class TestDreamModeAggression:
    def test_clamp_aggression_in_source(self):
        """T42-D01: DreamMode._clamp_aggression is defined."""
        src = (REPO_ROOT / "app" / "dream_mode.py").read_text()
        assert "def _clamp_aggression(" in src

    def test_clamp_negative(self):
        """T42-D02: _clamp_aggression(-1) == 0.0."""
        from app.dream_mode import DreamMode
        assert DreamMode._clamp_aggression(-1) == 0.0

    def test_clamp_over_one(self):
        """T42-D03: _clamp_aggression(2) == 1.0."""
        from app.dream_mode import DreamMode
        assert DreamMode._clamp_aggression(2) == 1.0

    def test_clamp_mid_range(self):
        """T42-D04: _clamp_aggression(0.5) == 0.5."""
        from app.dream_mode import DreamMode
        assert DreamMode._clamp_aggression(0.5) == 0.5
