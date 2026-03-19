# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_mobile_benchmark_emits_artifacts_and_respects_budget_contract(tmp_path: Path) -> None:
    budgets = tmp_path / "budgets.json"
    budgets.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "profile": "pydroid3_constrained",
                "metrics": {
                    "startup_latency_ms": {"baseline": 10.0, "max": 5000.0, "regression_tolerance_pct": 100000.0},
                    "peak_memory_mb": {"baseline": 10.0, "max": 5000.0, "regression_tolerance_pct": 100000.0},
                    "qr_workflow_ms": {"baseline": 10.0, "max": 5000.0, "regression_tolerance_pct": 100000.0},
                    "ledger_workflow_ms": {"baseline": 10.0, "max": 5000.0, "regression_tolerance_pct": 100000.0},
                },
            }
        ),
        encoding="utf-8",
    )

    output_json = tmp_path / "mobile_benchmark.json"
    output_md = tmp_path / "mobile_benchmark_summary.md"

    subprocess.run(
        [
            sys.executable,
            "scripts/bench_mobile_profile.py",
            "--iterations",
            "1",
            "--warmups",
            "0",
            "--budgets",
            str(budgets),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        check=True,
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["profile"] == "pydroid3_constrained"
    assert payload["pass"] is True
    assert {row["metric"] for row in payload["results"]} == {
        "startup_latency_ms",
        "peak_memory_mb",
        "qr_workflow_ms",
        "ledger_workflow_ms",
    }
    assert "Overall status" in output_md.read_text(encoding="utf-8")
