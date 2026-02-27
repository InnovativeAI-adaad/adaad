# SPDX-License-Identifier: Apache-2.0

from runtime.governance_surface import canonicalize_governance_details


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
