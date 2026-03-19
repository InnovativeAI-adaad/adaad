import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from scripts import validate_docs_integrity as validator


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_svg_asset_file_accepts_relative_href(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svg_file = tmp_path / "docs/assets/platforms.svg"
    _write(svg_file, '<svg><image href="qr/fdroid.svg"/></svg>\n')
    _write(tmp_path / "docs/assets/qr/fdroid.svg", "<svg/>\n")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    findings = validator._scan_svg_asset_file(svg_file)

    assert findings == []


def test_scan_svg_asset_file_flags_bad_docs_assets_prefixed_href(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svg_file = tmp_path / "docs/assets/platforms.svg"
    _write(svg_file, '<svg><image href="docs/assets/qr/fdroid.svg"/></svg>\n')
    _write(tmp_path / "docs/assets/qr/fdroid.svg", "<svg/>\n")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    findings = validator._scan_svg_asset_file(svg_file)

    kinds = {finding["kind"] for finding in findings}
    assert "bad_svg_intra_asset_href_path" in kinds
    assert "missing_local_target" in kinds
    assert all(finding["target"] == "docs/assets/qr/fdroid.svg" for finding in findings)


def test_collect_findings_detects_bad_svg_asset_path_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path / "README.md", "![banner](docs/assets/platforms.svg)\n")
    _write(tmp_path / "docs/assets/platforms.svg", '<svg><image href="docs/assets/qr/fdroid.svg"/></svg>\n')
    _write(tmp_path / "docs/assets/qr/fdroid.svg", "<svg/>\n")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    findings = validator._collect_findings(roots=["README.md"])

    assert any(
        finding["kind"] == "bad_svg_intra_asset_href_path"
        and finding["file"] == "docs/assets/platforms.svg"
        for finding in findings
    )
