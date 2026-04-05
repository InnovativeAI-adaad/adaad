# SPDX-License-Identifier: Apache-2.0
"""Phase 122 — README Credibility + ROADMAP Sync acceptance tests.

T122-CRED-01..30  (30/30)
pytest mark: phase122
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.phase122

REPO_ROOT = Path(__file__).parent.parent
README = REPO_ROOT / "README.md"
ROADMAP = REPO_ROOT / "ROADMAP.md"
VERIFIABLE_CLAIMS = REPO_ROOT / "docs" / "VERIFIABLE_CLAIMS.md"
VERSION_FILE = REPO_ROOT / "VERSION"
PYPROJECT = REPO_ROOT / "pyproject.toml"
AGENT_STATE = REPO_ROOT / ".adaad_agent_state.json"
REPORT_VERSION = REPO_ROOT / "governance" / "report_version.json"


# ── README: world-first removal ──────────────────────────────────────────────

def test_T122_CRED_01_no_world_first_in_readme():
    """T122-CRED-01: README contains zero 'world-first' instances."""
    text = README.read_text()
    matches = re.findall(r"world.first", text, re.IGNORECASE)
    assert matches == [], f"Found {len(matches)} 'world-first' instance(s): {matches}"


def test_T122_CRED_02_no_worlds_first_in_readme():
    """T122-CRED-02: README contains no \"world's first\" phrasing."""
    text = README.read_text()
    assert "world's first" not in text.lower()


# ── README: version and invariant currency ───────────────────────────────────

def test_T122_CRED_03_hero_alt_text_not_stale():
    """T122-CRED-03: Hero alt text does not reference v9.48.0 or earlier stale versions."""
    text = README.read_text()
    assert "v9.48.0" not in text
    assert "115 Phases" not in text


def test_T122_CRED_04_invariant_count_162():
    """T122-CRED-04: README references 162 Hard-class invariants (not 125)."""
    text = README.read_text()
    assert "162" in text
    assert "125 Hard-class" not in text
    assert "125 invariants" not in text


def test_T122_CRED_05_no_internal_phase_batch_labels():
    """T122-CRED-05: README does not expose internal 'INNOV-NN' batch identifiers in section headers."""
    text = README.read_text()
    # INNOV labels should not appear in ## section headings
    headers = re.findall(r"^##+ .*", text, re.MULTILINE)
    for h in headers:
        assert "INNOV-" not in h, f"Internal batch label in header: {h}"


def test_T122_CRED_06_no_phase_number_in_section_headers():
    """T122-CRED-06: README section headers do not expose internal phase numbers."""
    text = README.read_text()
    headers = re.findall(r"^##+ .*", text, re.MULTILINE)
    phase_pattern = re.compile(r"Phase \d{2,3}", re.IGNORECASE)
    for h in headers:
        assert not phase_pattern.search(h), f"Phase number in header: {h}"


def test_T122_CRED_07_shipped_capabilities_section_present():
    """T122-CRED-07: README has a 'Shipped capabilities' section replacing old innovations section."""
    text = README.read_text()
    assert "## Shipped capabilities" in text


def test_T122_CRED_08_36_modules_in_capabilities_table():
    """T122-CRED-08: Capabilities table contains entries for all 36 modules."""
    text = README.read_text()
    # Count table rows with invariant anchors (backtick-wrapped)
    rows = re.findall(r"\| .+ \| `.+` \|", text)
    # At least 36 capability rows
    assert len(rows) >= 36, f"Expected >=36 capability rows, found {len(rows)}"


def test_T122_CRED_09_verifiable_claims_linked_in_readme():
    """T122-CRED-09: README links to docs/VERIFIABLE_CLAIMS.md."""
    text = README.read_text()
    assert "docs/VERIFIABLE_CLAIMS.md" in text


def test_T122_CRED_10_roadmap_section_not_stale():
    """T122-CRED-10: README Roadmap section does not reference 'Phases 87-115' or v9.48.0."""
    text = README.read_text()
    roadmap_idx = text.find("## Roadmap")
    assert roadmap_idx != -1
    roadmap_section = text[roadmap_idx:roadmap_idx + 600]
    assert "Phases 87–115" not in roadmap_section
    assert "v9.48.0" not in roadmap_section


# ── VERIFIABLE_CLAIMS.md ─────────────────────────────────────────────────────

def test_T122_CRED_11_verifiable_claims_exists():
    """T122-CRED-11: docs/VERIFIABLE_CLAIMS.md exists."""
    assert VERIFIABLE_CLAIMS.exists(), "VERIFIABLE_CLAIMS.md not found"


def test_T122_CRED_12_verifiable_claims_has_verify_commands():
    """T122-CRED-12: VERIFIABLE_CLAIMS.md contains pytest verification commands."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "pytest" in text


def test_T122_CRED_13_verifiable_claims_has_module_column():
    """T122-CRED-13: VERIFIABLE_CLAIMS.md table contains Module column."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "Module" in text


def test_T122_CRED_14_verifiable_claims_has_test_file_column():
    """T122-CRED-14: VERIFIABLE_CLAIMS.md table contains Test file column."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "Test file" in text


def test_T122_CRED_15_verifiable_claims_has_artifact_column():
    """T122-CRED-15: VERIFIABLE_CLAIMS.md table contains Governance artifact column."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "Governance artifact" in text or "Artifact" in text


def test_T122_CRED_16_verifiable_claims_covers_das():
    """T122-CRED-16: VERIFIABLE_CLAIMS.md covers DAS (Phase 121)."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "DAS" in text
    assert "deterministic_audit_sandbox" in text


def test_T122_CRED_17_verifiable_claims_covers_spie():
    """T122-CRED-17: VERIFIABLE_CLAIMS.md covers SPIE (Phase 120)."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "SPIE" in text
    assert "self_proposing_innovation_engine" in text


def test_T122_CRED_18_verifiable_claims_covers_human0_gate():
    """T122-CRED-18: VERIFIABLE_CLAIMS.md documents HUMAN-0 gate claims."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "HUMAN-0" in text
    assert "GPG" in text


def test_T122_CRED_19_verifiable_claims_no_world_first():
    """T122-CRED-19: VERIFIABLE_CLAIMS.md contains no unsubstantiated 'world-first' claims."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "world-first" not in text.lower()


def test_T122_CRED_20_verifiable_claims_has_what_is_not_claimed():
    """T122-CRED-20: VERIFIABLE_CLAIMS.md has explicit 'What is not claimed' section."""
    text = VERIFIABLE_CLAIMS.read_text()
    assert "not claimed" in text.lower() or "What is not" in text


# ── ROADMAP sync ─────────────────────────────────────────────────────────────

def test_T122_CRED_21_roadmap_phase121_shipped():
    """T122-CRED-21: ROADMAP marks Phase 121 as shipped."""
    text = ROADMAP.read_text()
    # Find phase 121 section and verify shipped status
    idx = text.find("Phase 121")
    assert idx != -1
    section = text[idx:idx + 300]
    assert "✅" in section or "shipped" in section.lower()


def test_T122_CRED_22_roadmap_current_state_162_invariants():
    """T122-CRED-22: ROADMAP current state block references 162 invariants."""
    text = ROADMAP.read_text()
    assert "162" in text


def test_T122_CRED_23_roadmap_phase122_in_progress():
    """T122-CRED-23: ROADMAP marks Phase 122 as in progress."""
    text = ROADMAP.read_text()
    idx = text.find("Phase 122")
    assert idx != -1
    section = text[idx:idx + 300]
    assert "🔄" in section or "in progress" in section.lower()


def test_T122_CRED_24_roadmap_current_state_not_stale():
    """T122-CRED-24: ROADMAP current state does not reference v9.53.0 as current."""
    text = ROADMAP.read_text()
    # v9.53.0 should appear only in the innovations table, not in the current state header
    idx = text.find("## Current State")
    assert idx != -1
    current_block = text[idx:idx + 400]
    assert "v9.53.0" not in current_block


# ── Version surface alignment ─────────────────────────────────────────────────

def test_T122_CRED_25_version_file_bumped():
    """T122-CRED-25: VERSION file is 9.55.0."""
    assert VERSION_FILE.read_text().strip() == "9.55.0"


def test_T122_CRED_26_pyproject_version_bumped():
    """T122-CRED-26: pyproject.toml version is 9.55.0."""
    text = PYPROJECT.read_text()
    assert 'version = "9.55.0"' in text


def test_T122_CRED_27_agent_state_version_bumped():
    """T122-CRED-27: .adaad_agent_state.json version is 9.55.0."""
    d = json.loads(AGENT_STATE.read_text())
    assert d.get("version") == "9.55.0"


def test_T122_CRED_28_agent_state_phase_122():
    """T122-CRED-28: .adaad_agent_state.json current_phase is 122."""
    d = json.loads(AGENT_STATE.read_text())
    assert d.get("current_phase") == 122


def test_T122_CRED_29_report_version_bumped():
    """T122-CRED-29: governance/report_version.json version is 9.55.0."""
    d = json.loads(REPORT_VERSION.read_text())
    assert d.get("version") == "9.55.0"


def test_T122_CRED_30_four_version_surfaces_aligned():
    """T122-CRED-30: All four version surfaces agree on 9.55.0."""
    v_file = VERSION_FILE.read_text().strip()
    pyproject_text = PYPROJECT.read_text()
    agent = json.loads(AGENT_STATE.read_text())
    report = json.loads(REPORT_VERSION.read_text())

    pyproject_match = re.search(r'^version = "([^"]+)"', pyproject_text, re.MULTILINE)
    assert pyproject_match, "No version found in pyproject.toml"
    v_pyproject = pyproject_match.group(1)

    assert v_file == "9.55.0", f"VERSION: {v_file}"
    assert v_pyproject == "9.55.0", f"pyproject: {v_pyproject}"
    assert agent.get("version") == "9.55.0", f"agent_state: {agent.get('version')}"
    assert report.get("version") == "9.55.0", f"report_version: {report.get('version')}"
