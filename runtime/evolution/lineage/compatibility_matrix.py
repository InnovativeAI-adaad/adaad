# SPDX-License-Identifier: Apache-2.0
"""
runtime.evolution.lineage.compatibility_matrix
===============================================
CompatibilityMatrix — co-occurrence tracking and epistasis detection.

Epistasis (EPISTASIS-0): when mutation A and B individually pass governance
but their combination (A applied before B) causes a test regression that
neither caused alone, the pair is flagged as epistatic.

The matrix records every co-occurring mutation pair per epoch and their
joint outcome. An epistatic pair is blacklisted from co-submission for
EPISTASIS_COOLING_EPOCHS epochs.

Invariants
----------
EPISTASIS-0  Epistatic pairs detected and cooled for EPISTASIS_COOLING_EPOCHS.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


EPISTASIS_COOLING_EPOCHS: int = 3


@dataclass
class CoOccurrenceRecord:
    """Record of two mutations applied in the same epoch.

    Attributes
    ----------
    patch_a         patch_hash of first mutation (lexicographically first).
    patch_b         patch_hash of second mutation.
    epoch_id        Epoch identifier string.
    a_passed_alone  Whether A passed governance when submitted alone.
    b_passed_alone  Whether B passed governance when submitted alone.
    joint_passed    Whether both passed when applied together.
    epistatic       True if joint regression detected (EPISTASIS-0).
    """
    patch_a: str
    patch_b: str
    epoch_id: str
    a_passed_alone: bool
    b_passed_alone: bool
    joint_passed: bool
    epistatic: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "CoOccurrenceRecord":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})


class CompatibilityMatrix:
    """Tracks mutation co-occurrence and detects epistasis (EPISTASIS-0).

    Usage
    -----
    matrix = CompatibilityMatrix()
    matrix.record(patch_a_hash, patch_b_hash, epoch_id,
                  a_alone=True, b_alone=True, joint=False)
    blocked = matrix.is_epistatic_pair(patch_a_hash, patch_b_hash)
    """

    def __init__(self) -> None:
        self._records: List[CoOccurrenceRecord] = []
        # pair_key → epoch_id list when epistasis first recorded
        self._epistatic_pairs: Dict[FrozenSet[str], List[str]] = {}
        self._cooling_counters: Dict[FrozenSet[str], int] = {}

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        patch_a: str,
        patch_b: str,
        epoch_id: str,
        a_passed_alone: bool,
        b_passed_alone: bool,
        joint_passed: bool,
    ) -> CoOccurrenceRecord:
        """Record a co-occurrence event; detect epistasis if applicable."""
        a, b = sorted([patch_a, patch_b])  # canonical order
        epistatic = (
            a_passed_alone
            and b_passed_alone
            and not joint_passed
        )
        rec = CoOccurrenceRecord(
            patch_a=a,
            patch_b=b,
            epoch_id=epoch_id,
            a_passed_alone=a_passed_alone,
            b_passed_alone=b_passed_alone,
            joint_passed=joint_passed,
            epistatic=epistatic,
        )
        self._records.append(rec)

        if epistatic:
            pair = frozenset([a, b])
            self._epistatic_pairs.setdefault(pair, []).append(epoch_id)
            self._cooling_counters[pair] = EPISTASIS_COOLING_EPOCHS

        return rec

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_epistatic_pair(self, patch_a: str, patch_b: str) -> bool:
        """Return True if pair is currently in epistasis cooling."""
        pair = frozenset([patch_a, patch_b])
        return self._cooling_counters.get(pair, 0) > 0

    def advance_epoch(self) -> None:
        """Decrement all epistasis cooling counters by 1."""
        expired = []
        for pair, counter in self._cooling_counters.items():
            self._cooling_counters[pair] = counter - 1
            if self._cooling_counters[pair] <= 0:
                expired.append(pair)
        for pair in expired:
            del self._cooling_counters[pair]

    def epistatic_pairs(self) -> List[FrozenSet[str]]:
        """Return all pairs currently in epistasis cooling."""
        return list(self._cooling_counters.keys())

    def co_occurrence_count(self, patch_a: str, patch_b: str) -> int:
        """Return total times patch_a and patch_b co-occurred."""
        pair = frozenset([patch_a, patch_b])
        return sum(
            1 for r in self._records
            if frozenset([r.patch_a, r.patch_b]) == pair
        )

    def epistasis_count(self) -> int:
        return sum(1 for r in self._records if r.epistatic)

    def matrix_hash(self) -> str:
        """Deterministic hash of all records."""
        state = json.dumps(
            [r.to_dict() for r in self._records],
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(state.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "records": [r.to_dict() for r in self._records],
            "cooling_counters": {
                json.dumps(sorted(list(k))): v
                for k, v in self._cooling_counters.items()
            },
            "matrix_hash": self.matrix_hash(),
        }
