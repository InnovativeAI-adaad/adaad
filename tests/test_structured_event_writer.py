# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json

from runtime.logging import emit_governance_diagnostic


def test_emit_governance_diagnostic_writes_schema_conformant_jsonl(monkeypatch, tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("ADAAD_AUDIT_JSONL_PATH", str(audit_path))

    emit_governance_diagnostic(
        component="runtime.test",
        event_type="governance_probe",
        correlation_id="corr-123",
        severity="warning",
        invariant="PHASE6-STORM-0",
        gate="tier0_schema",
        payload={"detail": "ok"},
    )

    record = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert set(record.keys()) == {
        "timestamp",
        "component",
        "event_type",
        "correlation_id",
        "severity",
        "governance_context",
        "payload",
    }
    assert record["component"] == "runtime.test"
    assert record["event_type"] == "governance_probe"
    assert record["correlation_id"] == "corr-123"
    assert record["severity"] == "WARNING"
    assert record["governance_context"] == {"invariant": "PHASE6-STORM-0", "gate": "tier0_schema"}
    assert record["payload"] == {"detail": "ok"}


def test_emit_governance_diagnostic_redacts_sensitive_fields(monkeypatch, tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("ADAAD_AUDIT_JSONL_PATH", str(audit_path))

    emit_governance_diagnostic(
        component="runtime.test",
        event_type="redaction_probe",
        correlation_id="corr-456",
        payload={
            "token": "secret-token",
            "nested": {"api_key": "abc123", "safe": "value"},
            "items": [{"authorization": "Bearer x"}],
        },
    )

    record = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert record["payload"]["token"] == "[REDACTED]"
    assert record["payload"]["nested"]["api_key"] == "[REDACTED]"
    assert record["payload"]["nested"]["safe"] == "value"
    assert record["payload"]["items"][0]["authorization"] == "[REDACTED]"
