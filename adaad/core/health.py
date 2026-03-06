# SPDX-License-Identifier: Apache-2.0
"""Minimal JSON health payload helper.

PR #12 fix: gate_ok is now always included in the health payload.
gate_ok reflects whether the Gatekeeper governance gate has passed.
Defaults to True for backward compatibility; Orchestrator overrides
via the extra dict when gate status is known.
"""

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


def health_report(
    status: str = "ok",
    extra: dict | None = None,
    clock: Clock | None = None,
    gate_ok: bool = True,
) -> str:
    """Build the JSON health payload.

    Contract:
    - ``status`` (str): service status marker.
    - ``gate_ok`` (bool): Gatekeeper governance gate result.  Always present
      in payload (PR #12 fix).  Defaults to True; Orchestrator sets this from
      actual gate evaluation result.
    - ``timestamp_iso`` (str): canonical UTC ISO-8601 timestamp.
    - ``timestamp_unix`` (float): UNIX epoch seconds for compatibility.
    - ``timestamp`` (float): legacy alias of ``timestamp_unix``.
    """
    timestamp_iso, timestamp_unix = _utc_now_iso_and_unix(clock=clock)
    payload: dict[str, object] = {
        "status":        status,
        "gate_ok":       gate_ok,   # PR #12 — always present
        "timestamp_iso": timestamp_iso,
        "timestamp_unix": timestamp_unix,
        "timestamp":     timestamp_unix,
    }
    if extra:
        # extra may override gate_ok — Orchestrator injects real gate result
        payload.update(extra)
    return json.dumps(payload)
