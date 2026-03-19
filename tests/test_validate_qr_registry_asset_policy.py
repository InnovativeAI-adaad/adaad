# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression_standard


def _run_validator(registry_path: Path) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_qr_registry.py", "--registry", str(registry_path), "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_qr_registry_validator_reports_missing_asset_hash_with_rule_and_file(tmp_path: Path) -> None:
    svg_path = Path("docs/assets/qr/missing_hash.svg")
    svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0"/></svg>', encoding="utf-8")
    try:
        registry = {
            "approved_query_params": ["utm_source", "utm_medium", "utm_campaign"],
            "managed_redirect_prefixes": [],
            "targets": [
                {
                    "id": "missing-hash",
                    "active": True,
                    "placement": "install_card",
                    "asset_path": "docs/assets/qr/missing_hash.svg",
                    "target_url": "https://example.com/?utm_source=qr&utm_medium=install_card&utm_campaign=install_tracks_2026q2",
                }
            ],
        }
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")

        returncode, payload = _run_validator(registry_path)
        assert returncode != 0
        findings = payload["findings"]
        details = "\n".join(str(item["detail"]) for item in findings)
        assert "docs/assets/qr/missing_hash.svg" in details
        assert "rule: required_asset_integrity_hash" in details
    finally:
        svg_path.unlink(missing_ok=True)


def test_qr_registry_validator_rejects_svg_script_elements(tmp_path: Path) -> None:
    svg_path = Path("docs/assets/qr/svg_script.svg")
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><path d="M0,0"/></svg>',
        encoding="utf-8",
    )
    try:
        registry = {
            "approved_query_params": ["utm_source", "utm_medium", "utm_campaign"],
            "managed_redirect_prefixes": [],
            "targets": [
                {
                    "id": "svg-script",
                    "active": True,
                    "placement": "install_card",
                    "asset_path": "docs/assets/qr/svg_script.svg",
                    "asset_sha256": "sha256:" + ("0" * 64),
                    "target_url": "https://example.com/?utm_source=qr&utm_medium=install_card&utm_campaign=install_tracks_2026q2",
                }
            ],
        }
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")

        returncode, payload = _run_validator(registry_path)
        assert returncode != 0
        kinds = {item["kind"] for item in payload["findings"]}
        assert "svg_disallowed_tag" in kinds
    finally:
        svg_path.unlink(missing_ok=True)
