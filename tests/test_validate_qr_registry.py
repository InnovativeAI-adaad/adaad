# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression_standard


def test_qr_registry_validator_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_qr_registry.py", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["findings"] == []


def test_qr_registry_validator_rejects_missing_utm_campaign(tmp_path: Path) -> None:
    registry = {
        "approved_query_params": ["utm_source", "utm_medium", "utm_campaign"],
        "managed_redirect_prefixes": ["https://innovativeai-adaad.github.io/ADAAD/r/"],
        "targets": [
            {
                "id": "broken",
                "active": True,
                "placement": "install_card",
                "asset_path": "docs/assets/qr/releases_install_card.svg",
                "target_url": "https://github.com/InnovativeAI-adaad/ADAAD/releases/latest?utm_source=qr&utm_medium=install_card",
            }
        ],
    }
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "scripts/validate_qr_registry.py", "--registry", str(registry_path), "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    kinds = {finding["kind"] for finding in payload["findings"]}
    assert "invalid_required_utm" in kinds
