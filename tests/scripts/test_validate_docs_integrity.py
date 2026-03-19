import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from scripts import validate_docs_integrity as validator


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_install_page_assets_accepts_present_manifest_and_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path / "docs/install.html", '<link rel="manifest" href="./manifest.json"/>\n<script>navigator.serviceWorker.register("./sw.js");</script>\n<img src="/ADAAD/assets/qr/pwa.svg">\n')
    _write(tmp_path / "docs/manifest.json", "{}")
    _write(tmp_path / "docs/sw.js", "self.addEventListener('fetch', () => {});")
    _write(tmp_path / "docs/assets/qr/pwa.svg", "<svg/>")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    assert validator._scan_install_page_assets() == []


def test_scan_install_page_assets_fails_closed_for_missing_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path / "docs/install.html", '<link rel="manifest" href="./manifest.json"/>\n<script>navigator.serviceWorker.register("./sw.js");</script>\n<img src="/ADAAD/assets/qr/missing.svg">\n')

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    findings = validator._scan_install_page_assets()
    missing_targets = {entry["target"] for entry in findings if entry["kind"] == "missing_install_static_asset"}

    assert "./manifest.json" in missing_targets
    assert "./sw.js" in missing_targets
    assert "/ADAAD/assets/qr/missing.svg" in missing_targets
