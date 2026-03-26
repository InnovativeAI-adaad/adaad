# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Centralized JSONL metrics writer.

Payload sensitivity rules:
- Never log raw environment variables, secrets, tokens, credentials, or full
  command lines that may embed sensitive values.
- Prefer minimal, allowlisted fields and coarse metadata (counts, booleans,
  status, durations) over raw process/user context.
- All writes are serialized with a process lock and written as a single UTF-8
  encoded append operation to keep JSONL records line-atomic under
  thread/process concurrency.
"""

import json
import os
import sys
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fcntl

from runtime import ROOT_DIR

ELEMENT_ID = "Earth"

METRICS_PATH = ROOT_DIR / "reports" / "metrics.jsonl"
_THREAD_LOCK = threading.Lock()
_BILLING_LOCK = threading.Lock()


BILLABLE_EVENT_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "active_users": {
        "unit": "users",
        "description": "Unique active user identities observed in API requests.",
    },
    "active_seats": {
        "unit": "seats",
        "description": "Unique seat identifiers observed in API requests.",
    },
    "mutation_epochs_executed": {
        "unit": "events",
        "description": "Successful mutation-epoch execution requests accepted by API surfaces.",
    },
    "replay_verifications": {
        "unit": "events",
        "description": "Successful replay-verification requests served by audit APIs.",
    },
    "governance_approvals": {
        "unit": "events",
        "description": "Successful governance-approval proposal submissions.",
    },
}
_BILLABLE_COUNTS: Dict[str, int] = {name: 0 for name in BILLABLE_EVENT_DEFINITIONS}
_ACTIVE_USERS: set[str] = set()
_ACTIVE_SEATS: set[str] = set()


# ---------------------------------------------------------------------------
# MetricsSink abstraction (Phase 67 / Phase 3 metrics fan-out)
# ---------------------------------------------------------------------------

class MetricsSink(ABC):
    """Abstract base for metrics output backends."""
    @abstractmethod
    def emit(self, record: "Dict[str, Any]") -> None:
        """Emit a single structured metrics record."""


class JsonlSink(MetricsSink):
    """Appends records to METRICS_PATH as line-delimited JSON (default backend)."""
    def __init__(self, path: "Path | None" = None) -> None:
        self._path = path or METRICS_PATH

    def emit(self, record: "Dict[str, Any]") -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        with _FileLock(lock_path):
            fd = os.open(self._path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)


class StdoutSink(MetricsSink):
    """Writes records as JSON lines to stdout (activated via ADAAD_METRICS_STDOUT=1)."""
    def emit(self, record: "Dict[str, Any]") -> None:
        print(json.dumps(record, ensure_ascii=False), file=sys.stdout, flush=True)


class OpenTelemetrySink(MetricsSink):
    """Optional OTel export sink — silently no-ops if opentelemetry is not installed.

    Activated by ADAAD_METRICS_OTEL=1. Requires the opentelemetry-api package.
    Counter name: adaad.metrics.events; attributes: event, level, element.
    """
    def __init__(self) -> None:
        self._counter = None
        try:
            from opentelemetry import metrics as otel_metrics  # type: ignore[import]
            meter = otel_metrics.get_meter("adaad.runtime.metrics")
            self._counter = meter.create_counter(
                "adaad.metrics.events",
                description="Count of ADAAD governance metrics events",
            )
        except Exception:  # noqa: BLE001
            pass

    def emit(self, record: "Dict[str, Any]") -> None:
        if self._counter is None:
            return
        try:
            self._counter.add(1, attributes={
                "event": record.get("event", "unknown"),
                "level": record.get("level", "INFO"),
                "element": record.get("element", ELEMENT_ID),
            })
        except Exception:  # noqa: BLE001
            pass


def _is_truthy(val: str) -> bool:
    return val.strip().lower() in {"1", "true", "yes", "on"}


_sinks: "List[MetricsSink] | None" = None
_sinks_lock = threading.Lock()


def get_active_sinks() -> "List[MetricsSink]":
    """Return the ordered list of active sinks. Initialised lazily on first call."""
    global _sinks
    if _sinks is None:
        with _sinks_lock:
            if _sinks is None:
                active: List[MetricsSink] = [JsonlSink()]
                if _is_truthy(os.environ.get("ADAAD_METRICS_STDOUT", "")):
                    active.append(StdoutSink())
                if _is_truthy(os.environ.get("ADAAD_METRICS_OTEL", "")):
                    active.append(OpenTelemetrySink())
                _sinks = active
    else:
        with _sinks_lock:
            if _sinks and isinstance(_sinks[0], JsonlSink):
                if _sinks[0]._path != METRICS_PATH:  # type: ignore[attr-defined]
                    updated = list(_sinks)
                    updated[0] = JsonlSink()
                    _sinks = updated
    return _sinks


def _set_sinks(sinks: "List[MetricsSink]") -> None:
    """Replace active sinks — for test isolation only."""
    global _sinks
    with _sinks_lock:
        _sinks = sinks


def register_billable_usage(
    *,
    event_name: str,
    quantity: int = 1,
    user_id: str = "",
    seat_id: str = "",
) -> None:
    """Register a billable usage event and active actor cardinality.

    Unknown event names are ignored to preserve fail-safe request handling.
    """
    if quantity <= 0:
        return
    with _BILLING_LOCK:
        if user_id.strip():
            _ACTIVE_USERS.add(user_id.strip())
            _BILLABLE_COUNTS["active_users"] = len(_ACTIVE_USERS)
        if seat_id.strip():
            _ACTIVE_SEATS.add(seat_id.strip())
            _BILLABLE_COUNTS["active_seats"] = len(_ACTIVE_SEATS)
        if event_name in _BILLABLE_COUNTS:
            _BILLABLE_COUNTS[event_name] += int(quantity)


def billable_usage_snapshot() -> Dict[str, Any]:
    """Return a deterministic snapshot of billable counters."""
    with _BILLING_LOCK:
        counts = dict(_BILLABLE_COUNTS)
        active_user_ids = sorted(_ACTIVE_USERS)
        active_seat_ids = sorted(_ACTIVE_SEATS)
    return {
        "event_definitions": BILLABLE_EVENT_DEFINITIONS,
        "counters": counts,
        "active_user_ids": active_user_ids,
        "active_seat_ids": active_seat_ids,
    }


def reset_billable_usage() -> None:
    """Reset all in-memory billable counters (test-only utility)."""
    with _BILLING_LOCK:
        _ACTIVE_USERS.clear()
        _ACTIVE_SEATS.clear()
        for key in _BILLABLE_COUNTS:
            _BILLABLE_COUNTS[key] = 0


class _FileLock:
    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._fd: Optional[int] = None

    def __enter__(self) -> "_FileLock":
        self._fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None


def _ensure_metrics_file() -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not METRICS_PATH.exists():
        METRICS_PATH.touch()


def log(
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
    level: str = "INFO",
    element_id: Optional[str] = None,
) -> None:
    """Append a structured metrics record to all active MetricsSinks."""
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event_type,
        "level": level,
        "element": element_id or ELEMENT_ID,
        "payload": payload or {},
    }
    with _THREAD_LOCK:
        for sink in get_active_sinks():
            try:
                sink.emit(record)
            except Exception:  # noqa: BLE001
                # Never let a sink failure propagate — metrics are observability,
                # not control flow. The JSONL sink is always first; if it fails,
                # subsequent sinks still run.
                pass


def line_count() -> int:
    """Return the current total number of lines written to the metrics file.

    Used by test harnesses to compute an exact before/after delta without being
    constrained by the tail() limit cap.
    """
    _ensure_metrics_file()
    try:
        return sum(1 for _ in METRICS_PATH.open("rb") if _ != b"\n")
    except OSError:
        return 0


def tail_after(baseline: int, limit: int = 500) -> List[Dict[str, Any]]:
    """Return all entries appended after *baseline* line count.

    More reliable than ``observed[baseline:]`` when the file already has more
    than *limit* lines at baseline time.
    """
    _ensure_metrics_file()
    try:
        all_lines = METRICS_PATH.read_bytes().splitlines()
    except OSError:
        return []
    new_lines = all_lines[baseline:]
    entries: List[Dict[str, Any]] = []
    for raw in new_lines[-limit:]:
        try:
            entries.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return entries


def tail(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Return the most recent entries from the metrics log.
    """
    _ensure_metrics_file()
    raw_lines, _ = _read_last_lines(METRICS_PATH, limit)
    entries: List[Dict[str, Any]] = []
    for line in raw_lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _read_last_lines(path: Path, limit: int, chunk_size: int = 4096) -> Tuple[List[str], int]:
    """
    Read only the last `limit` lines from a UTF-8 file without loading it fully
    into memory. Returns the decoded lines (newlines stripped) and the number of
    bytes read to satisfy the request.
    """
    decoded: List[str] = []
    bytes_read = 0
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        buffer = b""
        lines_found = 0
        position = handle.tell()
        while position > 0 and lines_found < limit + 1:
            step = min(chunk_size, position)
            position -= step
            handle.seek(position)
            chunk = handle.read(step)
            bytes_read += len(chunk)
            buffer = chunk + buffer
            lines_found = buffer.count(b"\n")
            if lines_found >= limit + 1:
                break

    if buffer:
        decoded = [line.decode("utf-8", errors="ignore") for line in buffer.splitlines()[-limit:]]
    return decoded, bytes_read
