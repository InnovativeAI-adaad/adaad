# SPDX-License-Identifier: Apache-2.0
"""Typed schemas for runtime market/economic ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class MarketSignal:
    source: str
    symbol: str
    value: float
    observed_at: datetime
    tags: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketSnapshot:
    snapshot_id: str
    signals: tuple[MarketSignal, ...]

    @property
    def mean_value(self) -> float:
        if not self.signals:
            return 0.0
        return sum(signal.value for signal in self.signals) / len(self.signals)
