# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from runtime.evolution.replay_divergence_artifacts import build_replay_divergence_artifacts

pytestmark = pytest.mark.regression_standard


class _FakeLedger:
    def read_epoch(self, epoch_id: str):
        return [
            {
                "type": "MutationBundleEvent",
                "payload": {
                    "epoch_id": epoch_id,
                    "nonce": "abc123",
                    "event_timestamp": "2026-01-01T00:00:00Z",
                    "bundle_id": "bundle-1",
                },
            }
        ]


def test_build_replay_divergence_artifacts_writes_machine_and_human_reports(tmp_path: Path) -> None:
    preflight = {
        "verify_target": "single_epoch",
        "decision": "fail_closed",
        "has_divergence": True,
        "results": [
            {
                "epoch_id": "epoch-1",
                "expected_digest": "sha256:aaa",
                "actual_digest": "sha256:bbb",
                "passed": False,
                "generated_at": "2026-01-02T00:00:00Z",
            }
        ],
    }
    with mock.patch("runtime.evolution.replay_divergence_artifacts.subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0, stdout="determinism lint ok\n", stderr="")
        bundle = build_replay_divergence_artifacts(
            preflight=preflight,
            replay_command="python -m app.main --verify-replay --replay strict --replay-epoch epoch-1",
            replay_env_flags={"ADAAD_FORCE_DETERMINISTIC_PROVIDER": "1", "ADAAD_DETERMINISTIC_SEED": "ci"},
            ledger=_FakeLedger(),
            artifacts_root=tmp_path,
        )

    machine_path = Path(bundle.machine_report_path)
    human_path = Path(bundle.human_report_path)
    assert machine_path.exists()
    assert human_path.exists()

    report = json.loads(machine_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "replay_divergence_artifact.v1"
    assert report["digests"] == {"base": "sha256:aaa", "current": "sha256:bbb"}
    assert report["replay"]["verify_target"] == "single_epoch"
    assert report["normalized_timeline"]["first_divergence_epoch"] == "epoch-1"
    assert report["determinism_lint"]["command"].startswith("python tools/lint_determinism.py")


def test_build_replay_divergence_artifacts_normalizes_nondeterministic_fields(tmp_path: Path) -> None:
    preflight = {
        "verify_target": "all_epochs",
        "decision": "fail_closed",
        "has_divergence": True,
        "results": [
            {
                "epoch_id": "epoch-7",
                "expected": "sha256:111",
                "digest": "sha256:222",
                "passed": False,
                "timestamp": "2026-01-02T10:11:12Z",
                "run_id": "run-xyz",
            }
        ],
    }
    with mock.patch("runtime.evolution.replay_divergence_artifacts.subprocess.run") as run:
        run.return_value = mock.Mock(returncode=1, stdout="violation line\n", stderr="")
        bundle = build_replay_divergence_artifacts(
            preflight=preflight,
            replay_command="python -m app.main --verify-replay --replay strict",
            replay_env_flags={},
            ledger=_FakeLedger(),
            artifacts_root=tmp_path,
        )

    report = json.loads(Path(bundle.machine_report_path).read_text(encoding="utf-8"))
    excerpt = report["normalized_timeline"]["result_excerpt"]
    assert excerpt["timestamp"] == "<normalized>"
    assert excerpt["run_id"] == "<normalized>"
    assert report["determinism_lint"]["status"] == "violations"
