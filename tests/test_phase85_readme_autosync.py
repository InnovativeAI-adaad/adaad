# SPDX-License-Identifier: Apache-2.0
"""Phase 85 Track C — README auto-sync tests. T85-README-01..10"""
from __future__ import annotations
import json, re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.phase85


@pytest.fixture
def tmp_repo(tmp_path):
    (tmp_path / "VERSION").write_text("9.17.0\n")
    (tmp_path / "CHANGELOG.md").write_text(
        "## [9.17.0] — 2026-03-21 — Phase 85 · KMS/HSM\n\nPhase 85 content.\n\n"
    )
    (tmp_path / "README.md").write_text(
        "<!-- ADAAD_VERSION_INFOBOX:START -->\n"
        "| **Tests passing** | 4,800+ |\n"
        "| **Ledger entries** | 12,441+ SHA-256 hash-chained |\n"
        "| **Next** | Phase 86 — OperatorCoevolution |\n"
        "<!-- ADAAD_VERSION_INFOBOX:END -->\n"
    )
    (tmp_path / ".adaad_agent_state.json").write_text(json.dumps({"current_version": "9.17.0"}))
    (tmp_path / "docs" / "assets" / "readme").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _import_gen(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generate_readme_svgs", ROOT / "scripts" / "generate_readme_svgs.py")
    mod = importlib.util.module_from_spec(spec)
    mod.ROOT = tmp_path
    mod.ASSETS_DIR = tmp_path / "docs" / "assets" / "readme"
    spec.loader.exec_module(mod)
    return mod


def test_all_svgs_generated(tmp_repo):
    """T85-README-01: generate_all writes 4 SVG files."""
    mod = _import_gen(tmp_repo)
    results = mod.generate_all(dry_run=False)
    assert len(results) == 4


def test_stats_card_contains_version(tmp_repo):
    """T85-README-02: stats card has version string."""
    mod = _import_gen(tmp_repo)
    mod.generate_all(dry_run=False)
    svg = (tmp_repo / "docs/assets/readme/adaad-stats-card.svg").read_text()
    assert "9.17.0" in svg


def test_version_hero_has_live(tmp_repo):
    """T85-README-03: version hero contains LIVE."""
    mod = _import_gen(tmp_repo)
    mod.generate_all(dry_run=False)
    svg = (tmp_repo / "docs/assets/readme/adaad-version-hero.svg").read_text()
    assert "LIVE" in svg


def test_live_status_has_invariants(tmp_repo):
    """T85-README-04: live status has invariant codes."""
    mod = _import_gen(tmp_repo)
    mod.generate_all(dry_run=False)
    svg = (tmp_repo / "docs/assets/readme/adaad-live-status.svg").read_text()
    assert "CEL-ORDER-0" in svg
    assert "AUDIT-0" in svg


def test_phase_progress_has_rects(tmp_repo):
    """T85-README-05: phase progress has >80 rect elements."""
    mod = _import_gen(tmp_repo)
    mod.generate_all(dry_run=False)
    svg = (tmp_repo / "docs/assets/readme/adaad-phase-progress.svg").read_text()
    assert len(re.findall(r"<rect", svg)) > 80


def test_deterministic(tmp_repo):
    """T85-README-06: two runs produce identical digests."""
    mod = _import_gen(tmp_repo)
    r1 = {r["file"]: r["digest"] for r in mod.generate_all(dry_run=False)}
    r2 = {r["file"]: r["digest"] for r in mod.generate_all(dry_run=False)}
    assert r1 == r2


def test_valid_xml(tmp_repo):
    """T85-README-07: all SVGs parse as valid XML."""
    import xml.etree.ElementTree as ET
    _import_gen(tmp_repo).generate_all(dry_run=False)
    for f in (tmp_repo / "docs/assets/readme").glob("*.svg"):
        ET.parse(f)


def test_missing_version_exits_1(tmp_repo):
    """T85-README-08: missing VERSION exits 1."""
    (tmp_repo / "VERSION").unlink()
    mod = _import_gen(tmp_repo)
    with pytest.raises(SystemExit) as e:
        mod.generate_all()
    assert e.value.code == 1


def test_generate_script_exists():
    """T85-README-09: generate script present."""
    assert (ROOT / "scripts" / "generate_readme_svgs.py").exists()


def test_stats_card_has_animation(tmp_repo):
    """T85-README-10: stats card has @keyframes."""
    mod = _import_gen(tmp_repo)
    svg = mod.generate_stats_card("9.17.0", 85, "4,800+", "12,441+", 36)
    assert "@keyframes" in svg


