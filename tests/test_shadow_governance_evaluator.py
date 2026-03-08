# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import sys


def test_shadow_governance_evaluator_emits_expected_metrics(tmp_path) -> None:
    report_path = tmp_path / "report.json"
    cmd = [
        sys.executable,
        "scripts/evaluate_shadow_governance.py",
        "--candidate",
        "governance/governance_policy_v1.json",
        "--dataset",
        "tests/fixtures/governance/shadow_replay_ledger.json",
        "--output",
        str(report_path),
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["metrics"]["records_evaluated"] == 6
    assert payload["metrics"]["false_allow_rate"] == 0.0
    assert payload["metrics"]["false_block_rate"] == 0.16666666666666666
    assert payload["metrics"]["false_block_count"] == 1
    assert payload["metrics"]["divergence_count"] == 1
