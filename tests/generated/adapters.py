# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvidenceLayout:
    """Deterministic paths used by generated-artifact CI lanes."""

    fixture: str
    evidence_root: Path
    reports_root: Path

    @property
    def fixture_evidence(self) -> Path:
        return self.evidence_root / self.fixture

    @property
    def fixture_reports(self) -> Path:
        return self.reports_root / self.fixture
