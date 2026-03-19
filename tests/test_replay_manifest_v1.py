# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json

import pytest

from runtime.evolution.replay_manifest import (
    build_replay_manifest_v1,
    canonical_replay_manifest_bytes,
    replay_manifest_filename,
    validate_replay_manifest_schema,
    verify_replay_manifest_signature,
    write_replay_manifest_v1,
)

pytestmark = pytest.mark.regression_standard


def _preflight_payload() -> dict[str, object]:
    return {
        "mode": "strict",
        "verify_target": "all_epochs",
        "decision": "continue",
        "federation_drift_detected": False,
        "results": [
            {
                "epoch_id": "epoch-b",
                "decision": "diverge",
                "passed": False,
                "replay_score": 0.2,
                "baseline_source": "lineage_epoch_digest",
                "digest_match": False,
                "trusted": False,
                "cause_buckets": {"digest_mismatch": True, "time_input_variance": False},
            },
            {
                "epoch_id": "epoch-a",
                "decision": "match",
                "passed": True,
                "replay_score": 1.0,
                "baseline_source": "lineage_epoch_digest",
                "digest_match": True,
                "trusted": True,
                "cause_buckets": {"digest_mismatch": False, "time_input_variance": False},
            },
        ],
    }


def test_replay_manifest_schema_valid_and_signature_verifies() -> None:
    manifest = build_replay_manifest_v1(
        replay_started_at="2026-03-19T00:00:00Z",
        replay_finished_at="2026-03-19T00:00:05Z",
        preflight=_preflight_payload(),
        halted=True,
    )

    assert validate_replay_manifest_schema(manifest) == []
    assert verify_replay_manifest_signature(manifest) is True


def test_replay_manifest_canonical_bytes_are_deterministic() -> None:
    manifest_a = build_replay_manifest_v1(
        replay_started_at="2026-03-19T00:00:00Z",
        replay_finished_at="2026-03-19T00:00:05Z",
        preflight=_preflight_payload(),
        halted=False,
    )
    manifest_b = build_replay_manifest_v1(
        replay_started_at="2026-03-19T00:00:00Z",
        replay_finished_at="2026-03-19T00:00:05Z",
        preflight=_preflight_payload(),
        halted=False,
    )

    assert canonical_replay_manifest_bytes(manifest_a) == canonical_replay_manifest_bytes(manifest_b)


def test_replay_manifest_filename_stable_for_equivalent_payload() -> None:
    manifest = build_replay_manifest_v1(
        replay_started_at="2026-03-19T00:00:00Z",
        replay_finished_at="2026-03-19T00:00:05Z",
        preflight=_preflight_payload(),
        halted=False,
    )

    assert replay_manifest_filename(manifest) == replay_manifest_filename(dict(manifest))


def test_replay_manifest_signature_detects_tampering() -> None:
    manifest = build_replay_manifest_v1(
        replay_started_at="2026-03-19T00:00:00Z",
        replay_finished_at="2026-03-19T00:00:05Z",
        preflight=_preflight_payload(),
        halted=True,
    )
    tampered = json.loads(json.dumps(manifest))
    tampered["divergence"]["halted"] = False

    assert verify_replay_manifest_signature(manifest) is True
    assert verify_replay_manifest_signature(tampered) is False


def test_write_replay_manifest_uses_deterministic_filename(tmp_path) -> None:
    manifest = build_replay_manifest_v1(
        replay_started_at="2026-03-19T00:00:00Z",
        replay_finished_at="2026-03-19T00:00:05Z",
        preflight=_preflight_payload(),
        halted=False,
    )

    path = write_replay_manifest_v1(manifest, manifests_dir=tmp_path)

    assert path.name == replay_manifest_filename(manifest)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["lineage_chain"] == sorted(
        payload["lineage_chain"],
        key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
    )
