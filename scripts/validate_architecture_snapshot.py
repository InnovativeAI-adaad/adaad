#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate architecture snapshot metadata against canonical version + git metadata.

By default this script validates tracked snapshot docs are up-to-date.
Use --write to refresh the managed metadata block.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.report_version import build_snapshot_metadata

SNAPSHOT_DOC = ROOT / "docs" / "README_IMPLEMENTATION_ALIGNMENT.md"
START = "<!-- ARCH_SNAPSHOT_METADATA:START -->"
END = "<!-- ARCH_SNAPSHOT_METADATA:END -->"


def _metadata_block() -> str:
    meta = build_snapshot_metadata()
    return "\n".join(
        [
            START,
            "## Architecture Deep-Dive Snapshot",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Report version | `{meta['report_version']}` |",
            f"| Branch | `{meta['branch']}` |",
            f"| Tag | `{meta['tag']}` |",
            f"| Short SHA | `{meta['short_sha']}` |",
            "",
            "All future architecture snapshots MUST include branch, tag (if any), and short SHA.",
            END,
        ]
    )


def _replace_managed_block(content: str, new_block: str) -> str:
    if START not in content or END not in content:
        raise ValueError("managed metadata block markers not found")
    head, rest = content.split(START, 1)
    _old, tail = rest.split(END, 1)
    return f"{head}{new_block}{tail}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate architecture snapshot metadata block.")
    parser.add_argument("--write", action="store_true", help="Rewrite managed metadata block in-place")
    args = parser.parse_args()

    content = SNAPSHOT_DOC.read_text(encoding="utf-8")
    block = _metadata_block()
    updated = _replace_managed_block(content, block)

    if args.write:
        SNAPSHOT_DOC.write_text(updated, encoding="utf-8")
        print(f"updated {SNAPSHOT_DOC.relative_to(ROOT)}")
        return 0

    if updated != content:
        print("architecture snapshot metadata drift detected", file=sys.stderr)
        print("run: python scripts/validate_architecture_snapshot.py --write", file=sys.stderr)
        return 1

    print("architecture snapshot metadata OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
