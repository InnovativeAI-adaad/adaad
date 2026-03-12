# SPDX-License-Identifier: Apache-2.0

# ADAAD-LANE: governance-signals

from pathlib import Path
import pytest
from adaad.agents.mutation_request import MutationRequest, MutationTarget
from runtime import constitution
pytestmark = pytest.mark.governance_gate

def _write_policy(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
def test_reload_logs_amendment_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_hash = constitution.POLICY_HASH
    policy_path = tmp_path / "constitution.yaml"
    _write_policy(policy_path, constitution.POLICY_PATH.read_text(encoding="utf-8"))

    writes = []
    txs = []

    def _capture_write_entry(agent_id: str, action: str, payload: dict | None = None) -> None:
        writes.append({"agent_id": agent_id, "action": action, "payload": payload or {}})

    def _capture_append_tx(tx_type: str, payload: dict, tx_id: str | None = None) -> dict:
        txs.append({"tx_type": tx_type, "payload": payload, "tx_id": tx_id})
        return {"hash": "captured"}

    monkeypatch.setattr(constitution.journal, "write_entry", _capture_write_entry)
    monkeypatch.setattr(constitution.journal, "append_tx", _capture_append_tx)

    updated_text = constitution.POLICY_PATH.read_text(encoding="utf-8").replace(
        '"SANDBOX": "advisory"', '"SANDBOX": "warning"', 1
    )
    _write_policy(policy_path, updated_text)

    new_hash = constitution.reload_constitution_policy(path=policy_path)

    assert new_hash != original_hash
    assert writes
    assert txs
    payload = writes[-1]["payload"]
    assert payload["old_policy_hash"] == original_hash
    assert payload["new_policy_hash"] == new_hash
    assert payload["version"] == constitution.CONSTITUTION_VERSION

    restored_hash = constitution.reload_constitution_policy(path=constitution.POLICY_PATH)
    assert restored_hash == original_hash
def test_evaluate_mutation_emits_applicability_matrix() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="docs",
        ops=[],
        signature="",
        nonce="n",
    )
    verdict = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)
    assert "applicability_matrix" in verdict
    assert verdict["applicability_matrix"]
    by_rule = {row["rule"]: row for row in verdict["applicability_matrix"]}
    assert by_rule["single_file_scope"]["applicable"] is False
    assert by_rule["signature_required"]["applicable"] is False
def test_resource_bounds_violation_emits_metrics_and_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    validator = constitution.VALIDATOR_REGISTRY["resource_bounds"]
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="",
        nonce="n",
    )
    monkeypatch.setenv("ADAAD_RESOURCE_MEMORY_MB", "10")
    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    monkeypatch.setenv("ADAAD_RESOURCE_CPU_SECONDS", "1")
    monkeypatch.setenv("ADAAD_RESOURCE_WALL_SECONDS", "1")

    metric_events = []
    journal_events = []
    ledger_events = []

    def _capture_metric(*, event_type: str, payload: dict, level: str = "INFO", element_id: str | None = None) -> None:
        metric_events.append({"event_type": event_type, "payload": payload, "level": level, "element_id": element_id})

    def _capture_journal(agent_id: str, action: str, payload: dict | None = None) -> None:
        journal_events.append({"agent_id": agent_id, "action": action, "payload": payload or {}})

    def _capture_tx(tx_type: str, payload: dict, tx_id: str | None = None) -> dict:
        ledger_events.append({"tx_type": tx_type, "payload": payload, "tx_id": tx_id})
        return {"hash": "captured"}

    monkeypatch.setattr(constitution.metrics, "log", _capture_metric)
    monkeypatch.setattr(constitution.journal, "write_entry", _capture_journal)
    monkeypatch.setattr(constitution.journal, "append_tx", _capture_tx)

    with constitution.deterministic_envelope_scope(
        {
            "agent_id": request.agent_id,
            "epoch_id": "epoch-2",
            "resource_measurements": {"peak_rss_mb": 11.0, "cpu_seconds": 2.0, "wall_seconds": 2.0},
        }
    ):
        result = validator(request)

    assert result["ok"] is False
    assert metric_events and metric_events[-1]["event_type"] == "resource_bounds_exceeded"
    assert journal_events and journal_events[-1]["action"] == "resource_bounds_exceeded"
    assert ledger_events and ledger_events[-1]["tx_type"] == "resource_bounds_exceeded"
def test_governance_rejection_event_contains_resource_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[{"op": "replace", "path": "runtime/constitution.py", "value": "x"}],
        signature="cryovant-dev-test",
        nonce="n",
        targets=[MutationTarget(agent_id="test_subject", path="runtime/constitution.py", target_type="file", ops=[])],
    )
    monkeypatch.setenv("ADAAD_RESOURCE_MEMORY_MB", "10")

    metric_events = []
    journal_events = []
    ledger_events = []

    monkeypatch.setattr(
        constitution.metrics,
        "log",
        lambda *, event_type, payload, level="INFO", element_id=None: metric_events.append(
            {"event_type": event_type, "payload": payload, "level": level}
        ),
    )
    monkeypatch.setattr(
        constitution.journal,
        "write_entry",
        lambda agent_id, action, payload=None: journal_events.append(
            {"agent_id": agent_id, "action": action, "payload": payload or {}}
        ),
    )
    monkeypatch.setattr(
        constitution.journal,
        "append_tx",
        lambda tx_type, payload, tx_id=None: ledger_events.append(
            {"tx_type": tx_type, "payload": payload, "tx_id": tx_id}
        ) or {"hash": "captured"},
    )

    with constitution.deterministic_envelope_scope(
        {
            "agent_id": request.agent_id,
            "epoch_id": "epoch-rj",
            "resource_measurements": {"peak_rss_mb": 64.0, "cpu_seconds": 1.0, "wall_seconds": 1.0},
        }
    ):
        verdict = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)

    assert verdict["passed"] is False
    rejection_metric = next(item for item in metric_events if item["event_type"] == "governance_rejection")
    assert rejection_metric["payload"]["resource_usage_snapshot"]["memory_mb"] == 64.0
    assert rejection_metric["payload"]["bounds_policy_version"] == "1.0.0"
    assert journal_events[-1]["action"] == "governance_rejection"
    assert ledger_events[-1]["tx_type"] == "governance_rejection"
def test_verdicts_include_validator_provenance() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="",
        nonce="n",
    )
    verdict = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)
    row = next(item for item in verdict["verdicts"] if item["rule"] == "lineage_continuity")
    provenance = row["provenance"]
    assert provenance["constitution_version"] == constitution.CONSTITUTION_VERSION
    assert provenance["validator_name"]
    assert len(provenance["validator_source_hash"]) == 64
def test_evaluate_mutation_emits_domain_ceiling_ledger_event(monkeypatch: pytest.MonkeyPatch) -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="cryovant-dev-test",
        nonce="n",
        epoch_id="epoch-domain-1",
        targets=[MutationTarget(agent_id="test_subject", path="security/policy.py", target_type="file", ops=[])],
    )
    ledger_writes = []
    ledger_txs = []

    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    monkeypatch.setenv("ADAAD_MAX_MUTATION_RATE", "10")
    monkeypatch.setattr(constitution, "_deterministic_mutation_count", lambda window_sec, epoch_id: {
        "window_sec": window_sec,
        "window_start_ts": 0.0,
        "window_end_ts": 0.0,
        "count": 1,
        "rate_per_hour": 1.0,
        "event_types": [],
        "entries_considered": 0,
        "entries_scoped": 0,
        "scope": {"epoch_id": "*"},
        "source": "test",
    })

    monkeypatch.setattr(constitution.journal, "write_entry", lambda agent_id, action, payload=None: ledger_writes.append({"agent_id": agent_id, "action": action, "payload": payload or {}}))
    monkeypatch.setattr(constitution.journal, "append_tx", lambda tx_type, payload, tx_id=None: ledger_txs.append({"tx_type": tx_type, "payload": payload}))

    verdict = constitution.evaluate_mutation(request, constitution.Tier.STABLE)

    assert verdict["resolved_domain"] == "security"
    assert ledger_writes
    event = next(item for item in ledger_writes if item["action"] == "constitutional_evaluation_domain_ceiling")
    assert event["payload"]["resolved_domain"] == "security"
    assert any(item["rule"] == "max_mutation_rate" and item["applied_ceiling"] == 4.0 for item in event["payload"]["applied_ceilings"])
    assert any(item["tx_type"] == "constitutional_evaluation_domain_ceiling" for item in ledger_txs)
def test_resource_bounds_logs_warning_when_policy_document_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    validator = constitution.VALIDATOR_REGISTRY["resource_bounds"]
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="",
        nonce="n",
    )
    events = []
    monkeypatch.setattr(
        constitution.metrics,
        "log",
        lambda *, event_type, payload, level="INFO", element_id=None: events.append(
            {"event_type": event_type, "payload": payload, "level": level, "element_id": element_id}
        ),
    )
    monkeypatch.setattr(constitution, "_POLICY_DOCUMENT", {})

    with constitution.deterministic_envelope_scope({"resource_measurements": {"peak_rss_mb": 1.0}}):
        result = validator(request)

    assert result["ok"] is True
    warning = next(item for item in events if item["event_type"] == "resource_bounds_policy_unavailable")
    assert warning["level"] == "WARNING"
