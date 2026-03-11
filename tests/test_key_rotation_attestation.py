# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from security.key_rotation_attestation import compute_attestation_hash, validate_rotation_record


def _base_record() -> dict[str, object]:
    record = {
        "rotation_date": "2026-01-10T00:00:00Z",
        "previous_rotation_date": "2025-12-10T00:00:00Z",
        "next_rotation_due": "2026-02-09T00:00:00Z",
        "policy_days": 30,
        "nonce": "abc",
        "generated_at": "2026-01-10T00:01:00Z",
        "host_info": {"host": "a"},
    }
    record["attestation_hash"] = compute_attestation_hash(record)
    return record


def test_compute_attestation_hash_ignores_ephemerals() -> None:
    a = _base_record()
    b = _base_record()
    b["nonce"] = "different"
    b["generated_at"] = "2026-01-10T00:02:00Z"
    b["host_info"] = {"host": "b"}
    b["attestation_hash"] = "sha256:deadbeef"
    assert compute_attestation_hash(a) == compute_attestation_hash(b)


def test_validate_rotation_record_enforces_monotonic_and_hash() -> None:
    valid = _base_record()
    result = validate_rotation_record(valid)
    assert result.ok is True

    invalid = dict(valid)
    invalid["previous_rotation_date"] = valid["rotation_date"]
    invalid["attestation_hash"] = compute_attestation_hash(invalid)
    non_monotonic = validate_rotation_record(invalid)
    assert non_monotonic.ok is False
    assert non_monotonic.reason == "rotation_not_monotonic"

    tampered = dict(valid)
    tampered["attestation_hash"] = "sha256:" + "0" * 64
    tampered_result = validate_rotation_record(tampered)
    assert tampered_result.ok is False
    assert tampered_result.reason == "attestation_hash_mismatch"


def test_validate_rotation_record_accepts_cryovant_metadata_shape() -> None:
    result = validate_rotation_record(
        {
            "interval_seconds": 3600,
            "last_rotation_ts": 1700000000,
            "last_rotation_iso": "2024-01-01T00:00:00Z",
        }
    )
    assert result.ok is True
    assert result.reason == "ok"


def test_validate_rotation_record_legacy_invalid_types_are_rejected() -> None:
    result = validate_rotation_record(
        {
            "interval_seconds": "bad",
            "last_rotation_ts": 1700000000,
            "last_rotation_iso": "2024-01-01T00:00:00Z",
        }
    )
    assert result.ok is False
    assert result.reason == "interval_seconds_invalid"
