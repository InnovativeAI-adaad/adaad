# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adaad.orchestrator.status import build_status_report, render_human_table


@pytest.fixture()
def repo_fixture(tmp_path: Path) -> Path:
    (tmp_path / "docs/governance").mkdir(parents=True)
    (tmp_path / "docs/comms").mkdir(parents=True)

    (tmp_path / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md").write_text(
        """
adaad_pr_procession_contract:
  state_alignment:
    expected_next_pr: "PR-PHASE65-01 (Phase 65 — First Autonomous Capability Evolution)"

| Phase | Version | Depends on | Status |
|---|---|---|---|
| 64 | v8.7.0 | Phase 63 | shipped |
| 65 | v9.0.0 | Phase 64 | next |
""".strip()
        + "\n",
        encoding="utf-8",
    )

    (tmp_path / ".adaad_agent_state.json").write_text(
        json.dumps(
            {
                "blocked_reason": None,
                "last_gate_results": {
                    "tier_0": "pass",
                    "tier_1": "pass",
                    "tier_2": "fail",
                    "tier_3": "pass",
                },
            }
        ),
        encoding="utf-8",
    )

    (tmp_path / "docs/comms/claims_evidence_matrix.md").write_text(
        """
| Claim ID | Claim | Evidence | Scope | Status |
|---|---|---|---|---|
| `claim-complete` | done | ref | f | Complete |
| `claim-pending` | waiting | ref | f | Pending |
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


def test_build_status_report_aggregates_expected_fields(repo_fixture: Path) -> None:
    report = build_status_report(repo_root=repo_fixture, trigger_mode="DEVADAAD")

    assert report.schema_version == "adaad_status.v1"
    assert report.trigger_mode == "DEVADAAD"
    assert report.next_pr.startswith("PR-PHASE65-01")
    assert report.dependency_readiness.ready is True
    assert report.tiers == {
        "tier_0": "pass",
        "tier_1": "pass",
        "tier_2": "fail",
        "tier_3": "pass",
        "tier_m": "unknown",
    }
    assert report.pending_evidence_rows == ["claim-pending"]


def test_build_status_report_fails_when_procession_missing_next_pr(repo_fixture: Path) -> None:
    (repo_fixture / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md").write_text(
        "# no contract block\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="procession_contract_missing_expected_next_pr"):
        build_status_report(repo_root=repo_fixture, trigger_mode="ADAAD")


def test_render_human_table_marks_blocked_when_dependencies_not_ready(repo_fixture: Path) -> None:
    (repo_fixture / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md").write_text(
        """
adaad_pr_procession_contract:
  state_alignment:
    expected_next_pr: "PR-PHASE65-01 (Phase 65 — First Autonomous Capability Evolution)"

| Phase | Version | Depends on | Status |
|---|---|---|---|
| 64 | v8.7.0 | Phase 63 | pending |
| 65 | v9.0.0 | Phase 64 | next |
""".strip()
        + "\n",
        encoding="utf-8",
    )

    report = build_status_report(repo_root=repo_fixture, trigger_mode="ADAAD")
    table = render_human_table(report)

    assert report.dependency_readiness.ready is False
    assert "Dependency readiness : BLOCKED" in table
    assert "Unmet dependencies" in table
