# SPDX-License-Identifier: Apache-2.0
"""Storage footprint management for ADAAD runtime data."""

from __future__ import annotations

import json
import logging
import shutil
import time
import warnings
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Mapping

from runtime import metrics


LOG = logging.getLogger(__name__)
METRIC_EVENT = "storage_manager_prune_fallback"


class StorageManager:
    def __init__(
        self,
        data_root: Path,
        max_storage_mb: float = 5000.0,
        failed_candidate_score_threshold: float | None = None,
        snapshot_max_age_days: int | None = None,
        minimum_reclaim_target_mb: float | None = None,
        governance_config: Mapping[str, Any] | None = None,
        runtime_config: Mapping[str, Any] | None = None,
    ):
        self.data_root = data_root
        self.max_storage_mb = max_storage_mb
        self.failed_candidate_score_threshold = self._coerce_float(
            failed_candidate_score_threshold,
            runtime_config,
            governance_config,
            key="failed_candidate_score_threshold",
            default=0.3,
        )
        self.snapshot_max_age_days = int(
            self._coerce_float(
                snapshot_max_age_days,
                runtime_config,
                governance_config,
                key="snapshot_max_age_days",
                default=30.0,
            )
        )
        self.minimum_reclaim_target_mb = self._coerce_optional_float(
            minimum_reclaim_target_mb,
            runtime_config,
            governance_config,
            key="minimum_reclaim_target_mb",
        )
        self.dynamic_agent_pressure = self._coerce_optional_float(
            None,
            runtime_config,
            governance_config,
            key="dynamic_agent_pressure",
        )

    def check_and_prune(self) -> dict:
        current_mb = self._get_usage_mb()
        pressure = self._effective_dynamic_pressure()
        storage_cap_mb = self.max_storage_mb * (1.0 - (0.25 * pressure))
        if current_mb < storage_cap_mb:
            return {"pruned": False, "current_mb": round(current_mb, 3), "dynamic_agent_pressure": round(pressure, 3)}

        baseline_mb = current_mb
        pruned_count = self._prune_failed_candidates(pressure=pressure)
        current_mb = self._get_usage_mb()
        should_prune_snapshots = current_mb >= storage_cap_mb
        if self.minimum_reclaim_target_mb is not None:
            reclaimed_mb = max(0.0, baseline_mb - current_mb)
            should_prune_snapshots = should_prune_snapshots or reclaimed_mb < self.minimum_reclaim_target_mb

        if should_prune_snapshots:
            pruned_count += self._prune_old_snapshots(pressure=pressure)

        return {
            "pruned": True,
            "pruned_count": pruned_count,
            "current_mb": round(self._get_usage_mb(), 3),
            "dynamic_agent_pressure": round(pressure, 3),
        }

    def _get_usage_mb(self) -> float:
        total_bytes = 0
        if not self.data_root.exists():
            return 0.0
        for path in self.data_root.rglob("*"):
            if path.is_file():
                total_bytes += path.stat().st_size
        return total_bytes / (1024.0 * 1024.0)

    def _prune_failed_candidates(self, *, pressure: float = 0.0) -> int:
        candidates_dir = self.data_root / "candidates"
        if not candidates_dir.exists():
            return 0
        pruned = 0
        for candidate in sorted(candidates_dir.glob("*"), key=lambda path: path.name):
            if not candidate.is_dir():
                continue
            fitness_file = candidate / "fitness.json"
            if not fitness_file.exists():
                continue
            try:
                fitness = json.loads(fitness_file.read_text(encoding="utf-8"))
            except (JSONDecodeError, OSError, ValueError) as exc:
                self._warn(
                    "Failed to read candidate fitness for pruning",
                    path=fitness_file,
                    context={"candidate": str(candidate), "error": type(exc).__name__},
                )
                continue
            try:
                score = float(fitness.get("score", 1.0))
            except ValueError as exc:
                self._warn(
                    "Failed to parse candidate fitness score for pruning",
                    path=fitness_file,
                    context={"candidate": str(candidate), "error": type(exc).__name__},
                )
                continue
            threshold = max(0.05, self.failed_candidate_score_threshold + (0.20 * max(0.0, pressure)))
            if score < threshold:
                shutil.rmtree(candidate, ignore_errors=True)
                pruned += 1
        return pruned

    def _prune_old_snapshots(self, *, pressure: float = 0.0) -> int:
        snapshots_dir = self.data_root / "snapshots"
        if not snapshots_dir.exists():
            return 0
        effective_days = max(1, int(self.snapshot_max_age_days * (1.0 - (0.5 * max(0.0, pressure)))))
        threshold = time.time() - (effective_days * 24 * 60 * 60)
        pruned = 0
        for snapshot in sorted(snapshots_dir.glob("*"), key=lambda path: path.name):
            try:
                if snapshot.stat().st_mtime < threshold:
                    if snapshot.is_dir():
                        shutil.rmtree(snapshot, ignore_errors=True)
                    else:
                        snapshot.unlink(missing_ok=True)
                    pruned += 1
            except (OSError, ValueError) as exc:
                self._warn(
                    "Failed to evaluate or prune snapshot",
                    path=snapshot,
                    context={"error": type(exc).__name__},
                )
                continue
        return pruned

    @staticmethod
    def _warn(message: str, path: Path, context: dict[str, str]) -> None:
        details = {
            "warning_message": message,
            "path": str(path),
            "context": context,
        }
        LOG.warning("storage manager prune fallback", extra=details)
        metrics.log(event_type=METRIC_EVENT, payload=details, level="WARNING")
        warnings.warn(json.dumps(details, sort_keys=True), stacklevel=2)

    def _effective_dynamic_pressure(self) -> float:
        if self.dynamic_agent_pressure is None:
            return 0.0
        return max(0.0, min(1.0, float(self.dynamic_agent_pressure)))

    @staticmethod
    def _coerce_float(
        explicit: float | int | None,
        runtime_config: Mapping[str, Any] | None,
        governance_config: Mapping[str, Any] | None,
        *,
        key: str,
        default: float,
    ) -> float:
        if explicit is not None:
            return float(explicit)
        for source in (runtime_config, governance_config):
            if not isinstance(source, Mapping):
                continue
            value = source.get(key)
            if value is not None:
                return float(value)
        return default

    @staticmethod
    def _coerce_optional_float(
        explicit: float | int | None,
        runtime_config: Mapping[str, Any] | None,
        governance_config: Mapping[str, Any] | None,
        *,
        key: str,
    ) -> float | None:
        if explicit is not None:
            return float(explicit)
        for source in (runtime_config, governance_config):
            if not isinstance(source, Mapping):
                continue
            value = source.get(key)
            if value is not None:
                return float(value)
        return None


__all__ = ["StorageManager"]
