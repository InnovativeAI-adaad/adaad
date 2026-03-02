"""Immutable append-only mutation ledger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LedgerEntry:
    variant_id: str
    seed: int
    metrics: dict[str, float]
    promoted: bool

    def serialized(self) -> str:
        return json.dumps(
            {
                "variant_id": self.variant_id,
                "seed": self.seed,
                "metrics": self.metrics,
                "promoted": self.promoted,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def sha256(self) -> str:
        return hashlib.sha256(self.serialized().encode("utf-8")).hexdigest()


class MutationLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(self, entry: LedgerEntry) -> str:
        digest = entry.sha256()
        payload = {"entry": json.loads(entry.serialized()), "hash": digest}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return digest

    def entries(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
