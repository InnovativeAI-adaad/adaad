# SPDX-License-Identifier: Apache-2.0
"""Tests for EvidenceBundleBuilder._collect_federated_evidence — Phase 5 integration.

Coverage:
  - Empty ledger → empty verifications, invariant_ok=True
  - federated_evidence_verified events → passed=True entries
  - federated_evidence_failed events → passed=False entries
  - divergence_count increments for no_divergence:digest_mismatch failure codes
  - divergence_count increments for no_divergence axis failures
  - invariant_ok=False when divergence_count > 0
  - Only events for in-scope epoch_ids are collected
  - results sorted by (epoch_id, proposal_id)
  - federated_evidence present in _build_core output (integration)
  - schema_version field present
"""

from __future__ import annotations

import pytest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Minimal stubs so we can instantiate EvidenceBundleBuilder without full FS
# ---------------------------------------------------------------------------
def _make_ledger(events_by_epoch: Dict[str, List[Dict]] = None) -> MagicMock:
    """Create a mock LineageLedgerV2 with controllable read_epoch output."""
    ledger = MagicMock()
    ledger.read_epoch.side_effect = lambda epoch_id: list(
        (events_by_epoch or {}).get(epoch_id, [])
    )
    ledger.list_epoch_ids.return_value = list((events_by_epoch or {}).keys())
    ledger.get_expected_epoch_digest.return_value = "sha256:" + "0" * 64
    ledger.compute_incremental_epoch_digest.return_value = "sha256:" + "0" * 64
    return ledger


def _make_event(
    event_type: str,
    proposal_id: str = "prop-001",
    passed: bool = True,
    failure_codes: List[str] = None,
    axes: List = None,
    matrix_digest: str = "",
) -> Dict[str, Any]:
    return {
        "type": event_type,
        "payload": {
            "proposal_id": proposal_id,
            "passed": passed,
            "failure_codes": failure_codes or [],
            "axes": axes or [],
            "matrix_digest": matrix_digest or ("sha256:" + "a" * 64),
        },
    }


def _builder_with_ledger(ledger) -> Any:
    """Instantiate EvidenceBundleBuilder with a mock ledger, patching heavy deps."""
    from runtime.evolution.evidence_bundle import EvidenceBundleBuilder
    builder = object.__new__(EvidenceBundleBuilder)
    builder.ledger = ledger
    return builder


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestCollectFederatedEvidence:
    def test_empty_ledger_returns_empty_verifications(self):
        ledger = _make_ledger({"epoch-1": []})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["verification_count"] == 0
        assert result["verifications"] == []
        assert result["invariant_ok"] is True

    def test_schema_version_present(self):
        ledger = _make_ledger({"epoch-1": []})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["schema_version"] == "federated_evidence.v1"

    def test_epoch_ids_in_output(self):
        ledger = _make_ledger({"epoch-1": [], "epoch-2": []})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1", "epoch-2"])

        assert "epoch-1" in result["epoch_ids"]
        assert "epoch-2" in result["epoch_ids"]

    def test_verified_event_produces_passed_entry(self):
        event = _make_event("federated_evidence_verified", proposal_id="prop-001", passed=True)
        ledger = _make_ledger({"epoch-1": [event]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["verification_count"] == 1
        assert result["passed_count"] == 1
        assert result["failed_count"] == 0
        v = result["verifications"][0]
        assert v["passed"] is True
        assert v["proposal_id"] == "prop-001"

    def test_failed_event_produces_failed_entry(self):
        event = _make_event(
            "federated_evidence_failed",
            proposal_id="prop-002",
            passed=False,
            failure_codes=["destination_registered:epoch_not_found"],
        )
        ledger = _make_ledger({"epoch-1": [event]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["failed_count"] == 1
        v = result["verifications"][0]
        assert v["passed"] is False

    def test_divergence_count_increments_on_failure_code(self):
        event = _make_event(
            "federated_evidence_failed",
            proposal_id="prop-div",
            passed=False,
            failure_codes=["no_divergence:digest_mismatch"],
        )
        ledger = _make_ledger({"epoch-1": [event]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["divergence_count"] == 1
        assert result["invariant_ok"] is False

    def test_divergence_count_increments_on_axis_object(self):
        axes = [{"axis": "no_divergence", "ok": False, "reason": "digest_mismatch"}]
        event = _make_event(
            "federated_evidence_failed",
            proposal_id="prop-div2",
            passed=False,
            axes=axes,
        )
        ledger = _make_ledger({"epoch-1": [event]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["divergence_count"] == 1
        assert result["invariant_ok"] is False

    def test_invariant_ok_true_when_no_divergences(self):
        event = _make_event("federated_evidence_verified", passed=True)
        ledger = _make_ledger({"epoch-1": [event]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["divergence_count"] == 0
        assert result["invariant_ok"] is True

    def test_multiple_epochs_collected(self):
        e1 = _make_event("federated_evidence_verified", proposal_id="prop-e1")
        e2 = _make_event("federated_evidence_verified", proposal_id="prop-e2")
        ledger = _make_ledger({"epoch-1": [e1], "epoch-2": [e2]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1", "epoch-2"])

        assert result["verification_count"] == 2

    def test_only_in_scope_epochs_collected(self):
        e1 = _make_event("federated_evidence_verified", proposal_id="prop-in")
        e_out = _make_event("federated_evidence_verified", proposal_id="prop-out")
        ledger = _make_ledger({"epoch-in": [e1], "epoch-out": [e_out]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-in"])

        assert result["verification_count"] == 1
        assert result["verifications"][0]["proposal_id"] == "prop-in"

    def test_non_federation_events_ignored(self):
        good = _make_event("federated_evidence_verified", proposal_id="prop-good")
        noise = {"type": "ReplayVerificationEvent", "payload": {"epoch_id": "epoch-1"}}
        ledger = _make_ledger({"epoch-1": [good, noise]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["verification_count"] == 1

    def test_results_sorted_by_epoch_and_proposal_id(self):
        events = [
            _make_event("federated_evidence_verified", proposal_id="prop-z"),
            _make_event("federated_evidence_verified", proposal_id="prop-a"),
        ]
        ledger = _make_ledger({"epoch-1": events})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        pids = [v["proposal_id"] for v in result["verifications"]]
        assert pids == sorted(pids)

    def test_multiple_divergences_counted(self):
        div1 = _make_event("federated_evidence_failed", "p1", False, ["no_divergence:digest_mismatch"])
        div2 = _make_event("federated_evidence_failed", "p2", False, ["no_divergence:digest_mismatch"])
        ledger = _make_ledger({"epoch-1": [div1, div2]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        assert result["divergence_count"] == 2
        assert result["invariant_ok"] is False

    def test_has_divergence_flag_set_per_result(self):
        div = _make_event("federated_evidence_failed", "p1", False, ["no_divergence:digest_mismatch"])
        ok = _make_event("federated_evidence_verified", "p2", True)
        ledger = _make_ledger({"epoch-1": [div, ok]})
        builder = _builder_with_ledger(ledger)

        result = builder._collect_federated_evidence(["epoch-1"])

        by_id = {v["proposal_id"]: v for v in result["verifications"]}
        assert by_id["p1"]["has_divergence"] is True
        assert by_id["p2"]["has_divergence"] is False


class TestBuildCoreIncludesFederatedEvidence:
    """Integration test: _build_core output contains federated_evidence key."""

    def test_build_core_has_federated_evidence_key(self, tmp_path):
        """Verify federated_evidence is present in the _build_core return dict."""
        from runtime.evolution.evidence_bundle import EvidenceBundleBuilder
        from runtime.evolution.lineage_v2 import LineageLedgerV2

        ledger_path = tmp_path / "ledger.jsonl"
        ledger = LineageLedgerV2(ledger_path)
        # Seed a minimal epoch
        ledger.append_event("EpochStartEvent", {"epoch_id": "test-epoch-1"})

        builder = EvidenceBundleBuilder(
            ledger=ledger,
            sandbox_evidence_path=tmp_path / "sandbox.jsonl",
            policy_path=tmp_path / "policy.yaml",
        )
        core = builder._build_core("test-epoch-1", None)

        assert "federated_evidence" in core
        fed = core["federated_evidence"]
        assert fed["schema_version"] == "federated_evidence.v1"
        assert "invariant_ok" in fed
        assert "divergence_count" in fed
        assert "verifications" in fed
