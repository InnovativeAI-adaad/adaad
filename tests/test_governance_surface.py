import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from runtime.governance_surface import (
    VERSION_COMPARISON_EPHEMERAL_FIELDS,
    VOLATILE_DETAIL_KEYS,
    canonicalize_governance_details,
    strip_version_comparison_ephemerals,
)


def test_canonicalize_governance_details_excludes_volatile_keys() -> None:
    payload = {
        "reason": "ok",
        "resource_usage_snapshot": {"memory_mb": 12.3},
        "details": {"validator": "v", "window_start_ts": 123},
    }

    canonical = canonicalize_governance_details(payload)

    assert "resource_usage_snapshot" not in canonical
    assert "window_start_ts" not in canonical["details"]
    assert canonical["reason"] == "ok"


def test_version_comparison_ephemeral_fields_strict_superset() -> None:
    assert VOLATILE_DETAIL_KEYS < VERSION_COMPARISON_EPHEMERAL_FIELDS


def test_strip_version_comparison_ephemerals_removes_runtime_noise() -> None:
    payload = {
        "verification_result": "pass",
        "nonce": "nonce-2",
        "generated_at": "2026-02-01T00:00:02Z",
        "run_id": "run-b",
        "details": {"window_start_ts": 111, "stable": "yes"},
    }

    stripped = strip_version_comparison_ephemerals(payload)

    assert stripped == {"verification_result": "pass", "details": {"stable": "yes"}}
