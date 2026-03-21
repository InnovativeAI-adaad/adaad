# SPDX-License-Identifier: Apache-2.0
"""Phase 85 Track D — Noah Governance Incident tests. NOAH-01..04

Because even the joke gets tested. This is ADAAD.
"""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.phase85_d


def test_noah_incident_log_present():
    """NOAH-01: README contains the Noah incident log."""
    readme = (ROOT / "README.md").read_text()
    assert "DEVLOG-NOAH" in readme
    assert "hypnosis_protocol_failure" in readme


def test_noah_does_not_bypass_human0():
    """NOAH-02: incident log references HUMAN-0 as inviolable."""
    readme = (ROOT / "README.md").read_text()
    start = readme.find("DEVLOG-NOAH")
    section = readme[start:start+2000]
    assert "HUMAN-0" in section


def test_noah_rehire_probability_always():
    """NOAH-03: rehire_probability must be always. Non-negotiable."""
    assert "rehire_probability: always" in (ROOT / "README.md").read_text()


def test_noah_vibes_immaculate():
    """NOAH-04: vibes: immaculate is a constitutional constant."""
    assert "vibes: immaculate" in (ROOT / "README.md").read_text()
