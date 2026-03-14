# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import time

import pytest

from security import cryovant
from security.identity_rings import build_ring_token


@pytest.fixture
def signed_token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", "ring-test-secret")
    return cryovant.sign_governance_token(
        key_id="ring-key",
        expires_at=int(time.time()) + 3600,
        nonce="ring-nonce",
    )


def _ring_payload(ring: str, subject_id: str, claims: dict[str, str]) -> dict[str, object]:
    token = build_ring_token(ring=ring, subject_id=subject_id, claims=claims)
    return {"subject_id": subject_id, "claims": claims, "digest": token.digest}


def test_verify_identity_rings_success_all_rings() -> None:
    payload = {
        "device": _ring_payload("device", "dev-1", {"device_id": "dev-1", "device_key_id": "k-1"}),
        "agent": _ring_payload("agent", "agent-1", {"agent_id": "agent-1", "agent_version": "1.2.3"}),
        "human": _ring_payload("human", "human-1", {"human_id": "human-1", "human_role": "governor"}),
        "federation": _ring_payload(
            "federation",
            "fed-1",
            {"federation_id": "fed-1", "source_repo": "repo-A", "target_repo": "repo-B"},
        ),
    }
    assert cryovant.verify_identity_rings(payload, operation="unit", expected_federation_origin="repo-A") is True


def test_verify_identity_rings_missing_or_invalid_claims_fail_closed() -> None:
    payload = {
        "device": {
            "subject_id": "dev-1",
            "claims": {"device_id": "dev-1"},
            "digest": "deadbeef",
        }
    }
    assert cryovant.verify_identity_rings(payload, operation="unit") is False


def test_verify_identity_rings_federation_mismatch_fail_closed() -> None:
    payload = {
        "federation": _ring_payload(
            "federation",
            "fed-1",
            {"federation_id": "fed-1", "source_repo": "repo-A", "target_repo": "repo-B"},
        )
    }
    assert cryovant.verify_identity_rings(payload, operation="unit", expected_federation_origin="repo-Z") is False


def test_verify_identity_rings_malformed_payload_fail_closed() -> None:
    assert cryovant.verify_identity_rings("not-a-mapping", operation="unit") is False


def test_verify_governance_token_with_ring_claims(signed_token: str) -> None:
    payload = {
        "agent": _ring_payload("agent", "agent-1", {"agent_id": "agent-1", "agent_version": "1.2.3"}),
    }
    assert cryovant.verify_governance_token(
        signed_token,
        ring_claims=payload,
        operation="runtime_operation",
    ) is True


def test_verify_governance_token_rejects_malformed_ring_claims(signed_token: str) -> None:
    payload = {
        "human": {
            "subject_id": "human-1",
            "claims": {"human_id": "human-1", "human_role": ""},
            "digest": "abc",
        }
    }
    assert cryovant.verify_governance_token(
        signed_token,
        ring_claims=payload,
        operation="runtime_operation",
    ) is False
