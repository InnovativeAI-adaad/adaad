import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0
import hashlib
import hmac

from runtime.governance.foundation import canonical_json
from runtime.sandbox.evidence import sign_bundle, verify_bundle_signature
from runtime.sandbox.fs_rules import enforce_write_path_allowlist


def test_write_rules_block_outside_workspace():
    ok, violations = enforce_write_path_allowlist(("/etc/passwd",), ("/workspace",))
    assert ok is False
    assert violations


def test_evidence_bundle_signing_is_deterministic(monkeypatch):
    monkeypatch.setenv("ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY", "test-evidence-key")
    payload = {"a": 1, "z": ["x"], "nested": {"b": "2"}}

    signed = sign_bundle(payload, metadata={"k": "v"})
    expected_payload = dict(payload)
    expected_payload["signature_metadata"] = {"k": "v"}
    expected_hmac = hmac.new(
        b"test-evidence-key",
        canonical_json(expected_payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert signed["signed_digest"] == f"sha256:{expected_hmac}"
    assert verify_bundle_signature(signed) is True
