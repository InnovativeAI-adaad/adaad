# SPDX-License-Identifier: Apache-2.0
"""Repository scanner used by runtime intake workflows."""

from __future__ import annotations

from pathlib import Path

from .intake_schema import ScanReport
from .scan_rules import ScanRules


def scan_repository(root: Path, rules: ScanRules | None = None, *, scan_id: str = "scan-local") -> ScanReport:
    effective_rules = rules or ScanRules()
    report = ScanReport(report_version="1.0", scan_id=scan_id, root=str(root))

    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if effective_rules.should_skip(path.relative_to(root)):
            report.skipped_files += 1
            continue

        report.total_files += 1
        if path.stat().st_size > effective_rules.max_flag_file_size_bytes:
            report.flagged_paths.append(str(path.relative_to(root)))

    report.flagged_paths.sort()
    return report
