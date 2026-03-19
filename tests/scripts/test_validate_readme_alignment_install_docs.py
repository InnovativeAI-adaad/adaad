import pytest

pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from scripts import validate_readme_alignment as validator


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_install_doc_versions_flag_outdated_hardcoded_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "VERSION", "9.12.0\n")
    _write(
        tmp_path / "INSTALL_ANDROID.md",
        "# Install\n**InnovativeAI LLC · v7.0.0 · Free · No Play Store required**\n",
    )
    _write(
        tmp_path / "docs/install.html",
        '<span class="version-pill">v3.1.0-dev · Community · Free</span>\n',
    )

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    missing: list[str] = []
    validator._validate_install_doc_version_freshness(missing=missing)

    assert "stale_install_doc_version:INSTALL_ANDROID.md:found=v7.0.0:minimum=v9.12.x" in missing
    assert "stale_install_doc_version:docs/install.html:found=v3.1.0:minimum=v9.12.x" in missing


def test_install_doc_versions_accept_version_synced_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "VERSION", "9.12.0\n")
    _write(
        tmp_path / "INSTALL_ANDROID.md",
        "# Install\n**InnovativeAI LLC · Version synced from `VERSION` during docs publish · Free · No Play Store required**\n",
    )
    _write(
        tmp_path / "docs/install.html",
        '<span class="version-pill">Version synced from /VERSION at docs publish · Community · Free</span>\n',
    )

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    missing: list[str] = []
    validator._validate_install_doc_version_freshness(missing=missing)

    assert missing == []
