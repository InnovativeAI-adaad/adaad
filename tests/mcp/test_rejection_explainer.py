# SPDX-License-Identifier: Apache-2.0
import pytest
pytestmark = pytest.mark.regression_standard

from runtime.mcp.rejection_explainer import explain_rejection
from security.ledger import journal


def test_unknown_mutation_id_404_semantics():
    with pytest.raises(KeyError):
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
