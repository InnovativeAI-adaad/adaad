# SPDX-License-Identifier: Apache-2.0
"""Schema helpers for intake manifests and scan reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(slots=True)
class IntakeManifest:
    manifest_version: str
    intake_id: str
    source_type: str
    source_ref: str
    extracted_at: str = field(default_factory=now_utc_iso)
    extracted_file_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScanReport:
    report_version: str
    scan_id: str
    root: str
    scanned_at: str = field(default_factory=now_utc_iso)
    total_files: int = 0
    skipped_files: int = 0
    flagged_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
