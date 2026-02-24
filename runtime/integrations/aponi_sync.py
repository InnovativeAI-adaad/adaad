from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict

import logging

from runtime.governance.foundation import RuntimeDeterminismProvider, default_provider, require_replay_safe_provider

LOG = logging.getLogger(__name__)

DEFAULT_APONI_URL = os.environ.get("APONI_API_URL", "http://localhost:5000/api/v1/events")
ERROR_LOG = Path("logs/aponi_sync_errors.log")


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
        entry = {
            "ts": event_ts,
            "type": event_type,
            "reason_code": "aponi_transport_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "payload": data,
        }
        LOG.warning(
            "Aponi sync failed",
            extra={
                "reason_code": entry["reason_code"],
                "error_type": entry["error_type"],
                "event_type": event_type,
            },
        )
        with ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return False


__all__ = ["push_to_dashboard"]
