#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate env-var inventory freshness for CI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import generate_env_var_inventory  # noqa: E402


def main() -> int:
    return generate_env_var_inventory.main(["--check", "--format", "json"])


if __name__ == "__main__":
    raise SystemExit(main())
