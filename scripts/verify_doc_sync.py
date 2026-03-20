#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""verify_doc_sync.py — M78-02 documentation determinism gate.

Asserts that the README.md version infobox, badge strings, hero-image alt
text, and stats-card alt text all match the canonical VERSION file on disk.

Invariants
----------
DOC-SYNC-VERSION-0  : README version string equals VERSION file content.
DOC-SYNC-DETERM-0   : identical repo state → identical exit code on every run.
DOC-SYNC-NO-BYPASS-0: exits 1 on *any* version drift; CI must not skip this check.

Exit codes
----------
0 — all checks pass (clean, no drift).
1 — one or more SYNC_DRIFT_* violations detected (details printed to stdout as JSON).

Usage
-----
    python scripts/verify_doc_sync.py
    python scripts/verify_doc_sync.py --root /path/to/repo --format text
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Patterns that must agree with VERSION
# ---------------------------------------------------------------------------

# shields.io for-the-badge ADAAD version pill:
#   [![Version](https://img.shields.io/badge/ADAAD-9.12.1-000?...)]
_BADGE_ADAAD_RE = re.compile(
    r"https://img\.shields\.io/badge/ADAAD-(\d+\.\d+\.\d+)-",
)

# shields.io PyPI badge:
#   [![PyPI](https://img.shields.io/badge/PyPI-adaad_9.12.1-000?...)]
_BADGE_PYPI_RE = re.compile(
    r"https://img\.shields\.io/badge/PyPI-adaad_(\d+\.\d+\.\d+)-",
)

# PyPI URL in badge link target:
#   https://pypi.org/project/adaad/9.12.1/
_PYPI_URL_RE = re.compile(
    r"https://pypi\.org/project/adaad/(\d+\.\d+\.\d+)/",
)

# Hero image alt attribute:
#   alt="ADAAD — ... · v9.12.1 · Phase N"
_HERO_ALT_RE = re.compile(
    r'alt="ADAAD[^"]*· v(\d+\.\d+\.\d+) ·',
)

# Stats-card alt attribute:
#   alt="ADAAD Stats — v9.12.1 · ..."
_STATS_ALT_RE = re.compile(
    r'alt="ADAAD Stats[^"]*v(\d+\.\d+\.\d+)',
)

# Tests badge (flat-square):
#   ![Tests](https://img.shields.io/badge/N_Tests-Passing-...)
_TESTS_BADGE_RE = re.compile(
    r"https://img\.shields\.io/badge/([\d,%2C]+)_Tests-Passing-",
)

# Infobox Current version row:
#   | **Current version** | `9.12.1` |
_INFOBOX_VERSION_RE = re.compile(
    r"\*\*Current version\*\*\s*\|\s*`(\d+\.\d+\.\d+)`",
)


@dataclass
class Drift:
    rule: str
    location: str
    found: str
    expected: str

    def to_dict(self) -> dict:
        return {
            "event": "SYNC_DRIFT",
            "rule": self.rule,
            "location": self.location,
            "found": self.found,
            "expected": self.expected,
        }


@dataclass
class VerifyResult:
    version: str
    drifts: list[Drift] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.drifts) == 0


def _check_pattern(
    content: str,
    pattern: re.Pattern,
    expected: str,
    rule: str,
    location: str,
    result: VerifyResult,
) -> None:
    for match in pattern.finditer(content):
        found = match.group(1)
        if found != expected:
            result.drifts.append(
                Drift(rule=rule, location=location, found=found, expected=expected)
            )


def verify(root: Path) -> VerifyResult:
    """Run all sync-version checks under *root* and return a VerifyResult.

    DOC-SYNC-DETERM-0: this function is pure — given the same filesystem state
    it always returns the same result.
    """
    version_path = root / "VERSION"
    if not version_path.exists():
        print(
            json.dumps({"event": "SYNC_ERROR_MISSING_VERSION", "path": str(version_path)}),
            flush=True,
        )
        sys.exit(1)

    version = version_path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        print(
            json.dumps({"event": "SYNC_ERROR_BAD_VERSION", "raw": version}),
            flush=True,
        )
        sys.exit(1)

    result = VerifyResult(version=version)
    readme_path = root / "README.md"

    if not readme_path.exists():
        result.drifts.append(
            Drift(
                rule="DOC-SYNC-VERSION-0",
                location="README.md",
                found="(missing)",
                expected=version,
            )
        )
        return result

    readme = readme_path.read_text(encoding="utf-8")

    checks = [
        (_BADGE_ADAAD_RE,  "DOC-SYNC-VERSION-0",  "README.md / ADAAD badge"),
        (_BADGE_PYPI_RE,   "DOC-SYNC-VERSION-0",  "README.md / PyPI badge"),
        (_PYPI_URL_RE,     "DOC-SYNC-VERSION-0",  "README.md / PyPI URL"),
        (_HERO_ALT_RE,     "DOC-SYNC-VERSION-0",  "README.md / hero alt"),
        (_STATS_ALT_RE,    "DOC-SYNC-VERSION-0",  "README.md / stats-card alt"),
        (_INFOBOX_VERSION_RE, "DOC-SYNC-VERSION-0", "README.md / VERSION_INFOBOX"),
    ]
    for pattern, rule, location in checks:
        _check_pattern(readme, pattern, version, rule, location, result)

    return result


def _format_text(result: VerifyResult) -> str:
    lines = [f"verify_doc_sync — VERSION={result.version}"]
    if result.clean:
        lines.append("  ✓ all checks passed — no drift detected")
    else:
        for d in result.drifts:
            lines.append(f"  ✗ {d.rule}  {d.location}: found={d.found!r} expected={d.expected!r}")
    return "\n".join(lines)


def _format_json(result: VerifyResult) -> str:
    out = []
    out.append(json.dumps({"event": "verify_start", "version": result.version}))
    for d in result.drifts:
        out.append(json.dumps(d.to_dict()))
    out.append(
        json.dumps({
            "event": "verify_complete",
            "version": result.version,
            "drift_count": len(result.drifts),
            "clean": result.clean,
        })
    )
    return "\n".join(out)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Verify README version strings match the VERSION file (M78-02).",
    )
    p.add_argument(
        "--root",
        default=str(ROOT),
        help="Repository root (default: repo root auto-detected from script location).",
    )
    p.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format (default: json for CI readability).",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = verify(Path(args.root))

    if args.format == "text":
        print(_format_text(result))
    else:
        print(_format_json(result))

    # DOC-SYNC-NO-BYPASS-0: exit 1 on any drift.
    return 0 if result.clean else 1


if __name__ == "__main__":
    sys.exit(main())
