# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict

import logging

from runtime.constants import APONI_URL
from runtime.governance.foundation import RuntimeDeterminismProvider, default_provider, require_replay_safe_provider

LOG = logging.getLogger(__name__)

def _default_aponi_events_url() -> str:
    return f"{APONI_URL}/api/v1/events"


DEFAULT_APONI_URL = os.environ.get("APONI_API_URL", _default_aponi_events_url())
ERROR_LOG = Path("logs/aponi_sync_errors.log")

# Canonical Aponi transport error entry schema.
# required keys: ts, type, reason_code, error_class, error, payload
# allowed enum values:
#   - reason_code: aponi_transport_failed
#   - error_class: http_error | url_error | timeout_error | os_error | value_error
ERROR_REASON_CODE = "aponi_transport_failed"
ERROR_CLASSES = frozenset({"http_error", "url_error", "timeout_error", "os_error", "value_error"})
ERROR_ENTRY_KEYS = ("ts", "type", "reason_code", "error_class", "error", "payload")


def _error_class_for(exc: Exception) -> str:
    # Mapping order is intentional: HTTPError is a URLError subtype.
    if isinstance(exc, urllib.error.HTTPError):
        return "http_error"
    if isinstance(exc, urllib.error.URLError):
        return "url_error"
    if isinstance(exc, TimeoutError):
        return "timeout_error"
    if isinstance(exc, OSError):
        return "os_error"
    if isinstance(exc, ValueError):
        return "value_error"
    return "value_error"


def push_to_dashboard(
    event_type: str,
    data: Dict[str, object],
    *,
    provider: RuntimeDeterminismProvider | None = None,
) -> bool:
    runtime_provider = provider or default_provider()
    require_replay_safe_provider(
        runtime_provider,
        replay_mode=os.getenv("ADAAD_REPLAY_MODE", "off"),
        recovery_tier=os.getenv("ADAAD_RECOVERY_TIER"),
    )

    event_ts = runtime_provider.iso_now()
    payload = {"ts": event_ts, "type": event_type, "payload": data}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        DEFAULT_APONI_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=2) as resp:  # noqa: S310
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        error_class = _error_class_for(exc)
        entry = {
            "ts": event_ts,
            "type": event_type,
            "reason_code": ERROR_REASON_CODE,
            "error_class": error_class,
            "error": str(exc),
            "payload": data,
        }
        if entry["error_class"] not in ERROR_CLASSES:
            raise ValueError(f"Unsupported error_class: {entry['error_class']}")
        if tuple(entry.keys()) != ERROR_ENTRY_KEYS:
            raise ValueError("Aponi error entry schema drift detected")
        LOG.warning(
            "Aponi sync failed",
            extra={
                "reason_code": entry["reason_code"],
                "error_class": entry["error_class"],
                "event_type": event_type,
            },
        )
        with ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return False


__all__ = ["push_to_dashboard"]
