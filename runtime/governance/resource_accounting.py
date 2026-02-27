# SPDX-License-Identifier: Apache-2.0
"""Deterministic resource accounting helpers shared across governance and sandboxing."""

from __future__ import annotations

from typing import Any, Mapping


def _parse_non_negative(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed < 0:
        return 0.0
    return parsed


def normalize_resource_usage_snapshot(
    *,
    cpu_seconds: Any = 0.0,
    memory_mb: Any = 0.0,
    wall_seconds: Any = 0.0,
    disk_mb: Any = 0.0,
) -> dict[str, float]:
    """Return a canonical usage snapshot with stable rounding and aliases."""

    normalized = {
        "cpu_seconds": round(_parse_non_negative(cpu_seconds), 4),
        "memory_mb": round(_parse_non_negative(memory_mb), 4),
        "wall_seconds": round(_parse_non_negative(wall_seconds), 4),
        "disk_mb": round(_parse_non_negative(disk_mb), 4),
    }
    normalized["duration_s"] = normalized["wall_seconds"]
    return normalized


def normalize_platform_telemetry_snapshot(
    *,
    memory_mb: Any = 0.0,
    cpu_percent: Any = 0.0,
    battery_percent: Any = 0.0,
    storage_mb: Any = 0.0,
) -> dict[str, float]:
    """Return canonical platform telemetry values for deterministic envelope state."""

    cpu = round(min(100.0, _parse_non_negative(cpu_percent)), 4)
    battery = round(min(100.0, _parse_non_negative(battery_percent)), 4)
    return {
        "memory_mb": round(_parse_non_negative(memory_mb), 4),
        "cpu_percent": cpu,
        "battery_percent": battery,
        "storage_mb": round(_parse_non_negative(storage_mb), 4),
    }


def merge_platform_telemetry(*, observed: Mapping[str, Any], android: Mapping[str, Any]) -> dict[str, float]:
    """Merge sandbox and Android telemetry into a single deterministic snapshot.

    Precedence semantics are intentionally conservative:
    - memory_mb/cpu_percent use max(...): keep the worst observed pressure signal.
    - battery_percent/storage_mb use min(...): keep the most constrained mobile context.
    """

    observed_normalized = normalize_platform_telemetry_snapshot(
        memory_mb=observed.get("memory_mb"),
        cpu_percent=observed.get("cpu_percent"),
        battery_percent=observed.get("battery_percent"),
        storage_mb=observed.get("storage_mb"),
    )
    android_normalized = normalize_platform_telemetry_snapshot(
        memory_mb=android.get("memory_mb"),
        cpu_percent=android.get("cpu_percent"),
        battery_percent=android.get("battery_percent"),
        storage_mb=android.get("storage_mb"),
    )
    return {
        "memory_mb": round(max(observed_normalized["memory_mb"], android_normalized["memory_mb"]), 4),
        "cpu_percent": round(max(observed_normalized["cpu_percent"], android_normalized["cpu_percent"]), 4),
        "battery_percent": round(min(observed_normalized["battery_percent"], android_normalized["battery_percent"]), 4),
        "storage_mb": round(min(observed_normalized["storage_mb"], android_normalized["storage_mb"]), 4),
    }


def coalesce_resource_usage_snapshot(*, observed: Mapping[str, Any], telemetry: Mapping[str, Any]) -> dict[str, float]:
    """Resolve deterministic resource usage from observed measurements with telemetry fallback."""

    observed_peak = _parse_non_negative(observed.get("peak_rss_mb"))
    observed_memory = _parse_non_negative(observed.get("memory_mb"))
    telemetry_memory = _parse_non_negative(telemetry.get("memory_mb"))
    memory_mb = max(observed_peak, observed_memory) if max(observed_peak, observed_memory) > 0.0 else telemetry_memory
    cpu_seconds = max(
        _parse_non_negative(observed.get("cpu_seconds")),
        _parse_non_negative(observed.get("cpu_time_seconds")),
    )
    wall_seconds = max(
        _parse_non_negative(observed.get("wall_seconds")),
        _parse_non_negative(observed.get("wall_time_seconds")),
        _parse_non_negative(observed.get("duration_s")),
    )
    disk_mb = _parse_non_negative(observed.get("disk_mb"))
    return normalize_resource_usage_snapshot(
        cpu_seconds=cpu_seconds,
        memory_mb=memory_mb,
        wall_seconds=wall_seconds,
        disk_mb=disk_mb,
    )


__all__ = [
    "coalesce_resource_usage_snapshot",
    "merge_platform_telemetry",
    "normalize_platform_telemetry_snapshot",
    "normalize_resource_usage_snapshot",
]
