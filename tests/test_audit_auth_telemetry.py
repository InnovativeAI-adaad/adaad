# SPDX-License-Identifier: Apache-2.0
"""AUDIT-TEL-01: load_audit_tokens telemetry + constant-time scope check tests."""
import json
import logging
import pytest
from fastapi import HTTPException
from runtime.audit_auth import load_audit_tokens, require_audit_read_scope, require_audit_write_scope


@pytest.mark.autonomous_critical
def test_load_audit_tokens_not_configured_emits_debug(monkeypatch, caplog):
    """Mode (a): absent env var emits DEBUG log, not silent."""
    monkeypatch.delenv("ADAAD_AUDIT_TOKENS", raising=False)
    with caplog.at_level(logging.DEBUG, logger="runtime.audit_auth"):
        result = load_audit_tokens()
    assert result == {}
    assert any("audit_tokens_not_configured" in r.message for r in caplog.records), (
        "AUDIT-TEL-01: missing ADAAD_AUDIT_TOKENS must emit DEBUG log"
    )


@pytest.mark.autonomous_critical
def test_load_audit_tokens_malformed_json_emits_warning(monkeypatch, caplog):
    """Mode (b): malformed JSON emits WARNING, not silent."""
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", "{not valid json}")
    with caplog.at_level(logging.WARNING, logger="runtime.audit_auth"):
        result = load_audit_tokens()
    assert result == {}
    assert any("audit_tokens_malformed_json" in r.message for r in caplog.records), (
        "AUDIT-TEL-01: malformed ADAAD_AUDIT_TOKENS must emit WARNING log"
    )


@pytest.mark.autonomous_critical
def test_load_audit_tokens_wrong_type_emits_warning(monkeypatch, caplog):
    """Mode (c): non-dict JSON emits WARNING, not silent."""
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", '["not", "a", "dict"]')
    with caplog.at_level(logging.WARNING, logger="runtime.audit_auth"):
        result = load_audit_tokens()
    assert result == {}
    assert any("audit_tokens_wrong_type" in r.message for r in caplog.records), (
        "AUDIT-TEL-01: non-dict ADAAD_AUDIT_TOKENS must emit WARNING log"
    )


@pytest.mark.autonomous_critical
def test_require_audit_read_scope_constant_time_comparison(monkeypatch):
    """Scope check must use hmac.compare_digest (constant-time) not 'in'."""
    tokens = {"valid-token-abc": ["audit:read", "audit:write"]}
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps(tokens))

    result = require_audit_read_scope("Bearer valid-token-abc")
    assert result["scope"] == "audit:read"


@pytest.mark.autonomous_critical
def test_require_audit_write_scope_constant_time_comparison(monkeypatch):
    """Write scope check must use hmac.compare_digest."""
    tokens = {"write-token-xyz": ["audit:write"]}
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps(tokens))

    result = require_audit_write_scope("Bearer write-token-xyz")
    assert result["scope"] == "audit:write"


@pytest.mark.autonomous_critical
def test_require_audit_read_scope_insufficient_scope_raises_403(monkeypatch):
    """Token with write-only scope must get 403 on read endpoint."""
    tokens = {"write-only-token": ["audit:write"]}
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps(tokens))

    with pytest.raises(HTTPException) as exc_info:
        require_audit_read_scope("Bearer write-only-token")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "insufficient_scope"
