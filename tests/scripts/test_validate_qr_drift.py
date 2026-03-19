# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import validate_qr_drift

pytestmark = pytest.mark.regression_standard


def test_normalize_query_map_is_deterministic_for_order_duplicates_and_encoding() -> None:
    query_url = (
        "https://example.com/?b=2&a=1&a=3&empty=&encoded=hello%20world&plus=hello+world"
    )

    parsed = validate_qr_drift._normalize_query_map(query_url)

    assert parsed == {
        "a": ["1", "3"],
        "b": ["2"],
        "empty": [""],
        "encoded": ["hello world"],
        "plus": ["hello world"],
    }


def test_validate_qr_drift_reports_expected_and_observed_mismatch_fields() -> None:
    ok, report = validate_qr_drift.validate_qr_drift(
        Path("tests/fixtures/qr_drift/registry_mismatch.json"),
        check_reachability=False,
    )

    assert ok is False
    finding_kinds = {finding["kind"] for finding in report["findings"]}
    assert "query_param_mismatch" in finding_kinds

    mismatch = next(f for f in report["findings"] if f["kind"] == "query_param_mismatch")
    assert mismatch["asset_id"] == "asset-mismatch"
    assert mismatch["expected_params"] == {
        "utm_campaign": ["install_tracks_2026q2"],
        "utm_medium": ["install_card"],
        "utm_source": ["qr"],
    }
    assert mismatch["observed_params"] == {
        "utm_campaign": ["install_tracks_2026q2"],
        "utm_medium": ["wrong_medium"],
        "utm_source": ["qr"],
        "z": ["1"],
    }


def test_validate_qr_drift_cli_json_with_deterministic_fixture_passes() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_qr_drift.py",
            "--registry",
            "tests/fixtures/qr_drift/registry_ok.json",
            "--skip-reachability",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["findings"] == []


def test_validate_qr_drift_unreachable_can_be_non_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        validate_qr_drift,
        "_check_url",
        lambda _url, _timeout: (None, "URLError: blocked"),
    )

    ok, report = validate_qr_drift.validate_qr_drift(
        Path("tests/fixtures/qr_drift/registry_ok.json"),
        check_reachability=True,
        fail_on_unreachable=False,
    )

    assert ok is True
    assert any(finding["kind"] == "unreachable_url" for finding in report["findings"])
