# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from pathlib import Path

from runtime.intake.repo_scanner import scan_repository
from runtime.intake.scan_rules import ScanRules


def test_scan_repository_counts_and_flags_files(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("print('x')\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored", encoding="utf-8")
    (tmp_path / "big.bin").write_bytes(b"x" * 32)

    report = scan_repository(tmp_path, ScanRules(max_flag_file_size_bytes=16), scan_id="scan-1")

    assert report.scan_id == "scan-1"
    assert report.total_files == 2
    assert report.skipped_files == 1
    assert report.flagged_paths == ["big.bin"]
