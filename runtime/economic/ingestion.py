# SPDX-License-Identifier: Apache-2.0
"""Economic ingestion pipeline contracts for AGM runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from runtime.economic.schema import MarketSignal, MarketSnapshot


class MarketIngestion:
    """Normalizes raw market payloads into typed snapshots."""

    def parse(self, *, snapshot_id: str, payloads: Iterable[dict[str, object]]) -> MarketSnapshot:
        signals: list[MarketSignal] = []
        for payload in payloads:
            source = str(payload.get("source", "unknown"))
            symbol = str(payload.get("symbol", "UNKNOWN"))
            value = float(payload.get("value", 0.0))
            observed_at = payload.get("observed_at")
            if isinstance(observed_at, datetime):
                ts = observed_at
            else:
                ts = datetime.now(tz=timezone.utc)
            tags = payload.get("tags")
            normalized_tags = tags if isinstance(tags, dict) else {}
            signals.append(
                MarketSignal(
                    source=source,
                    symbol=symbol,
                    value=value,
                    observed_at=ts,
                    tags={str(key): str(value) for key, value in normalized_tags.items()},
                )
            )
        return MarketSnapshot(snapshot_id=snapshot_id, signals=tuple(signals))
