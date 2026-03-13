# SPDX-License-Identifier: Apache-2.0
"""
runtime.evolution.lineage — Lineage Engine (Phase 61)
======================================================
Lineage tracking, epistasis detection, niche speciation, and
cross-niche breeding for ADAAD's evolutionary substrate.

Invariants
----------
LINEAGE-STAB-0  Lineage stable iff ≥ 2/5 last epochs passed; else 1-epoch cool.
EPISTASIS-0     Epistatic pairs cooled EPISTASIS_COOLING_EPOCHS epochs.
"""

from runtime.evolution.lineage.lineage_node import (  # noqa: F401
    LineageNode,
    EpochOutcome,
    MutationNiche,
)
from runtime.evolution.lineage.compatibility_matrix import (  # noqa: F401
    CompatibilityMatrix,
    CoOccurrenceRecord,
    EPISTASIS_COOLING_EPOCHS,
)
from runtime.evolution.lineage.niche_registry import (  # noqa: F401
    NicheRegistry,
    NichePool,
    HybridCandidate,
)
from runtime.evolution.lineage.lineage_engine import (  # noqa: F401
    LineageEngine,
    EpochLineageSummary,
)

__all__ = [
    "LineageNode", "EpochOutcome", "MutationNiche",
    "CompatibilityMatrix", "CoOccurrenceRecord", "EPISTASIS_COOLING_EPOCHS",
    "NicheRegistry", "NichePool", "HybridCandidate",
    "LineageEngine", "EpochLineageSummary",
]
