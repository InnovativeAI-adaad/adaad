# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
from pathlib import Path

from runtime.analysis.redteam_harness import run_harness, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic red-team harness")
    parser.add_argument("--scenario-file", default="experiments/redteam/scenarios.json")
    parser.add_argument("--subset", choices=("all", "critical"), default="all")
    parser.add_argument("--output", default="reports/redteam/latest.json")
    args = parser.parse_args()

    report = run_harness(Path(args.scenario_file), subset=args.subset)
    write_report(report, Path(args.output))

    if report["failed_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
