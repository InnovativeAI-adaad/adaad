# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import security.cryovant as cryovant


def _read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").strip().splitlines() if line.strip()]


def test_verify_identity_rings_emits_structured_diagnostic(monkeypatch, tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("ADAAD_AUDIT_JSONL_PATH", str(audit_path))

    ok = cryovant.verify_identity_rings(
        {"federation": {"subject_id": "node-1", "claims": {"source_repo": "repo-a"}, "digest": "bad"}},
        operation="federated_apply",
        expected_federation_origin="repo-a",
    )

    assert not ok
    records = _read_records(audit_path)
    assert records
    latest = records[-1]
    assert latest["event_type"] == "cryovant_ring_verification_result"
    assert latest["component"] == "security.cryovant"
    assert latest["severity"] == "ERROR"
    assert latest["governance_context"]["gate"] == "identity_ring_validation"


def test_read_json_failure_emits_structured_error(monkeypatch, tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("ADAAD_AUDIT_JSONL_PATH", str(audit_path))

    broken = tmp_path / "broken.json"
    broken.write_text('{"bad":', encoding="utf-8")

    try:
        cryovant._read_json(broken)
    except cryovant.CriticalArtifactReadError:
        pass
    else:
        raise AssertionError("expected CriticalArtifactReadError")

    records = _read_records(audit_path)
    latest = records[-1]
    assert latest["event_type"] == "cryovant_critical_json_read_failed"
    assert latest["severity"] == "ERROR"
    assert latest["correlation_id"] == "critical_json_parse_error"
    assert latest["payload"]["error_type"] == "JSONDecodeError"
