# SPDX-License-Identifier: Apache-2.0
"""Structured audit-event writer for warnings/errors/governance diagnostics."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Mapping

import fcntl

from runtime import ROOT_DIR

AUDIT_LOG_PATH = ROOT_DIR / "reports" / "audit_events.jsonl"
_DEFAULT_COMPONENT = "runtime"

_SENSITIVE_KEY_MARKERS = (
    "token",
    "secret",
    "password",
    "credential",
    "signature",
    "api_key",
    "private_key",
    "authorization",
)

_THREAD_LOCK = threading.Lock()


class _FileLock:
    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._fd: int | None = None

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


def _is_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS)


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            text_key = str(key)
            if _is_sensitive_key(text_key):
                sanitized[text_key] = "[REDACTED]"
                continue
            sanitized[text_key] = _sanitize(nested)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize(item) for item in value)
    return value


def _audit_path() -> Path:
    configured = os.getenv("ADAAD_AUDIT_JSONL_PATH", "").strip()
    return Path(configured) if configured else AUDIT_LOG_PATH


def emit_structured_event(
    *,
    component: str,
    event_type: str,
    severity: str,
    correlation_id: str,
    invariant: str | None = None,
    gate: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one standardized structured event as a JSONL record."""

    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "component": component or _DEFAULT_COMPONENT,
        "event_type": event_type,
        "correlation_id": correlation_id,
        "severity": severity.upper(),
        "governance_context": {
            "invariant": invariant,
            "gate": gate,
        },
        "payload": _sanitize(dict(payload or {})),
    }

    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    lock_path = path.with_suffix(path.suffix + ".lock")

    with _THREAD_LOCK:
        with _FileLock(lock_path):
            fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
    return record


def emit_warning(*, component: str, event_type: str, correlation_id: str, invariant: str | None = None, gate: str | None = None, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return emit_structured_event(
        component=component,
        event_type=event_type,
        severity="WARNING",
        correlation_id=correlation_id,
        invariant=invariant,
        gate=gate,
        payload=payload,
    )


def emit_error(*, component: str, event_type: str, correlation_id: str, invariant: str | None = None, gate: str | None = None, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return emit_structured_event(
        component=component,
        event_type=event_type,
        severity="ERROR",
        correlation_id=correlation_id,
        invariant=invariant,
        gate=gate,
        payload=payload,
    )


def emit_governance_diagnostic(*, component: str, event_type: str, correlation_id: str, severity: str = "INFO", invariant: str | None = None, gate: str | None = None, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return emit_structured_event(
        component=component,
        event_type=event_type,
        severity=severity,
        correlation_id=correlation_id,
        invariant=invariant,
        gate=gate,
        payload=payload,
    )


__all__ = [
    "AUDIT_LOG_PATH",
    "emit_error",
    "emit_governance_diagnostic",
    "emit_structured_event",
    "emit_warning",
]
