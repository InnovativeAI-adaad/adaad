# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object in {path}")
    return payload


def canonical_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
