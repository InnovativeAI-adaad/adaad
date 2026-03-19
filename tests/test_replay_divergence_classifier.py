# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from runtime.evolution.replay_divergence import REPLAY_DIVERGENCE_REASON_CODES, classify_replay_divergence

pytestmark = pytest.mark.regression_standard


def test_classifier_missing_evidence() -> None:
    classified = classify_replay_divergence({"epoch_id": "epoch-1", "missing_evidence": True, "passed": False})
    assert classified["reason_code"] == "missing_evidence"


def test_classifier_hash_mismatch() -> None:
    classified = classify_replay_divergence(
        {"epoch_id": "epoch-1", "expected_digest": "sha256:a", "actual_digest": "sha256:b", "passed": False}
    )
    assert classified["reason_code"] == "hash_mismatch"


def test_classifier_signature_mismatch() -> None:
    classified = classify_replay_divergence({"epoch_id": "epoch-1", "signature_valid": False, "passed": False})
    assert classified["reason_code"] == "signature_mismatch"


def test_classifier_nondeterministic_field_detected() -> None:
    classified = classify_replay_divergence(
        {"epoch_id": "epoch-1", "nondeterministic_fields": ["timestamp"], "passed": False}
    )
    assert classified["reason_code"] == "nondeterministic_field_detected"


def test_classifier_lineage_discontinuity() -> None:
    classified = classify_replay_divergence(
        {"epoch_id": "epoch-1", "lineage_discontinuity": True, "expected_digest": "", "actual_digest": "", "passed": False}
    )
    assert classified["reason_code"] == "lineage_discontinuity"


def test_classifier_reconstructed_state_mismatch() -> None:
    classified = classify_replay_divergence(
        {"epoch_id": "epoch-1", "reconstructed_state_match": False, "expected_digest": "", "actual_digest": "", "passed": False}
    )
    assert classified["reason_code"] == "reconstructed_state_mismatch"


def test_reason_code_registry_contains_all_supported_codes() -> None:
    assert REPLAY_DIVERGENCE_REASON_CODES == (
        "missing_evidence",
        "hash_mismatch",
        "signature_mismatch",
        "nondeterministic_field_detected",
        "lineage_discontinuity",
        "reconstructed_state_mismatch",
    )
