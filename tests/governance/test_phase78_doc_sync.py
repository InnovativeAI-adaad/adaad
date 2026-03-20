# SPDX-License-Identifier: Apache-2.0
"""Phase 78 — M78-02: verify_doc_sync.py gate test suite.

Tests
-----
T78-SYNC-01  Clean repo exits 0 and reports no drift.
T78-SYNC-02  Missing VERSION exits with SYNC_ERROR_MISSING_VERSION.
T78-SYNC-03  Drifted ADAAD badge reports DOC-SYNC-VERSION-0 and exits 1.
T78-SYNC-04  Drifted PyPI badge reports DOC-SYNC-VERSION-0 and exits 1.
T78-SYNC-05  Drifted infobox version reports DOC-SYNC-VERSION-0 and exits 1.
T78-SYNC-06  Drift in hero alt-text reports DOC-SYNC-VERSION-0 and exits 1.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance_gate

# Import the verify function directly (unit test, no subprocess).
import importlib.util
import sys

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_doc_sync.py"
_spec = importlib.util.spec_from_file_location("verify_doc_sync", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["verify_doc_sync"] = _mod
_spec.loader.exec_module(_mod)

verify = _mod.verify
VerifyResult = _mod.VerifyResult

VERSION = "9.13.0"

# ---------------------------------------------------------------------------
# Minimal README that satisfies all patterns when version is correct.
# ---------------------------------------------------------------------------

def _clean_readme(version: str = VERSION) -> str:
    return textwrap.dedent(f"""\
        <img src="docs/assets/adaad-hero.svg" width="100%" alt="ADAAD — Autonomous Development · v{version} · Phase 78"/>

        [![Version](https://img.shields.io/badge/ADAAD-{version}-000?style=for-the-badge)](https://github.com/InnovativeAI-adaad/ADAAD/releases)&nbsp;[![PyPI](https://img.shields.io/badge/PyPI-adaad_{version}-000?style=for-the-badge)](https://pypi.org/project/adaad/{version}/)

        <!-- ADAAD_VERSION_INFOBOX:START -->
        | Field | Value |
        |---|---|
        | **Current version** | `{version}` |
        <!-- ADAAD_VERSION_INFOBOX:END -->

        <img src="docs/assets/adaad-stats-card.svg" width="100%" alt="ADAAD Stats — v{version} · 4,700 tests · 78 phases"/>
    """)


def _write_repo(tmp_path: Path, version: str, readme: str) -> Path:
    (tmp_path / "VERSION").write_text(version + "\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# T78-SYNC-01: Clean repo → exit 0, no drifts
# ---------------------------------------------------------------------------

def test_T78_SYNC_01_clean_repo_no_drift(tmp_path: Path) -> None:
    _write_repo(tmp_path, VERSION, _clean_readme(VERSION))
    result = verify(tmp_path)
    assert result.clean, f"expected no drifts, got: {[d.to_dict() for d in result.drifts]}"
    assert result.version == VERSION


# ---------------------------------------------------------------------------
# T78-SYNC-02: Missing VERSION file → sys.exit(1) via SYNC_ERROR_MISSING_VERSION
# ---------------------------------------------------------------------------

def test_T78_SYNC_02_missing_version_file_exits(tmp_path: Path, capsys) -> None:
    (tmp_path / "README.md").write_text(_clean_readme(VERSION), encoding="utf-8")
    # VERSION file deliberately not written.
    with pytest.raises(SystemExit) as exc_info:
        verify(tmp_path)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["event"] == "SYNC_ERROR_MISSING_VERSION"


# ---------------------------------------------------------------------------
# T78-SYNC-03: Drifted ADAAD badge → DOC-SYNC-VERSION-0 + exit 1
# ---------------------------------------------------------------------------

def test_T78_SYNC_03_drifted_adaad_badge(tmp_path: Path) -> None:
    readme = _clean_readme(VERSION).replace(
        f"https://img.shields.io/badge/ADAAD-{VERSION}-",
        "https://img.shields.io/badge/ADAAD-9.99.0-",
    )
    _write_repo(tmp_path, VERSION, readme)
    result = verify(tmp_path)
    assert not result.clean
    rules = [d.rule for d in result.drifts]
    assert "DOC-SYNC-VERSION-0" in rules
    found_locs = [d.location for d in result.drifts if d.rule == "DOC-SYNC-VERSION-0"]
    assert any("ADAAD badge" in loc for loc in found_locs)


# ---------------------------------------------------------------------------
# T78-SYNC-04: Drifted PyPI badge → DOC-SYNC-VERSION-0
# ---------------------------------------------------------------------------

def test_T78_SYNC_04_drifted_pypi_badge(tmp_path: Path) -> None:
    readme = _clean_readme(VERSION).replace(
        f"https://img.shields.io/badge/PyPI-adaad_{VERSION}-",
        "https://img.shields.io/badge/PyPI-adaad_9.99.0-",
    )
    _write_repo(tmp_path, VERSION, readme)
    result = verify(tmp_path)
    assert not result.clean
    assert any(d.rule == "DOC-SYNC-VERSION-0" for d in result.drifts)
    assert any("PyPI" in d.location for d in result.drifts)


# ---------------------------------------------------------------------------
# T78-SYNC-05: Drifted infobox Current version row → DOC-SYNC-VERSION-0
# ---------------------------------------------------------------------------

def test_T78_SYNC_05_drifted_infobox_version(tmp_path: Path) -> None:
    readme = _clean_readme(VERSION).replace(
        f"| **Current version** | `{VERSION}` |",
        "| **Current version** | `9.99.0` |",
    )
    _write_repo(tmp_path, VERSION, readme)
    result = verify(tmp_path)
    assert not result.clean
    assert any("VERSION_INFOBOX" in d.location for d in result.drifts)


# ---------------------------------------------------------------------------
# T78-SYNC-06: Drifted hero alt-text → DOC-SYNC-VERSION-0
# ---------------------------------------------------------------------------

def test_T78_SYNC_06_drifted_hero_alt_text(tmp_path: Path) -> None:
    readme = _clean_readme(VERSION).replace(
        f"v{VERSION} · Phase 78",
        "v9.99.0 · Phase 78",
    )
    _write_repo(tmp_path, VERSION, readme)
    result = verify(tmp_path)
    assert not result.clean
    assert any("hero alt" in d.location for d in result.drifts)
