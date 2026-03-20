#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""verify_doc_sync.py — Phase 78 M78-02

Asserts that README.md version markers and badge strings match the VERSION file.
Exits 0 on clean sync, exits 1 on any drift detected.

Constitutional invariants:
  DOC-SYNC-VERSION-0   README infobox version == VERSION file
  DOC-SYNC-BADGE-0     README badge version strings == VERSION file
  DOC-SYNC-NO-BYPASS-0 CI must call this script; manual doc patches are not accepted
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

def load_version() -> str:
    return (ROOT / "VERSION").read_text().strip()

def check_infobox(readme: str, version: str) -> list[str]:
    errors = []
    pattern = r"<!-- ADAAD_VERSION_INFOBOX:START -->.*?<!-- ADAAD_VERSION_INFOBOX:END -->"
    match = re.search(pattern, readme, re.DOTALL)
    if not match:
        errors.append("ADAAD_VERSION_INFOBOX markers not found in README.md")
        return errors
    block = match.group(0)
    if f"`{version}`" not in block and f"| `{version}` |" not in block:
        errors.append(f"DOC-SYNC-VERSION-0 FAIL: infobox does not contain version {version!r}")
    return errors

def check_badges(readme: str, version: str) -> list[str]:
    errors = []
    # Main version badge
    if f"ADAAD-v{version}" not in readme:
        errors.append(f"DOC-SYNC-BADGE-0 FAIL: main version badge does not contain v{version}")
    return errors

def main() -> int:
    version = load_version()
    readme = (ROOT / "README.md").read_text()
    errors = []
    errors.extend(check_infobox(readme, version))
    errors.extend(check_badges(readme, version))
    if errors:
        print(f"verify_doc_sync: VERSION={version!r} — {len(errors)} drift(s) detected:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print(f"verify_doc_sync: VERSION={version!r} — README in sync ✓")
    return 0

if __name__ == "__main__":
    sys.exit(main())
