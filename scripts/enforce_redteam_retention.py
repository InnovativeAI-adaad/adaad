#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M-06: Red-team evidence retention policy enforcer.

Enforces configurable retention for reports/redteam/ artifacts.
Files older than ADAAD_REDTEAM_EVIDENCE_RETENTION_DAYS (default 90) are rotated.
Fails closed if the directory exceeds ADAAD_REDTEAM_EVIDENCE_SIZE_CAP_MB
(default 500 MB) — requires operator acknowledgment before the nightly
harness will proceed.

Usage:
    python scripts/enforce_redteam_retention.py           # rotate + sentinel check
    python scripts/enforce_redteam_retention.py --dry-run # report only, no deletion
    python scripts/enforce_redteam_retention.py --check-only # size-cap sentinel only
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REDTEAM_DIR = REPO_ROOT / "reports" / "redteam"
SENTINEL_PATH = REDTEAM_DIR / ".retention_sentinel.json"

_DEFAULT_RETENTION_DAYS = 90
_DEFAULT_SIZE_CAP_MB = 500


def _retention_days() -> int:
    try:
        return max(1, int(os.environ.get("ADAAD_REDTEAM_EVIDENCE_RETENTION_DAYS", _DEFAULT_RETENTION_DAYS)))
    except (ValueError, TypeError):
        return _DEFAULT_RETENTION_DAYS


def _size_cap_bytes() -> int:
    try:
        mb = float(os.environ.get("ADAAD_REDTEAM_EVIDENCE_SIZE_CAP_MB", _DEFAULT_SIZE_CAP_MB))
        return int(max(1.0, mb) * 1024 * 1024)
    except (ValueError, TypeError):
        return _DEFAULT_SIZE_CAP_MB * 1024 * 1024


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for f in path.rglob("*"):
        if f.is_file() and f != SENTINEL_PATH:
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def _write_sentinel(rotated_count: int, dir_bytes: int) -> None:
    SENTINEL_PATH.write_text(
        json.dumps({
            "last_rotation_epoch": int(time.time()),
            "rotated_files": rotated_count,
            "dir_bytes_after": dir_bytes,
            "retention_days": _retention_days(),
            "size_cap_mb": _size_cap_bytes() // (1024 * 1024),
        }, indent=2),
        encoding="utf-8",
    )


def _read_sentinel() -> dict:
    try:
        return json.loads(SENTINEL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main(argv: list[str] | None = None) -> int:
    args = set(argv if argv is not None else sys.argv[1:])
    dry_run = "--dry-run" in args
    check_only = "--check-only" in args

    REDTEAM_DIR.mkdir(parents=True, exist_ok=True)

    retention_seconds = _retention_days() * 86400
    size_cap = _size_cap_bytes()
    now = time.time()
    cutoff = now - retention_seconds
    rotated: list[Path] = []

    if not check_only:
        for f in sorted(REDTEAM_DIR.rglob("*")):
            if not f.is_file() or f == SENTINEL_PATH:
                continue
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                rotated.append(f)
                if not dry_run:
                    f.unlink(missing_ok=True)

        verb = "Would rotate" if dry_run else "Rotated"
        if rotated:
            print(f"[redteam-retention] {verb} {len(rotated)} file(s) older than {_retention_days()} days:")
            for f in rotated:
                print(f"  {f.relative_to(REPO_ROOT)}")
        else:
            print(f"[redteam-retention] No files older than {_retention_days()} days.")

    # Size-cap sentinel check — fail closed if exceeded without operator ack
    current_bytes = _dir_size_bytes(REDTEAM_DIR)
    current_mb = current_bytes / (1024 * 1024)
    cap_mb = _size_cap_bytes() // (1024 * 1024)

    if not dry_run and rotated:
        _write_sentinel(len(rotated), current_bytes)

    sentinel = _read_sentinel()
    last_rotation = sentinel.get("last_rotation_epoch", 0)
    days_since = (now - last_rotation) / 86400 if last_rotation else float("inf")

    print(f"[redteam-retention] Dir size: {current_mb:.1f} MB / {cap_mb} MB cap")

    if current_bytes > size_cap:
        print(
            f"[redteam-retention] FAIL: reports/redteam/ exceeds {cap_mb} MB cap "
            f"({current_mb:.1f} MB). Last rotation: {days_since:.0f}d ago. "
            f"Lower ADAAD_REDTEAM_EVIDENCE_RETENTION_DAYS or raise "
            f"ADAAD_REDTEAM_EVIDENCE_SIZE_CAP_MB, then re-run.",
            file=sys.stderr,
        )
        return 1

    if last_rotation:
        print(f"[redteam-retention] OK. Last rotation: {days_since:.0f} days ago.")
    else:
        print("[redteam-retention] OK. No prior rotation recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
