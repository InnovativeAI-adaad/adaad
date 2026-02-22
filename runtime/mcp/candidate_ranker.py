# SPDX-License-Identifier: Apache-2.0
"""Deterministic candidate ranking for proposal ids."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List


def _score_from_id(mutation_id: str) -> float:
    digest = hashlib.sha256(mutation_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def rank_candidates(mutation_ids: List[str]) -> Dict[str, Any]:
    if not mutation_ids:
        raise ValueError("empty_candidates")
    scored = [{"mutation_id": mid, "score": round(_score_from_id(mid), 6)} for mid in mutation_ids]
    scored.sort(key=lambda item: (-item["score"], item["mutation_id"]))
    return {"ranked": scored}


__all__ = ["rank_candidates"]
