# SPDX-License-Identifier: Apache-2.0
"""Tests for MarketIngestion deterministic timestamp enforcement."""

from datetime import datetime, timedelta, timezone

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.economic.ingestion import MarketIngestion, MarketIngestionError

_UTC = timezone.utc


def test_accepts_datetime_observed_at() -> None:
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=_UTC)
    snapshot = MarketIngestion().parse(
        snapshot_id="s1",
        payloads=[{"source": "appstore", "symbol": "REVENUE", "value": 1.0, "observed_at": ts}],
    )
    assert len(snapshot.signals) == 1
    assert snapshot.signals[0].observed_at == ts


def test_accepts_iso8601_string_observed_at() -> None:
    snapshot = MarketIngestion().parse(
        snapshot_id="s2",
        payloads=[{"source": "analytics", "symbol": "DAU", "value": 500.0, "observed_at": "2026-03-01T00:00:00Z"}],
    )
    assert snapshot.signals[0].observed_at.year == 2026
    assert snapshot.signals[0].observed_at.tzinfo is not None


def test_raises_on_missing_observed_at() -> None:
    with pytest.raises(MarketIngestionError, match="missing_observed_at"):
        MarketIngestion().parse(snapshot_id="s3", payloads=[{"source": "x", "symbol": "Y", "value": 1.0}])


def test_raises_on_invalid_string_observed_at() -> None:
    with pytest.raises(MarketIngestionError, match="invalid_observed_at_format"):
        MarketIngestion().parse(
            snapshot_id="s5",
            payloads=[{"source": "x", "symbol": "Y", "value": 1.0, "observed_at": "not-a-date"}],
        )


def test_raises_on_naive_datetime_observed_at() -> None:
    naive_ts = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.raises(MarketIngestionError, match="observed_at_missing_timezone"):
        MarketIngestion().parse(
            snapshot_id="s8",
            payloads=[{"source": "x", "symbol": "Y", "value": 1.0, "observed_at": naive_ts}],
        )


def test_raises_on_naive_string_observed_at() -> None:
    with pytest.raises(MarketIngestionError, match="observed_at_missing_timezone"):
        MarketIngestion().parse(
            snapshot_id="s9",
            payloads=[{"source": "x", "symbol": "Y", "value": 1.0, "observed_at": "2026-03-01T12:00:00"}],
        )


def test_non_utc_offset_is_normalized_to_utc() -> None:
    tz_plus5 = timezone(timedelta(hours=5))
    ts_local = datetime(2026, 3, 1, 17, 0, 0, tzinfo=tz_plus5)
    expected_utc = datetime(2026, 3, 1, 12, 0, 0, tzinfo=_UTC)
    snapshot = MarketIngestion().parse(
        snapshot_id="s10",
        payloads=[{"source": "x", "symbol": "Y", "value": 1.0, "observed_at": ts_local}],
    )
    assert snapshot.signals[0].observed_at == expected_utc
    assert snapshot.signals[0].observed_at.utcoffset() == timedelta(0)
