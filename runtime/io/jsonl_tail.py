# SPDX-License-Identifier: Apache-2.0
"""Bounded JSONL tail reader utilities."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JSONLTailReadResult:
    records: list[dict[str, Any]]
    bytes_read: int


def read_jsonl_tail(path: Path, *, limit: int, chunk_size: int = 4096) -> JSONLTailReadResult:
    """Read at most the last ``limit`` JSON objects from ``path``.

    The implementation seeks from the end of the file and reads only enough
    bytes to satisfy the request.
    """
    if limit <= 0 or not path.exists():
        return JSONLTailReadResult(records=[], bytes_read=0)

    buffer = b""
    bytes_read = 0
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        while position > 0:
            if buffer.count(b"\n") >= limit + 1:
                break
            step = min(chunk_size, position)
            position -= step
            handle.seek(position)
            chunk = handle.read(step)
            bytes_read += len(chunk)
            buffer = chunk + buffer

    records: list[dict[str, Any]] = []
    for raw_line in buffer.splitlines()[-limit:]:
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)

    return JSONLTailReadResult(records=records, bytes_read=bytes_read)
