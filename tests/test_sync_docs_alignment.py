# SPDX-License-Identifier: Apache-2.0
import pytest

pytestmark = pytest.mark.regression_standard

from scripts import sync_docs_on_merge as sync
from scripts import validate_readme_alignment as validator


def test_replace_html_version_pill_replaces_and_audits() -> None:
    content = '<span class="version-pill">v1.2.3</span>'
    updated, changes = sync._replace_html_version_pill(content, "9.9.9")

    assert updated == '<span class="version-pill">v9.9.9</span>'
    assert changes == ["install_html_version_pill 1.2.3→9.9.9"]


def test_replace_html_version_pill_supports_single_quotes() -> None:
    content = "<span class='version-pill'>v1.2.3</span>"
    updated, changes = sync._replace_html_version_pill(content, "9.9.9")

    assert updated == "<span class='version-pill'>v9.9.9</span>"
    assert changes == ["install_html_version_pill 1.2.3→9.9.9"]


def test_replace_html_version_pill_is_idempotent_when_current() -> None:
    content = '<span class="version-pill">v9.9.9</span>'
    updated, changes = sync._replace_html_version_pill(content, "9.9.9")

    assert updated == content
    assert changes == []


def test_install_html_is_always_sync_target() -> None:
    assert "docs/install.html" in sync._ALWAYS_SYNC


def test_sync_and_validator_patterns_match_same_variants() -> None:
    variants = [
        '<span class="version-pill">v1.2.3</span>',
        "<span class='version-pill'>v1.2.3</span>",
        '<SPAN CLASS="VERSION-PILL">v1.2.3</SPAN>',
    ]

    for sample in variants:
        assert sync._HTML_VERSION_PILL_RE.search(sample)
        assert validator.INSTALL_DOC_VERSION_PATTERNS["docs/install.html"].search(sample)


def test_protected_path_logic_is_unchanged_for_install_html() -> None:
    assert not sync._is_protected("docs/install.html")
    assert sync._is_protected("docs/CONSTITUTION.md")
