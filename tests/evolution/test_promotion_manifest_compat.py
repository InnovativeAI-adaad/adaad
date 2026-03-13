# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

pytestmark = pytest.mark.regression_standard

from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.evolution.promotion_manifest import emit_pr_lifecycle_event


def test_emit_pr_lifecycle_event_writes_v11_and_legacy_identifier(tmp_path, monkeypatch) -> None:
    lineage_ledger_path = tmp_path / "lineage_v2.jsonl"
    monkeypatch.setattr("runtime.evolution.promotion_manifest.LEDGER_V2_PATH", lineage_ledger_path)

    event = emit_pr_lifecycle_event(
        policy_version="promotion-policy.v1",
        evaluation_result="allow",
        decision_id="decision-123",
    )

    assert event["schema_version"] == "1.1"
    assert str(event["synthetic_commit_id"]).startswith("sha256:")
    assert len(str(event["commit_sha"])) == 40

    events = LineageLedgerV2(lineage_ledger_path).read_all()
    lifecycle_payloads = [entry.get("payload") for entry in events if entry.get("type") == "PRLifecycleEvent"]
    assert any(
        isinstance(payload, dict) and payload.get("synthetic_commit_id") == event["synthetic_commit_id"]
        for payload in lifecycle_payloads
    )
