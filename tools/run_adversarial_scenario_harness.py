# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
from pathlib import Path

from runtime.analysis.adversarial_scenario_harness import run_manifest, write_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic governance adversarial scenario harness")
    parser.add_argument("--manifest", default="tests/security/fixtures/adversarial_governance_scenarios.json")
    parser.add_argument("--output", default="reports/security/adversarial_scenarios_summary.json")
    args = parser.parse_args()

    report = run_manifest(Path(args.manifest))
    write_summary(report, Path(args.output))

    for result in report["results"]:
        print(
            f"{result['scenario_id']}: expected={result['expected_verdict']} actual={result['actual_verdict']} "
            f"pass={result['passed']}"
        )

    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
