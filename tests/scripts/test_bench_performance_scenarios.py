# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_performance_scenarios_emit_versioned_artifacts_and_cover_required_scenarios(tmp_path: Path) -> None:
    output_root = tmp_path / "perf"

    subprocess.run(
        [
            sys.executable,
            "scripts/bench_performance_scenarios.py",
            "--sku",
            "community",
            "--version",
            "vtest",
            "--requests",
            "12",
            "--concurrency",
            "3",
            "--output-root",
            str(output_root),
        ],
        check=True,
    )

    scenario_dir = output_root / "sku-performance-scenarios" / "vtest"
    json_files = sorted(scenario_dir.glob("community.performance_scenarios.*.json"))
    md_files = sorted(scenario_dir.glob("community.performance_scenarios.*.md"))

    assert len(json_files) == 1
    assert len(md_files) == 1

    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["baseline_version"] == "vtest"
    assert payload["sku"] == "community"

    assert set(payload["scenarios"].keys()) == {
        "replay_verification_latency",
        "governance_gate_throughput",
        "api_p95_latency_under_concurrent_load",
        "ledger_growth_and_retrieval_performance",
    }
    assert "Overall status" in md_files[0].read_text(encoding="utf-8")
