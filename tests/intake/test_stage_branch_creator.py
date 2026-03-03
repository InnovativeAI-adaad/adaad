from __future__ import annotations

from runtime.intake.stage_branch_creator import build_stage_branch_name


def test_build_stage_branch_name_sanitizes_values() -> None:
    branch_name = build_stage_branch_name("feature/new api", "ticket#42")

    assert branch_name == "stage/intake/feature-new-api/ticket-42"
