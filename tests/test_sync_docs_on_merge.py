import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from scripts import sync_docs_on_merge as sync


def test_update_arch_snapshot_includes_tag_row() -> None:
    content = (
        "# Title\n\n"
        "<!-- ARCH_SNAPSHOT_METADATA:START -->\n"
        "old\n"
        "<!-- ARCH_SNAPSHOT_METADATA:END -->\n"
    )
    plan = sync.SyncPlan(
        version="3.0.0",
        prev_version="2.9.0",
        date_str="2026-03-07",
        changelog_entry="",
        new_capabilities=[],
        new_modules=[],
        shipped_phases=[],
        git_sha="deadbee",
        git_branch="main",
        git_tag="(none)",
        merged_files=[],
    )

    updated, changes = sync._update_arch_snapshot(content, plan)

    assert "| Tag | `(none)` |" in updated
    assert "| Branch | `main` |" in updated
    assert "| Short SHA | `deadbee` |" in updated
    assert changes == ["ARCH_SNAPSHOT→v3.0.0/deadbee"]
