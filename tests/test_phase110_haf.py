# SPDX-License-Identifier: Apache-2.0
"""T110-HAF-01..30 — Phase 110 acceptance tests for INNOV-25 Hardware-Adaptive Fitness.

Constitutional invariants under test:
    HAF-0        — profile_id non-empty; weights sum to 1.0 ± 0.001; bounds [0.01, 0.90]
    HAF-DETERM-0 — adapted_weights deterministic for identical profile
    HAF-AUDIT-0  — score_with_profile returns AuditRecord with required fields
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from runtime.innovations30.hardware_adaptive_fitness import (
    HardwareAdaptiveFitness, HardwareProfile, AuditRecord, WeightDriftGuard,
    BASE_WEIGHTS, HAF_INVARIANTS, WEIGHT_SUM_TOLERANCE, profile_fingerprint,
)

BASE = {"correctness_score": 0.8, "efficiency_score": 0.7,
        "policy_compliance_score": 0.9, "goal_alignment_score": 0.6,
        "simulated_market_score": 0.5}

# ── Fixture helpers ──────────────────────────────────────────────────────────
def make_haf(profile=None):
    return HardwareAdaptiveFitness(profile)

# ══════════════════════════════════════════════════════════════════════════════
# T110-HAF-01: module imports without error
def test_T110_HAF_01_module_import():
    assert HardwareAdaptiveFitness is not None

# T110-HAF-02: HAF_INVARIANTS contains exactly three required keys
def test_T110_HAF_02_invariant_registry():
    assert set(HAF_INVARIANTS.keys()) == {"HAF-0", "HAF-DETERM-0", "HAF-AUDIT-0"}

# T110-HAF-03: HAF-0 enforced — empty profile_id raises ValueError
def test_T110_HAF_03_empty_profile_id_rejected():
    with pytest.raises(ValueError, match="HAF-0"):
        HardwareProfile(profile_id="", architecture="x86_64", ram_mb=2048,
                        is_battery_constrained=False, thermal_envelope="medium",
                        storage_mb=10240)

# T110-HAF-04: whitespace-only profile_id also rejected
def test_T110_HAF_04_whitespace_profile_id_rejected():
    with pytest.raises(ValueError, match="HAF-0"):
        HardwareProfile(profile_id="   ", architecture="x86_64", ram_mb=2048,
                        is_battery_constrained=False, thermal_envelope="medium",
                        storage_mb=10240)

# T110-HAF-05: desktop_moderate weights sum to 1.0 ± tolerance
def test_T110_HAF_05_desktop_weights_sum():
    h = make_haf(HardwareProfile.desktop_moderate())
    w = h.adapted_weights()
    assert abs(sum(w.values()) - 1.0) <= WEIGHT_SUM_TOLERANCE

# T110-HAF-06: android_minimal weights sum to 1.0 ± tolerance
def test_T110_HAF_06_android_weights_sum():
    h = make_haf(HardwareProfile.android_minimal())
    w = h.adapted_weights()
    assert abs(sum(w.values()) - 1.0) <= WEIGHT_SUM_TOLERANCE

# T110-HAF-07: server_standard weights sum to 1.0 ± tolerance
def test_T110_HAF_07_server_weights_sum():
    h = make_haf(HardwareProfile.server_standard())
    w = h.adapted_weights()
    assert abs(sum(w.values()) - 1.0) <= WEIGHT_SUM_TOLERANCE

# T110-HAF-08: all weights within [WEIGHT_MIN, WEIGHT_MAX] for desktop
def test_T110_HAF_08_weights_bounds_desktop():
    h = make_haf(HardwareProfile.desktop_moderate())
    for k, v in h.adapted_weights().items():
        assert 0.01 <= v <= 0.90, f"{k}={v}"

# T110-HAF-09: all weights within bounds for android
def test_T110_HAF_09_weights_bounds_android():
    h = make_haf(HardwareProfile.android_minimal())
    for k, v in h.adapted_weights().items():
        assert 0.01 <= v <= 0.90, f"{k}={v}"

# T110-HAF-10: all weights within bounds for server
def test_T110_HAF_10_weights_bounds_server():
    h = make_haf(HardwareProfile.server_standard())
    for k, v in h.adapted_weights().items():
        assert 0.01 <= v <= 0.90, f"{k}={v}"

# T110-HAF-11: HAF-DETERM-0 — identical profile produces identical weights
def test_T110_HAF_11_determinism_desktop():
    h1 = make_haf(HardwareProfile.desktop_moderate())
    h2 = make_haf(HardwareProfile.desktop_moderate())
    assert h1.adapted_weights() == h2.adapted_weights()

# T110-HAF-12: HAF-DETERM-0 — determinism for android profile
def test_T110_HAF_12_determinism_android():
    h1 = make_haf(HardwareProfile.android_minimal())
    h2 = make_haf(HardwareProfile.android_minimal())
    assert h1.adapted_weights() == h2.adapted_weights()

# T110-HAF-13: HAF-DETERM-0 — determinism for server profile
def test_T110_HAF_13_determinism_server():
    h1 = make_haf(HardwareProfile.server_standard())
    h2 = make_haf(HardwareProfile.server_standard())
    assert h1.adapted_weights() == h2.adapted_weights()

# T110-HAF-14: battery-constrained profile elevates efficiency_score weight
def test_T110_HAF_14_battery_elevates_efficiency():
    android = make_haf(HardwareProfile.android_minimal())
    server = make_haf(HardwareProfile.server_standard())
    assert android.adapted_weights()["efficiency_score"] > server.adapted_weights()["efficiency_score"]

# T110-HAF-15: server profile elevates correctness_score weight
def test_T110_HAF_15_server_elevates_correctness():
    server = make_haf(HardwareProfile.server_standard())
    android = make_haf(HardwareProfile.android_minimal())
    assert server.adapted_weights()["correctness_score"] >= android.adapted_weights()["correctness_score"]

# T110-HAF-16: HAF-AUDIT-0 — score_with_profile returns (float, AuditRecord)
def test_T110_HAF_16_score_returns_audit_record():
    h = make_haf()
    score, record = h.score_with_profile(BASE)
    assert isinstance(score, float)
    assert isinstance(record, AuditRecord)

# T110-HAF-17: AuditRecord has non-empty profile_fingerprint
def test_T110_HAF_17_audit_fingerprint_nonempty():
    _, record = make_haf().score_with_profile(BASE)
    assert record.profile_fingerprint.startswith("sha256:")
    assert len(record.profile_fingerprint) > 10

# T110-HAF-18: AuditRecord weights_snapshot matches adapted_weights
def test_T110_HAF_18_audit_weights_match():
    h = make_haf()
    _, record = h.score_with_profile(BASE)
    assert record.weights_snapshot == h.adapted_weights()

# T110-HAF-19: AuditRecord composite_score matches manual calculation
def test_T110_HAF_19_composite_score_correct():
    h = make_haf()
    score, record = h.score_with_profile(BASE)
    expected = round(sum(BASE.get(k, 0.0) * w for k, w in h.adapted_weights().items()), 4)
    assert score == expected
    assert record.composite_score == expected

# T110-HAF-20: AuditRecord invariants_verified list contains all three invariants
def test_T110_HAF_20_audit_invariants_listed():
    _, record = make_haf().score_with_profile(BASE)
    assert set(record.invariants_verified) == {"HAF-0", "HAF-DETERM-0", "HAF-AUDIT-0"}

# T110-HAF-21: to_ledger_row produces valid JSON
def test_T110_HAF_21_ledger_row_valid_json():
    _, record = make_haf().score_with_profile(BASE)
    row = record.to_ledger_row()
    parsed = json.loads(row)
    assert parsed["innovation"] == "INNOV-25"

# T110-HAF-22: to_ledger_row is single-line (no embedded newlines)
def test_T110_HAF_22_ledger_row_single_line():
    _, record = make_haf().score_with_profile(BASE)
    assert "\n" not in record.to_ledger_row()

# T110-HAF-23: profile_fingerprint is deterministic for identical profile
def test_T110_HAF_23_fingerprint_deterministic():
    p = HardwareProfile.android_minimal()
    assert profile_fingerprint(p) == profile_fingerprint(p)

# T110-HAF-24: profile_fingerprint differs for distinct profiles
def test_T110_HAF_24_fingerprint_distinct_profiles():
    assert profile_fingerprint(HardwareProfile.android_minimal()) != \
           profile_fingerprint(HardwareProfile.server_standard())

# T110-HAF-25: WeightDriftGuard rejects weights that don't sum to ~1.0
def test_T110_HAF_25_drift_guard_sum_violation():
    with pytest.raises(RuntimeError, match="HAF-0"):
        WeightDriftGuard.validate({"a": 0.5, "b": 0.5, "c": 0.1})

# T110-HAF-26: WeightDriftGuard rejects weight below WEIGHT_MIN
def test_T110_HAF_26_drift_guard_min_violation():
    bad = {"a": 0.9999, "b": 0.0001}
    with pytest.raises(RuntimeError, match="HAF-0"):
        WeightDriftGuard.validate(bad)

# T110-HAF-27: WeightDriftGuard accepts valid normalised weights
def test_T110_HAF_27_drift_guard_valid_pass():
    ok = {"a": 0.50, "b": 0.30, "c": 0.20}
    WeightDriftGuard.validate(ok)  # must not raise

# T110-HAF-28: default profile is desktop_moderate when None provided
def test_T110_HAF_28_default_profile_desktop():
    h = make_haf(None)
    assert h.profile.profile_id == "desktop-moderate"

# T110-HAF-29: profile_description includes architecture and RAM
def test_T110_HAF_29_profile_description_content():
    h = make_haf(HardwareProfile.server_standard())
    desc = h.profile_description()
    assert "x86_64" in desc
    assert "8192" in desc

# T110-HAF-30: adapted_weights returns five canonical fitness dimensions
def test_T110_HAF_30_five_dimensions_returned():
    h = make_haf()
    keys = set(h.adapted_weights().keys())
    assert keys == set(BASE_WEIGHTS.keys())
