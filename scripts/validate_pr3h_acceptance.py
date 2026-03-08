#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run PR-3H acceptance tests and emit machine-readable audit output."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/pr3h_acceptance_audit.json"),
        help="Path to write machine-readable audit output.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/acceptance/pr3h",
        "-m",
        "pr3h_acceptance",
        "-q",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    audit_payload = {
        "suite": "pr3h_acceptance",
        "command": " ".join(command),
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
        "status": "pass" if completed.returncode == 0 else "fail",
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit_payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(audit_payload, indent=2, sort_keys=True))

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
