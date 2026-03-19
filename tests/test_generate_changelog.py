# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from scripts.generate_changelog import render_changelog


def test_render_changelog_contains_expected_fields() -> None:
    content = render_changelog()

    assert content.startswith("# CHANGELOG\n")
    assert "PR ID:" in content
    assert "Lane/Tier:" in content
    assert "Evidence refs:" in content
    assert "## [9.11.0]" in content
