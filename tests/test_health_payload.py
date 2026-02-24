# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import datetime as dt
import json

import pytest

from adaad.core.health import health_report


def test_health_report_contract_and_backward_compatibility() -> None:
    fixed = dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)

    payload = json.loads(health_report(extra={"a": 1}, clock=lambda: fixed))

    assert payload["status"] == "ok"
    assert payload["timestamp_iso"] == "2026-01-01T00:00:00Z"
    assert payload["timestamp_unix"] == pytest.approx(1767225600.0)
    assert payload["timestamp"] == pytest.approx(payload["timestamp_unix"])
    assert payload["a"] == 1


def test_health_report_timestamp_iso_uses_utc_z_suffix() -> None:
    offset_clock = lambda: dt.datetime(2026, 1, 1, 5, 30, 0, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))

    payload = json.loads(health_report(clock=offset_clock))

    assert payload["timestamp_iso"] == "2026-01-01T00:00:00Z"


def test_health_report_rejects_naive_clock() -> None:
    naive_clock = lambda: dt.datetime(2026, 1, 1, 0, 0, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        health_report(clock=naive_clock)
