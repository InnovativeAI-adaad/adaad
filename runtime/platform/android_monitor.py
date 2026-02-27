# SPDX-License-Identifier: Apache-2.0
"""Android-aware runtime resource monitoring."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from pathlib import Path

from runtime import metrics


LOG = logging.getLogger(__name__)
METRIC_EVENT = "android_monitor_probe_fallback"


def _emit_probe_fallback(
    *,
    probe: str,
    reason_code: str,
    fallback_value: float,
    source_path: str | None = None,
    error: Exception | None = None,
) -> None:
    payload = {
        "probe": probe,
        "reason_code": reason_code,
        "fallback_value": fallback_value,
    }
    if source_path is not None:
        payload["source_path"] = source_path
    if error is not None:
        payload["error_type"] = type(error).__name__
    LOG.warning("android monitor probe fallback", extra=payload)
    metrics.log(event_type=METRIC_EVENT, payload=payload, level="WARNING")


@dataclass(frozen=True)
class ResourceSnapshot:
    battery_percent: float
    memory_mb: float
    storage_mb: float
    cpu_percent: float
    dynamic_agent_pressure: float = 0.0

    def _pressure_adjustment(self) -> float:
        return max(0.0, min(1.0, self.dynamic_agent_pressure))

    def is_constrained(self) -> bool:
        pressure = self._pressure_adjustment()
        memory_floor = 500.0 + (700.0 * pressure)
        storage_floor = 1000.0 + (1500.0 * pressure)
        cpu_ceiling = 80.0 - (10.0 * pressure)
        return (
            self.battery_percent < 20.0
            or self.memory_mb < memory_floor
            or self.storage_mb < storage_floor
            or self.cpu_percent > cpu_ceiling
        )

    def should_throttle(self) -> bool:
        pressure = self._pressure_adjustment()
        memory_floor = 1000.0 + (900.0 * pressure)
        storage_floor = 2000.0 + (2200.0 * pressure)
        battery_floor = 50.0 + (10.0 * pressure)
        return self.battery_percent < battery_floor or self.memory_mb < memory_floor or self.storage_mb < storage_floor


class AndroidMonitor:
    """Collect lightweight resource signals with Android-aware battery probing."""

    def __init__(self, data_root: Path):
        self.data_root = data_root
        self.is_android = self._detect_android()

    @staticmethod
    def _detect_android() -> bool:
        return Path("/system/build.prop").exists()

    def snapshot(self) -> ResourceSnapshot:
        dynamic_pressure = self._dynamic_agent_pressure()
        if not self.is_android:
            return ResourceSnapshot(100.0, self._read_memory(), self._read_storage(), self._read_cpu(), dynamic_pressure)
        return ResourceSnapshot(self._read_battery(), self._read_memory(), self._read_storage(), self._read_cpu(), dynamic_pressure)

    @staticmethod
    def _dynamic_agent_pressure() -> float:
        raw = os.getenv("ADAAD_DYNAMIC_AGENT_PRESSURE", "0.0").strip()
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            _emit_probe_fallback(
                probe="dynamic_agent_pressure",
                reason_code="dynamic_agent_pressure_parse_error",
                fallback_value=0.0,
            )
            return 0.0

    @staticmethod
    def _read_battery() -> float:
        capacity_path = Path("/sys/class/power_supply/battery/capacity")
        try:
            reading = float(capacity_path.read_text(encoding="utf-8").strip())
            return max(0.0, min(100.0, reading))
        except OSError as exc:
            _emit_probe_fallback(
                probe="battery",
                reason_code="battery_probe_unreadable",
                fallback_value=100.0,
                source_path=str(capacity_path),
                error=exc,
            )
            return 100.0
        except ValueError as exc:
            _emit_probe_fallback(
                probe="battery",
                reason_code="battery_probe_parse_error",
                fallback_value=100.0,
                source_path=str(capacity_path),
                error=exc,
            )
            return 100.0

    @staticmethod
    def _read_memory() -> float:
        meminfo = Path("/proc/meminfo")
        try:
            lines = meminfo.read_text(encoding="utf-8").splitlines()
            available_kb = next(int(line.split()[1]) for line in lines if line.startswith("MemAvailable:"))
            return max(0.0, available_kb / 1024.0)
        except OSError as exc:
            _emit_probe_fallback(
                probe="memory",
                reason_code="meminfo_unreadable",
                fallback_value=8192.0,
                source_path=str(meminfo),
                error=exc,
            )
            return 8192.0
        except (StopIteration, IndexError, ValueError) as exc:
            _emit_probe_fallback(
                probe="memory",
                reason_code="meminfo_parse_error",
                fallback_value=8192.0,
                source_path=str(meminfo),
                error=exc,
            )
            return 8192.0

    def _read_storage(self) -> float:
        usage = os.statvfs(str(self.data_root))
        free_bytes = usage.f_bavail * usage.f_frsize
        return free_bytes / (1024.0 * 1024.0)

    @staticmethod
    def _read_cpu() -> float:
        try:
            load1, _, _ = os.getloadavg()
            cpus = os.cpu_count() or 1
            return max(0.0, min(100.0, (load1 / cpus) * 100.0))
        except OSError as exc:
            _emit_probe_fallback(
                probe="cpu",
                reason_code="cpu_probe_unavailable",
                fallback_value=0.0,
                error=exc,
            )
            return 0.0
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            _emit_probe_fallback(
                probe="cpu",
                reason_code="cpu_probe_parse_error",
                fallback_value=0.0,
                error=exc,
            )
            return 0.0


__all__ = ["ResourceSnapshot", "AndroidMonitor"]
