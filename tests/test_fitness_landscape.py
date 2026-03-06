# SPDX-License-Identifier: Apache-2.0
"""Test suite for runtime/autonomy/fitness_landscape.py"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from runtime.autonomy.fitness_landscape import FitnessLandscape, TypeRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_landscape(tmp_path):
    return FitnessLandscape(state_path=tmp_path / "landscape.json")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_record_wins_and_losses(tmp_landscape) -> None:
    for _ in range(7):
        tmp_landscape.record("structural", won=True)
    for _ in range(3):
        tmp_landscape.record("structural", won=False)
    rec = tmp_landscape._records["structural"]
    assert rec.wins == 7
    assert rec.losses == 3
    assert rec.win_rate == pytest.approx(0.7)


def test_plateau_declared_all_below_threshold(tmp_landscape) -> None:
    for _ in range(5):
        tmp_landscape.record("structural",   won=False)
        tmp_landscape.record("performance",  won=False)
        tmp_landscape.record("experimental", won=False)
    assert tmp_landscape.is_plateau() is True


def test_no_plateau_on_sparse_data(tmp_landscape) -> None:
    # Only 2 attempts per type — below min_attempts=3 guard
    tmp_landscape.record("structural", won=False)
    tmp_landscape.record("structural", won=False)
    assert tmp_landscape.is_plateau() is False


def test_recommended_agent_dream_on_plateau(tmp_landscape) -> None:
    for _ in range(5):
        tmp_landscape.record("structural", won=False)
    assert tmp_landscape.recommended_agent() == "dream"


def test_recommended_agent_architect_on_structural_win(tmp_landscape) -> None:
    for _ in range(5):
        tmp_landscape.record("structural", won=True)
    assert tmp_landscape.recommended_agent() == "architect"


def test_persistence_roundtrip(tmp_path) -> None:
    path = tmp_path / "landscape.json"
    landscape1 = FitnessLandscape(state_path=path)
    for _ in range(4):
        landscape1.record("performance", won=True)
    landscape2 = FitnessLandscape(state_path=path)
    assert landscape2._records["performance"].wins == 4
