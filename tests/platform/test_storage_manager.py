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
