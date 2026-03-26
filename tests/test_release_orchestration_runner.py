import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

import json
import re
import subprocess
from pathlib import Path


def test_orchestration_skips_when_no_policy_compliant(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidates.json"
    candidate_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {"candidate_id": "c1", "score": 0.9, "policy_compliant": False},
                    {"candidate_id": "c2", "score": 0.8, "policy_verdict": "deny"},
                ]
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundles"

    result = subprocess.run(
        [
            "python",
            "scripts/orchestrate_release_candidates.py",
            "--candidates",
            str(candidate_path),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout.strip())
    assert payload["status"] == "skipped_no_policy_compliant_candidate"
    bundle = json.loads(Path(payload["bundle_path"]).read_text(encoding="utf-8"))
    assert bundle["selected_candidate"] is None
    assert bundle["release_packaging"] is None


def test_orchestration_runs_for_top_compliant_candidate(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidates.json"
    candidate_path.write_text(
        json.dumps(
            [
                {"candidate_id": "c1", "score": 0.5, "policy_compliant": True},
                {"candidate_id": "c2", "score": 0.8, "policy_verdict": "allow"},
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundles"

    result = subprocess.run(
        [
            "python",
            "scripts/orchestrate_release_candidates.py",
            "--candidates",
            str(candidate_path),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode in {0, 1}
    payload = json.loads(result.stdout.strip())
    bundle = json.loads(Path(payload["bundle_path"]).read_text(encoding="utf-8"))
    assert bundle["selected_candidate"]["candidate_id"] == "c2"
    assert bundle["release_packaging"] is not None


def test_bundle_id_is_digest_based_and_deterministic(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidates.json"
    candidate_path.write_text(
        json.dumps(
            {
                "release_version": "9.0.0",
                "lane": "governance",
                "candidates": [
                    {"candidate_id": "c1", "score": 0.9, "policy_compliant": False},
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundles"
    command = [
        "python",
        "scripts/orchestrate_release_candidates.py",
        "--candidates",
        str(candidate_path),
        "--output-dir",
        str(output_dir),
    ]

    first = subprocess.run(command, check=False, capture_output=True, text=True)
    second = subprocess.run(command, check=False, capture_output=True, text=True)

    assert first.returncode == 0
    assert second.returncode == 0

    first_payload = json.loads(first.stdout.strip())
    second_payload = json.loads(second.stdout.strip())
    first_bundle = json.loads(Path(first_payload["bundle_path"]).read_text(encoding="utf-8"))
    second_bundle = json.loads(Path(second_payload["bundle_path"]).read_text(encoding="utf-8"))

    pattern = re.compile(r"^release-decision-[0-9a-f]{12}$")
    assert pattern.match(first_bundle["bundle_id"])
    assert first_bundle["bundle_id"] == second_bundle["bundle_id"]
