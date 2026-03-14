# SPDX-License-Identifier: Apache-2.0
import json

import pytest

from runtime.mcp.rejection_explainer import explain_rejection
from security.ledger import journal

pytestmark = pytest.mark.regression_standard


@pytest.fixture(autouse=True)
def _isolated_lineage_ledger(tmp_path, monkeypatch: pytest.MonkeyPatch):
    ledger_root = tmp_path / "ledger"
    monkeypatch.setattr(journal, "LEDGER_ROOT", ledger_root)
    monkeypatch.setattr(journal, "LEDGER_FILE", ledger_root / "lineage.jsonl")


def test_unknown_mutation_id_404_semantics():
    with pytest.raises(KeyError, match="mutation_not_found"):
        explain_rejection("missing")


def test_explainer_returns_steps_for_failure():
    mutation_id = "m-1"
    journal.write_entry(
        agent_id="a",
        action="mutation_lifecycle_rejected",
        payload={"mutation_id": mutation_id, "guard_report": {"fitness_threshold_gate": {"ok": False}}},
    )
    out = explain_rejection(mutation_id)
    assert out["gate_failures"]
    assert out["gate_failures"][0]["remediation_steps"]


def test_explainer_uses_latest_matching_record_without_read_entries(monkeypatch: pytest.MonkeyPatch):
    mutation_id = "m-2"
    journal.write_entry(
        agent_id="a",
        action="mutation_lifecycle_rejected",
        payload={"mutation_id": mutation_id, "guard_report": {"fitness_threshold_gate": {"ok": False}}},
    )
    journal.write_entry(
        agent_id="a",
        action="mutation_lifecycle_rejected",
        payload={"mutation_id": mutation_id, "guard_report": {"cert_reference_gate": {"ok": False}}},
    )

    monkeypatch.setattr(journal, "read_entries", lambda *args, **kwargs: pytest.fail("read_entries should not be used"))

    out = explain_rejection(mutation_id)
    assert out["gate_failures"][0]["gate"] == "cert_reference_gate"


def test_filtered_read_helper_is_bounded_and_does_not_materialize_full_file(monkeypatch: pytest.MonkeyPatch):
    mutation_id = "m-bounded"
    journal.ensure_ledger()
    with journal.LEDGER_FILE.open("w", encoding="utf-8") as handle:
        for idx in range(200):
            payload = {"mutation_id": f"other-{idx}", "guard_report": {"fitness_threshold_gate": {"ok": False}}}
            handle.write(json.dumps({"action": "mutation_lifecycle_rejected", "payload": payload}) + "\n")
        target_payload = {"mutation_id": mutation_id, "guard_report": {"trust_mode_compatibility_gate": {"ok": False}}}
        handle.write(json.dumps({"action": "mutation_lifecycle_rejected", "payload": target_payload}) + "\n")

    class TrackingDeque(list):
        max_observed = 0

        def __init__(self, *args, maxlen: int | None = None, **kwargs):
            super().__init__(*args, **kwargs)
            self.maxlen = maxlen

        def append(self, item):
            super().append(item)
            if self.maxlen is not None and len(self) > self.maxlen:
                del self[0]
            TrackingDeque.max_observed = max(TrackingDeque.max_observed, len(self))

    monkeypatch.setattr(journal, "deque", TrackingDeque)

    entry = journal.read_latest_entry_by_action_and_mutation_id(
        action="mutation_lifecycle_rejected",
        mutation_id=mutation_id,
        limit=25,
    )

    assert entry is not None
    assert str((entry.get("payload") or {}).get("mutation_id") or "") == mutation_id
    assert TrackingDeque.max_observed <= 25
