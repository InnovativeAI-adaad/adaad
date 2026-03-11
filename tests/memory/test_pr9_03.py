# SPDX-License-Identifier: Apache-2.0
"""
Phase 9 PR-9-03 — Test suite for ContextReplayInterface + Constitution v0.5.0.

Test IDs: T9-03-01 through T9-03-15

Coverage:
    ContextReplayInterface  (T9-03-01..10) — injection build, window, skip conditions,
                                              signal_quality_ok, explore_ratio, digest
    Constitution v0.5.0     (T9-03-11..15) — version bump, soulbound_privacy_invariant
                                              registered, validator runs without crash,
                                              constitution.yaml rule present
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
pytestmark = pytest.mark.regression_standard

# ─── Test helpers ──────────────────────────────────────────────────────────

_TEST_KEY_BYTES = bytes.fromhex("c" * 64)


def _no_op_audit(*args, **kwargs):
    return {}


def _make_ledger(tmp_path: Path):
    from runtime.memory.soulbound_ledger import SoulboundLedger
    return SoulboundLedger(
        ledger_path=tmp_path / "ledger.json",
        audit_writer=_no_op_audit,
        key_override=_TEST_KEY_BYTES,
    )


def _make_extractor(ledger, tmp_path: Path = None):
    from runtime.memory.craft_pattern_extractor import CraftPatternExtractor
    return CraftPatternExtractor(
        ledger=ledger,
        audit_writer=_no_op_audit,
        min_accepted=2,
    )


def _make_score(agent="architect", score=0.75):
    s = MagicMock()
    s.mutation_id = f"mut-{agent}"
    s.agent_origin = agent
    s.score = score
    s.accepted = True
    s.dimension_breakdown = {"risk_penalty_contrib": 0.12, "complexity_penalty_contrib": 0.03}
    return s


def _populate_ledger(ledger, n_epochs: int = 3, velocity: float = 0.02):
    """Populate ledger with n_epochs of craft_pattern entries."""
    from runtime.memory.craft_pattern_extractor import CraftPatternExtractor
    extractor = CraftPatternExtractor(
        ledger=ledger, audit_writer=_no_op_audit, min_accepted=2
    )
    for i in range(n_epochs):
        scores = [_make_score("architect", 0.80), _make_score("architect", 0.72),
                  _make_score("dream", 0.65)]
        extractor.extract(
            epoch_id=f"epoch-{i:03d}",
            accepted_scores=scores,
            weight_velocity_risk=velocity,
            weight_velocity_complexity=velocity,
        )


# ════════════════════════════════════════════════════════════════════════════
# ContextReplayInterface — T9-03-01..10
# ════════════════════════════════════════════════════════════════════════════

class TestContextReplayInterface:

    def _make_replay(self, ledger):
        from runtime.memory.context_replay_interface import ContextReplayInterface
        return ContextReplayInterface(ledger=ledger, audit_writer=_no_op_audit)

    def test_T9_03_01_build_injection_skips_on_empty_ledger(self, tmp_path):
        """build_injection() must return skipped=True when ledger has no craft_pattern entries."""
        ledger = _make_ledger(tmp_path)
        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-001")
        assert injection.skipped is True
        assert injection.skip_reason is not None

    def test_T9_03_02_build_injection_succeeds_when_entries_present(self, tmp_path):
        """build_injection() must return skipped=False when valid entries exist."""
        ledger = _make_ledger(tmp_path)
        _populate_ledger(ledger, n_epochs=3)
        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-010")
        assert injection.skipped is False
        assert injection.signal_quality_ok is True

    def test_T9_03_03_context_digest_is_64_char_hex(self, tmp_path):
        """injection.context_digest must be a 64-char SHA-256 hex string."""
        ledger = _make_ledger(tmp_path)
        _populate_ledger(ledger, n_epochs=3)
        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-010")
        assert len(injection.context_digest) == 64
        assert all(c in "0123456789abcdef" for c in injection.context_digest)

    def test_T9_03_04_dominant_pattern_is_most_frequent(self, tmp_path):
        """dominant_pattern must be the most frequent dominant_pattern in window."""
        ledger = _make_ledger(tmp_path)
        _populate_ledger(ledger, n_epochs=5)  # all architect → structural
        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-010")
        # architect is dominant in each epoch → structural
        assert injection.dominant_pattern == "structural"

    def test_T9_03_05_adjusted_explore_ratio_boosted_for_experimental(self, tmp_path):
        """adjusted_explore_ratio must be boosted when dominant_pattern='experimental'."""
        from runtime.memory.craft_pattern_extractor import CraftPatternExtractor
        from runtime.memory.context_replay_interface import EXPLORE_RATIO_BOOST

        ledger = _make_ledger(tmp_path)
        extractor = CraftPatternExtractor(ledger=ledger, audit_writer=_no_op_audit, min_accepted=2)
        # Use dream agent (experimental) as dominant
        for i in range(3):
            scores = [_make_score("dream", 0.80), _make_score("dream", 0.75),
                      _make_score("architect", 0.60)]
            extractor.extract(epoch_id=f"e{i}", accepted_scores=scores,
                              weight_velocity_risk=0.02, weight_velocity_complexity=0.02)

        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-010")
        # experimental → boosted
        assert injection.adjusted_explore_ratio >= 0.50 + EXPLORE_RATIO_BOOST - 0.01

    def test_T9_03_06_adjusted_explore_ratio_reduced_for_structural(self, tmp_path):
        """adjusted_explore_ratio must be reduced when dominant_pattern='structural'."""
        from runtime.memory.context_replay_interface import EXPLORE_RATIO_BOOST
        ledger = _make_ledger(tmp_path)
        _populate_ledger(ledger, n_epochs=3)  # architect → structural
        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-010")
        # structural → reduced
        assert injection.adjusted_explore_ratio <= 0.50 - EXPLORE_RATIO_BOOST + 0.01

    def test_T9_03_07_explore_ratio_clamped_to_floor(self, tmp_path):
        """adjusted_explore_ratio must never be below EXPLOIT_RATIO_FLOOR."""
        from runtime.memory.context_replay_interface import EXPLOIT_RATIO_FLOOR
        ledger = _make_ledger(tmp_path)
        _populate_ledger(ledger, n_epochs=5)
        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-010")
        assert injection.adjusted_explore_ratio >= EXPLOIT_RATIO_FLOOR

    def test_T9_03_08_low_velocity_entries_excluded(self, tmp_path):
        """Entries with signal_quality_flag='low_velocity' must be filtered out."""
        from runtime.memory.craft_pattern_extractor import (
            CraftPatternExtractor, VELOCITY_QUALITY_THRESHOLD
        )
        ledger = _make_ledger(tmp_path)
        extractor = CraftPatternExtractor(ledger=ledger, audit_writer=_no_op_audit, min_accepted=2)

        # Write 3 entries with low_velocity (velocity below threshold)
        for i in range(3):
            scores = [_make_score("architect", 0.75), _make_score("dream", 0.65)]
            extractor.extract(
                epoch_id=f"e{i}",
                accepted_scores=scores,
                weight_velocity_risk=VELOCITY_QUALITY_THRESHOLD * 0.1,    # << low
                weight_velocity_complexity=VELOCITY_QUALITY_THRESHOLD * 0.1,
            )

        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-010")
        # All entries low_velocity → should skip
        assert injection.skipped is True or injection.signal_quality_ok is False

    def test_T9_03_09_window_limits_entries_read(self, tmp_path):
        """valid_entry_count must not exceed window_size."""
        from runtime.memory.context_replay_interface import (
            ContextReplayInterface, REPLAY_WINDOW_SIZE
        )
        ledger = _make_ledger(tmp_path)
        _populate_ledger(ledger, n_epochs=REPLAY_WINDOW_SIZE + 3)

        replay = ContextReplayInterface(ledger=ledger, audit_writer=_no_op_audit)
        injection = replay.build_injection(epoch_id="epoch-099")
        assert injection.window_size <= REPLAY_WINDOW_SIZE

    def test_T9_03_10_injection_as_dict_is_json_serialisable(self, tmp_path):
        """injection.as_dict() must produce a JSON-serialisable dict."""
        ledger = _make_ledger(tmp_path)
        _populate_ledger(ledger, n_epochs=3)
        replay = self._make_replay(ledger)
        injection = replay.build_injection(epoch_id="epoch-010")
        serialized = json.dumps(injection.as_dict())
        assert isinstance(serialized, str)


# ════════════════════════════════════════════════════════════════════════════
# Constitution v0.5.0 — T9-03-11..15
# ════════════════════════════════════════════════════════════════════════════

class TestConstitutionV050:

    def test_T9_03_11_constitution_version_is_0_5_0(self):
        """CONSTITUTION_VERSION must be >= '0.5.0' (soulbound_privacy_invariant introduced)."""
        from runtime.constitution import CONSTITUTION_VERSION
        from packaging.version import Version
        assert Version(CONSTITUTION_VERSION) >= Version("0.5.0")

    def test_T9_03_12_soulbound_privacy_invariant_in_validator_registry(self):
        """soulbound_privacy_invariant must be registered in VALIDATOR_REGISTRY."""
        from runtime.constitution import VALIDATOR_REGISTRY
        assert "soulbound_privacy_invariant" in VALIDATOR_REGISTRY

    def test_T9_03_13_soulbound_privacy_validator_returns_ok_true(self):
        """_validate_soulbound_privacy_invariant must return ok=True (ignores request)."""
        from runtime.constitution import VALIDATOR_REGISTRY
        validator = VALIDATOR_REGISTRY["soulbound_privacy_invariant"]
        # Validator signature takes a MutationRequest but ignores it (uses _ param name)
        result = validator(None)
        assert result["ok"] is True
        assert "soulbound_privacy_invariant_recorded" in result.get("reason", "")

    def test_T9_03_14_constitution_yaml_contains_soulbound_rule(self):
        """constitution.yaml must declare a 'soulbound_privacy_invariant' rule."""
        yaml_path = Path("runtime/governance/constitution.yaml")
        doc = json.loads(yaml_path.read_text())
        rule_names = [r["name"] for r in doc.get("rules", [])]
        assert "soulbound_privacy_invariant" in rule_names

    def test_T9_03_15_constitution_yaml_version_is_0_5_0(self):
        """constitution.yaml version field must be >= '0.5.0' (soulbound_privacy_invariant introduced)."""
        from packaging.version import Version
        yaml_path = Path("runtime/governance/constitution.yaml")
        doc = json.loads(yaml_path.read_text())
        assert Version(doc["version"]) >= Version("0.5.0")
