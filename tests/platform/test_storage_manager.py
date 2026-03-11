import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

import json
import os
import time
import warnings
from pathlib import Path

from runtime.platform.storage_manager import StorageManager


def test_storage_manager_prunes_failed_candidates(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates"
    low = candidates / "low"
    low.mkdir(parents=True)
    (low / "fitness.json").write_text(json.dumps({"score": 0.1}), encoding="utf-8")

    mgr = StorageManager(tmp_path, max_storage_mb=0.0)
    result = mgr.check_and_prune()
    assert result["pruned"]
    assert not low.exists()


def test_storage_manager_uses_configurable_failed_candidate_threshold(
    tmp_path: Path,
) -> None:
    candidates = tmp_path / "candidates"
    keep = candidates / "keep"
    prune = candidates / "prune"
    keep.mkdir(parents=True)
    prune.mkdir(parents=True)
    (keep / "fitness.json").write_text(json.dumps({"score": 0.5}), encoding="utf-8")
    (prune / "fitness.json").write_text(json.dumps({"score": 0.1}), encoding="utf-8")

    mgr = StorageManager(
        tmp_path,
        max_storage_mb=0.0,
        failed_candidate_score_threshold=0.6,
    )
    result = mgr.check_and_prune()

    assert result["pruned"]
    assert result["pruned_count"] == 2
    assert not keep.exists()
    assert not prune.exists()


def test_storage_manager_prunes_old_snapshots(tmp_path: Path) -> None:
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir(parents=True)
    old = snapshots / "old.snap"
    old.write_text("x", encoding="utf-8")
    old_ts = time.time() - (40 * 24 * 60 * 60)
    old.chmod(0o644)
    os.utime(old, (old_ts, old_ts))

    mgr = StorageManager(tmp_path, max_storage_mb=0.0)
    mgr.check_and_prune()
    assert not old.exists()


def test_storage_manager_warns_for_malformed_fitness_json(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates"
    broken = candidates / "broken"
    broken.mkdir(parents=True)
    fitness_file = broken / "fitness.json"
    fitness_file.write_text("{not-json", encoding="utf-8")

    mgr = StorageManager(tmp_path, max_storage_mb=0.0)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pruned = mgr._prune_failed_candidates()

    assert pruned == 0
    assert len(caught) == 1
    payload = json.loads(str(caught[0].message))
    assert payload["path"] == str(fitness_file)
    assert payload["context"]["candidate"] == str(broken)
    assert payload["context"]["error"] == "JSONDecodeError"


def test_storage_manager_prune_report_and_counts_are_deterministic(
    tmp_path: Path,
) -> None:
    candidates = tmp_path / "candidates"
    low = candidates / "low"
    high = candidates / "high"
    low.mkdir(parents=True)
    high.mkdir(parents=True)
    (low / "fitness.json").write_text(json.dumps({"score": 0.2}), encoding="utf-8")
    (high / "fitness.json").write_text(json.dumps({"score": 0.9}), encoding="utf-8")

    snapshots = tmp_path / "snapshots"
    snapshots.mkdir(parents=True)
    old = snapshots / "old.snap"
    recent = snapshots / "recent.snap"
    old.write_text("old", encoding="utf-8")
    recent.write_text("recent", encoding="utf-8")
    old_ts = time.time() - (3 * 24 * 60 * 60)
    recent_ts = time.time() - (12 * 60 * 60)
    os.utime(old, (old_ts, old_ts))
    os.utime(recent, (recent_ts, recent_ts))

    mgr = StorageManager(
        tmp_path,
        max_storage_mb=0.0,
        failed_candidate_score_threshold=0.3,
        snapshot_max_age_days=1,
    )
    result = mgr.check_and_prune()

    assert result["pruned"] is True
    assert result["pruned_count"] == 2
    assert isinstance(result["current_mb"], float)
    assert set(result.keys()) == {"pruned", "pruned_count", "current_mb", "dynamic_agent_pressure"}
    assert not low.exists()
    assert high.exists()
    assert not old.exists()
    assert recent.exists()


def test_storage_manager_reads_thresholds_from_runtime_config(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates"
    borderline = candidates / "borderline"
    borderline.mkdir(parents=True)
    (borderline / "fitness.json").write_text(json.dumps({"score": 0.5}), encoding="utf-8")

    snapshots = tmp_path / "snapshots"
    snapshots.mkdir(parents=True)
    old = snapshots / "old.snap"
    old.write_text("old", encoding="utf-8")
    old_ts = time.time() - (2 * 24 * 60 * 60)
    os.utime(old, (old_ts, old_ts))

    mgr = StorageManager(
        tmp_path,
        max_storage_mb=0.0,
        runtime_config={
            "failed_candidate_score_threshold": 0.6,
            "snapshot_max_age_days": 1,
        },
    )
    result = mgr.check_and_prune()

    assert result["pruned"] is True
    assert result["pruned_count"] == 2
    assert not borderline.exists()
    assert not old.exists()


def test_storage_manager_minimum_reclaim_target_forces_snapshot_prune(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates"
    low = candidates / "low"
    low.mkdir(parents=True)
    (low / "fitness.json").write_text(json.dumps({"score": 0.1}), encoding="utf-8")

    snapshots = tmp_path / "snapshots"
    snapshots.mkdir(parents=True)
    old = snapshots / "old.snap"
    old.write_text("old", encoding="utf-8")
    old_ts = time.time() - (3 * 24 * 60 * 60)
    os.utime(old, (old_ts, old_ts))

    mgr = StorageManager(
        tmp_path,
        max_storage_mb=0.0,
        snapshot_max_age_days=1,
        minimum_reclaim_target_mb=0.01,
    )
    result = mgr.check_and_prune()

    assert result["pruned"] is True
    assert result["pruned_count"] == 2
    assert not low.exists()
    assert not old.exists()


def test_storage_manager_dynamic_agent_pressure_tightens_pruning(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates"
    candidate = candidates / "borderline"
    candidate.mkdir(parents=True)
    (candidate / "fitness.json").write_text(json.dumps({"score": 0.35}), encoding="utf-8")

    mgr = StorageManager(
        tmp_path,
        max_storage_mb=0.0,
        failed_candidate_score_threshold=0.3,
        runtime_config={"dynamic_agent_pressure": 1.0},
    )
    result = mgr.check_and_prune()

    assert result["pruned"] is True
    assert result["dynamic_agent_pressure"] == 1.0
    assert not candidate.exists()


def test_storage_manager_usage_index_reduces_stat_work_for_large_tree(tmp_path: Path) -> None:
    payload_root = tmp_path / "payload"
    payload_root.mkdir(parents=True)
    file_count = 160
    for index in range(file_count):
        bucket = payload_root / f"bucket-{index % 8}"
        bucket.mkdir(parents=True, exist_ok=True)
        (bucket / f"item-{index:03d}.bin").write_bytes(b"x" * (index + 1))

    mgr = StorageManager(tmp_path, runtime_config={"storage_usage_reconcile_interval_s": 3600})
    first_mb = mgr._get_usage_mb()
    first_scan = dict(mgr._last_usage_scan)

    second_mb = mgr._get_usage_mb()
    second_scan = dict(mgr._last_usage_scan)

    assert second_mb == first_mb
    assert first_scan["mode"] == "full"
    assert second_scan["mode"] == "incremental"
    assert first_scan["files_statted"] == file_count
    assert second_scan["files_statted"] == 0


def test_storage_manager_usage_index_tracks_mutations_and_emits_scan_metrics(tmp_path: Path, monkeypatch) -> None:
    metrics_events: list[dict[str, object]] = []

    def _capture(event_type: str, payload: dict[str, object] | None = None, level: str = "INFO", element_id: str | None = None) -> None:
        metrics_events.append({"event_type": event_type, "payload": payload or {}, "level": level, "element_id": element_id})

    monkeypatch.setattr("runtime.platform.storage_manager.metrics.log", _capture)

    payload_dir = tmp_path / "payload"
    payload_dir.mkdir(parents=True)
    alpha = payload_dir / "alpha.txt"
    beta = payload_dir / "beta.txt"
    alpha.write_bytes(b"a" * 10)
    beta.write_bytes(b"b" * 20)

    mgr = StorageManager(tmp_path, runtime_config={"storage_usage_reconcile_interval_s": 3600})
    base_mb = mgr._get_usage_mb()

    time.sleep(1.05)
    gamma = payload_dir / "gamma.txt"
    gamma.write_bytes(b"c" * 30)
    beta.unlink()
    os.utime(payload_dir, None)

    mutated_mb = mgr._get_usage_mb()
    assert mutated_mb != base_mb
    expected_bytes = alpha.stat().st_size + gamma.stat().st_size
    assert mutated_mb == expected_bytes / (1024.0 * 1024.0)

    usage_events = [entry for entry in metrics_events if entry["event_type"] == "storage_manager_usage_scan"]
    assert usage_events
    latest_payload = usage_events[-1]["payload"]
    assert isinstance(latest_payload, dict)
    assert latest_payload["duration_ms"] >= 0
    assert latest_payload["files_statted"] >= 2


def test_storage_manager_check_and_prune_reuses_usage_scan_when_no_mutation(tmp_path: Path, monkeypatch) -> None:
    payload_dir = tmp_path / "payload"
    payload_dir.mkdir(parents=True)
    (payload_dir / "file.txt").write_bytes(b"seed")

    mgr = StorageManager(tmp_path, max_storage_mb=10_000.0)

    scan_calls = 0
    original_get_usage = StorageManager._get_usage_mb

    def _tracked_get_usage(self: StorageManager) -> float:
        nonlocal scan_calls
        scan_calls += 1
        return original_get_usage(self)

    monkeypatch.setattr(StorageManager, "_get_usage_mb", _tracked_get_usage)
    result = mgr.check_and_prune()

    assert result["pruned"] is False
    assert scan_calls == 1
