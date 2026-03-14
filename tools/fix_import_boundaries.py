#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compatibility wrapper for the canonical import-boundary fixer CLI.

Deprecated: invoke ``python fix_import_boundaries.py`` directly.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    canonical = repo_root / "fix_import_boundaries.py"
    print(
        "DEPRECATION: tools/fix_import_boundaries.py is a compatibility wrapper; "
        "use `python fix_import_boundaries.py ...` instead.",
        file=sys.stderr,
    )
    try:
        runpy.run_path(str(canonical), run_name="__main__")
    except SystemExit as exc:  # pragma: no cover - passthrough behavior
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
