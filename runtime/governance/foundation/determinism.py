# SPDX-License-Identifier: Apache-2.0
"""Deterministic runtime provider abstractions for clock and ID/token generation."""

from __future__ import annotations

import hashlib
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Protocol


_SHA256_HEX_WIDTH = 64


def _validate_identifier_length(*, method: str, length: int, max_length: int = _SHA256_HEX_WIDTH) -> None:
    if length <= 0:
        raise ValueError(f"{method}: invalid length={length}; expected 1..{max_length}")
    if length > max_length:
        raise ValueError(f"{method}: invalid length={length}; expected 1..{max_length}")


class RuntimeDeterminismProvider(Protocol):
    """Clock + entropy interface for replay-safe runtime behavior."""

    @property
    def deterministic(self) -> bool: ...

    def now_utc(self) -> datetime: ...

    def iso_now(self) -> str: ...

    def format_utc(self, fmt: str) -> str: ...

    def next_id(self, *, label: str = "id", length: int = 32) -> str: ...

    def next_token(self, *, label: str = "token", length: int = 16) -> str: ...

    def next_int(self, *, low: int, high: int, label: str = "int") -> int: ...


class SystemDeterminismProvider:
    """Default live provider (non-deterministic)."""

    deterministic = False

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def iso_now(self) -> str:
        return self.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")

    def format_utc(self, fmt: str) -> str:
        return self.now_utc().strftime(fmt)

    def next_id(self, *, label: str = "id", length: int = 32) -> str:
        _ = label
        _validate_identifier_length(method="next_id", length=length)
        return (uuid.uuid4().hex + uuid.uuid4().hex)[:length]

    def next_token(self, *, label: str = "token", length: int = 16) -> str:
        _ = label
        _validate_identifier_length(method="next_token", length=length)
        return (uuid.uuid4().hex + uuid.uuid4().hex)[:length]

    def next_int(self, *, low: int, high: int, label: str = "int") -> int:
        _ = label
        return random.randint(low, high)


class SeededDeterminismProvider:
    """Deterministic provider for strict replay and tests."""

    deterministic = True

    def __init__(self, seed: str, fixed_now: datetime | None = None) -> None:
        self.seed = str(seed)
        base = fixed_now or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._now = base.astimezone(timezone.utc)
        self._call_counts: dict[str, int] = {}

    def _digest(self, label: str) -> str:
        return hashlib.sha256(f"{self.seed}:{label}".encode("utf-8")).hexdigest()

    def _counted_digest(self, label: str) -> str:
        seq = self._call_counts.get(label, 0)
        self._call_counts[label] = seq + 1
        return hashlib.sha256(f"{self.seed}:{label}:{seq}".encode("utf-8")).hexdigest()

    def now_utc(self) -> datetime:
        return self._now

    def iso_now(self) -> str:
        return self._now.isoformat().replace("+00:00", "Z")

    def format_utc(self, fmt: str) -> str:
        return self._now.strftime(fmt)

    def next_id(self, *, label: str = "id", length: int = 32) -> str:
        _validate_identifier_length(method="next_id", length=length)
        return self._counted_digest(f"id:{label}")[:length]

    def next_token(self, *, label: str = "token", length: int = 16) -> str:
        _validate_identifier_length(method="next_token", length=length)
        return self._counted_digest(f"token:{label}")[:length]

    def next_int(self, *, low: int, high: int, label: str = "int") -> int:
        if low > high:
            raise ValueError("low must be <= high")
        span = high - low + 1
        value = int(self._counted_digest(f"int:{label}")[:16], 16)
        return low + (value % span)


def require_replay_safe_provider(
    provider: RuntimeDeterminismProvider,
    *,
    replay_mode: str = "off",
    recovery_tier: str | None = None,
) -> None:
    """Reject non-deterministic providers when strict replay determinism is mandatory.

    ``strict`` replay mode and governance-critical recovery tiers require
    deterministic providers so replay/audit evidence remains reproducible.

    Backward compatibility: ``audit`` remains accepted as an alias tier.
    """

    if (replay_mode or "off").strip().lower() == "strict" and not getattr(provider, "deterministic", False):
        raise RuntimeError("strict_replay_requires_deterministic_provider")
    normalized_tier = (recovery_tier or "").strip().lower()
    if normalized_tier in {"audit", "governance", "critical"} and not getattr(provider, "deterministic", False):
        raise RuntimeError("audit_tier_requires_deterministic_provider")


def default_provider() -> RuntimeDeterminismProvider:
    if os.getenv("ADAAD_FORCE_DETERMINISTIC_PROVIDER", "").strip().lower() in {"1", "true", "yes", "on"}:
        return SeededDeterminismProvider(seed=os.getenv("ADAAD_DETERMINISTIC_SEED", "adaad"))

    replay_mode = os.getenv("ADAAD_REPLAY_MODE", "").strip().lower()
    if replay_mode == "strict":
        seed = os.getenv("ADAAD_DETERMINISTIC_SEED", "").strip()
        if not seed:
            raise RuntimeError(
                "ADAAD_REPLAY_MODE=strict requires ADAAD_DETERMINISTIC_SEED to be set or a deterministic provider to be injected"
            )
        return SeededDeterminismProvider(seed=seed)

    return SystemDeterminismProvider()


__all__ = [
    "RuntimeDeterminismProvider",
    "SystemDeterminismProvider",
    "SeededDeterminismProvider",
    "default_provider",
    "require_replay_safe_provider",
]
