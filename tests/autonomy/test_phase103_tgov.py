# SPDX-License-Identifier: Apache-2.0
"""
T103-TGOV: Phase 103 Temporal Governance Test Harness.
Deterministic validation of health-adjusted rule severities and cryptographic log integrity.
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Any

import pytest
from runtime.innovations30.temporal_governance import TemporalGovernanceEngine, GovernanceWindow

# Deterministic constants for CEL-REPLAY-0
FIXED_TIMESTAMP = 1775243822.0
EPOCH_ALPHA = "epoch-alpha"
EPOCH_BETA  = "epoch-beta"

@pytest.fixture
def tgov_engine(tmp_path: Path, monkeypatch):
    """Initialise TemporalGovernanceEngine with a deterministic time provider and sandbox path."""
    state_file = tmp_path / "tgov_state.jsonl"
    # CEL-REPLAY-0: force deterministic timestamp
    monkeypatch.setattr("time.time", lambda: FIXED_TIMESTAMP)
    return TemporalGovernanceEngine(state_path=state_file)

def test_t103_tgov_01_high_health_severity(tgov_engine):
    """T103-TGOV-01: High health score (>= 0.85) triggers high_health_severity (e.g. warning)."""
    tgov_engine.register_window(GovernanceWindow(
        rule_name="test_rule",
        baseline_severity="blocking",
        high_health_severity="warning",
        low_health_severity="blocking",
        high_health_threshold=0.85
    ))
    
    # 0.90 >= 0.85 -> should be warning
    assert tgov_engine.effective_severity("test_rule", 0.90) == "warning"
    # 0.85 >= 0.85 -> should be warning (boundary inclusive)
    assert tgov_engine.effective_severity("test_rule", 0.85) == "warning"

def test_t103_tgov_02_low_health_severity(tgov_engine):
    """T103-TGOV-02: Low health score (< 0.60) triggers low_health_severity (e.g. blocking)."""
    tgov_engine.register_window(GovernanceWindow(
        rule_name="test_rule",
        baseline_severity="warning",
        high_health_severity="advisory",
        low_health_severity="blocking",
        low_health_threshold=0.60
    ))
    
    # 0.50 < 0.60 -> should be blocking
    assert tgov_engine.effective_severity("test_rule", 0.50) == "blocking"
    # 0.70 is in the middle -> should be baseline warning
    assert tgov_engine.effective_severity("test_rule", 0.70) == "warning"

def test_t103_tgov_03_cryptographic_chain_integrity(tgov_engine):
    """T103-TGOV-03: log_adjustment entries form a verifiable SHA-256 hash chain (TGOV-CHAIN-0)."""
    tgov_engine.log_adjustment(EPOCH_ALPHA, 0.90)
    tgov_engine.log_adjustment(EPOCH_BETA, 0.50)
    
    trail = tgov_engine.audit_trail()
    assert len(trail) == 2
    
    entry1 = trail[0]
    entry2 = trail[1]
    
    # Genesis check
    assert entry1["prev_digest"] == "genesis"
    
    # Chain link check
    assert entry2["prev_digest"] == entry1["digest"]
    
    # Manual verification of the second entry's digest
    # Note: sort_keys=True is critical for deterministic hashing
    payload = json.dumps({
        "epoch_id": entry2["epoch_id"],
        "health_score": round(entry2["health_score"], 4),
        "adjustments": entry2["adjustments"],
        "prev_digest": entry2["prev_digest"],
    }, sort_keys=True)
    expected_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
    assert entry2["digest"] == expected_digest

def test_t103_tgov_04_health_trend_analysis(tgov_engine):
    """T103-TGOV-04: health_trend correctly identifies improving/degrading/stable states."""
    # Stable: not enough data
    tgov_engine.log_adjustment("e1", 0.80)
    assert tgov_engine.health_trend() == "stable"
    
    # Improving: 0.80 -> 0.90 (+0.10 > 0.05)
    tgov_engine.log_adjustment("e2", 0.90)
    assert tgov_engine.health_trend() == "improving"
    
    # Degrading: 0.80 -> 0.90 -> 0.70 (delta 0.70 - 0.80 = -0.10 < -0.05)
    # Note: health_trend checks delta between last and first in window
    tgov_engine.log_adjustment("e3", 0.70)
    assert tgov_engine.health_trend() == "degrading"

def test_t103_tgov_05_state_corruption_resilience(tgov_engine):
    """T103-TGOV-05: State persistence survives malformed JSON lines without halting (TGOV-CORRUPT-SKIP-0)."""
    tgov_engine.log_adjustment("e1", 0.80)
    
    # LSME-0: Manually append corruption to the shadow-path file
    with tgov_engine.state_path.open("a") as f:
        f.write("NOT_JSON_AT_ALL\n")
        f.write('{"epoch_id": "e2", "partially_valid": true}\n')
    
    tgov_engine.log_adjustment("e3", 0.90)
    
    trail = tgov_engine.audit_trail()
    # Should have e1, e2 (partial), and e3. The non-JSON line is skipped.
    assert len(trail) == 3
    assert trail[0]["epoch_id"] == "e1"
    assert trail[1]["epoch_id"] == "e2"
    assert trail[2]["epoch_id"] == "e3"
