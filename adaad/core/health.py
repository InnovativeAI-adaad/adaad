# SPDX-License-Identifier: Apache-2.0
"""Minimal JSON health payload helper."""

from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Callable


Clock = Callable[[], _dt.datetime]


def _utc_now_iso_and_unix(clock: Clock | None = None) -> tuple[str, float]:
    """Return timestamp pair as (UTC ISO-8601, UNIX epoch seconds).

    A provider-backed ``clock`` can be supplied for replay-sensitive contexts.
    The provider must return an aware UTC ``datetime``.
    """
    now = clock() if clock else _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    now_utc = now.astimezone(_dt.timezone.utc)
    return now_utc.isoformat().replace("+00:00", "Z"), now_utc.timestamp()


def health_report(status: str = "ok", extra: dict | None = None, clock: Clock | None = None) -> str:
    """Build the JSON health payload.

    Contract:
    - ``status`` (str): service status marker.
    - ``timestamp_iso`` (str): canonical UTC ISO-8601 timestamp (e.g. ``2026-01-01T00:00:00Z``).
    - ``timestamp_unix`` (float): UNIX epoch seconds for compatibility.
    - ``timestamp`` (float): legacy alias of ``timestamp_unix`` for backwards compatibility.
    """
    timestamp_iso, timestamp_unix = _utc_now_iso_and_unix(clock=clock)
    payload: dict[str, object] = {
        "status": status,
        "timestamp_iso": timestamp_iso,
        "timestamp_unix": timestamp_unix,
        "timestamp": timestamp_unix,
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload)
