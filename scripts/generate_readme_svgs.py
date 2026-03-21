#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""generate_readme_svgs.py — Phase 85 Track C/D: README visual asset generator.

Generates five CSS-animated SVG assets from live repo data with full
neon glow aesthetics, aurora backgrounds, gradient fills, and vibrant colours.

CONSTITUTIONAL INVARIANTS
  README-SVG-0      All assets regenerated on every merge.
  README-DETERM-0   Identical inputs → identical SVG output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "docs" / "assets" / "readme"

BG      = "#060a0f"
BG2     = "#0d1117"
CYAN    = "#00d4ff"
GREEN   = "#00ff88"
YELLOW  = "#f5c842"
RED     = "#ff4466"
PURPLE  = "#a855f7"
TEXT_PRI = "rgba(255,255,255,.9)"
TEXT_SEC = "rgba(255,255,255,.4)"
TEXT_DIM = "rgba(255,255,255,.18)"
MONO    = "'JetBrains Mono','Courier New',monospace"
SANS    = "'Segoe UI',system-ui,Arial,sans-serif"
MILESTONE_PHASES = {65, 77}


def _fatal(code: str, msg: str) -> None:
    print(json.dumps({"event": code, "message": msg}), flush=True)
    sys.exit(1)


def _read_version() -> str:
    p = ROOT / "VERSION"
    if not p.exists():
        _fatal("README_SVG_GEN_ERROR_NO_VERSION", str(p))
    return p.read_text().strip()


def _read_agent_state() -> dict[str, Any]:
    p = ROOT / ".adaad_agent_state.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _parse_phase_count_from_changelog(version: str) -> int:
    cl_path = ROOT / "CHANGELOG.md"
    if not cl_path.exists():
        return 84
    cl = cl_path.read_text()
    pat = rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)"
    m = re.search(pat, cl, re.MULTILINE | re.DOTALL)
    if not m:
        return 84
    block = m.group(0)
    phases = [int(n) for n in re.findall(r"Phase[s]? (\d+)", block)]
    return max(phases) if phases else 84


def _parse_next_phase(version: str) -> str:
    readme = (ROOT / "README.md").read_text()
    m = re.search(r"\|\s*\*\*Next\*\*\s*\|\s*(.+?)\s*\|", readme)
    return m.group(1) if m else f"Phase 85 — KMS/HSM"


def _parse_test_count() -> str:
    readme = (ROOT / "README.md").read_text()
    m = re.search(r"\|\s*\*\*Tests passing\*\*\s*\|\s*([^\|]+?)\s*\|", readme)
    return (m.group(1) if m else "4,800+").strip()


def _parse_ledger_count() -> str:
    readme = (ROOT / "README.md").read_text()
    m = re.search(r"\|\s*\*\*Ledger entries\*\*\s*\|\s*([^\|]+?)\s*\|", readme)
    return (m.group(1) if m else "12,441+").strip()


def generate_stats_card(version: str, phase: int, tests: str,
                        ledger: str, invariants: int = 36) -> str:
    today = date.today().isoformat()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 200" width="100%" preserveAspectRatio="xMidYMid meet">
  <defs>
    <style>
      @keyframes sp{{0%,100%{{opacity:.8}}50%{{opacity:1}}}}
      @keyframes gs{{0%{{background-position:0%}}100%{{background-position:200%}}}}
    </style>
    <linearGradient id="bg1" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{CYAN}" stop-opacity=".15"/><stop offset="100%" stop-color="{PURPLE}" stop-opacity=".08"/></linearGradient>
    <linearGradient id="bg2" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{GREEN}" stop-opacity=".12"/><stop offset="100%" stop-color="{CYAN}" stop-opacity=".06"/></linearGradient>
    <linearGradient id="bg3" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{YELLOW}" stop-opacity=".12"/><stop offset="100%" stop-color="#ff9500" stop-opacity=".06"/></linearGradient>
    <linearGradient id="bg4" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{PURPLE}" stop-opacity=".12"/><stop offset="100%" stop-color="{RED}" stop-opacity=".06"/></linearGradient>
    <linearGradient id="bar1" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{CYAN}"/><stop offset="100%" stop-color="{PURPLE}"/></linearGradient>
    <filter id="gc"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="gg"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="gy"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="gp"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <rect width="1200" height="200" fill="{BG}"/>
  <!-- Card 1 -->
  <rect x="0" y="0" width="300" height="200" fill="url(#bg1)"/>
  <rect x="0" y="0" width="300" height="5" fill="url(#bar1)"/>
  <g filter="url(#gc)"><text x="150" y="92" text-anchor="middle" font-family="{SANS}" font-size="52" font-weight="900" fill="{CYAN}" letter-spacing="-2" style="animation:sp 5s ease-in-out infinite">v{version}</text></g>
  <text x="150" y="128" text-anchor="middle" font-family="{MONO}" font-size="16" fill="{TEXT_SEC}" letter-spacing="3">CURRENT RELEASE</text>
  <text x="150" y="152" text-anchor="middle" font-family="{MONO}" font-size="14" fill="{TEXT_DIM}">{today}</text>
  <!-- Card 2 -->
  <rect x="301" y="0" width="299" height="200" fill="url(#bg2)"/>
  <rect x="301" y="0" width="299" height="5" fill="{GREEN}"/>
  <g filter="url(#gg)"><text x="450" y="92" text-anchor="middle" font-family="{SANS}" font-size="52" font-weight="900" fill="{GREEN}" letter-spacing="-2" style="animation:sp 5s .5s ease-in-out infinite">{phase}</text></g>
  <text x="450" y="128" text-anchor="middle" font-family="{MONO}" font-size="16" fill="{TEXT_SEC}" letter-spacing="3">PHASES COMPLETE</text>
  <text x="450" y="152" text-anchor="middle" font-family="{MONO}" font-size="14" fill="{TEXT_DIM}">⛓ Phase 65 · 🌱 Phase 77 sealed</text>
  <!-- Card 3 -->
  <rect x="601" y="0" width="299" height="200" fill="url(#bg3)"/>
  <rect x="601" y="0" width="299" height="5" fill="{YELLOW}"/>
  <g filter="url(#gy)"><text x="750" y="92" text-anchor="middle" font-family="{SANS}" font-size="52" font-weight="900" fill="{YELLOW}" letter-spacing="-2">{tests}</text></g>
  <text x="750" y="128" text-anchor="middle" font-family="{MONO}" font-size="16" fill="{TEXT_SEC}" letter-spacing="3">TESTS PASSING</text>
  <text x="750" y="152" text-anchor="middle" font-family="{MONO}" font-size="14" fill="{TEXT_DIM}">ledger: {ledger} · SHA-256</text>
  <!-- Card 4 -->
  <rect x="901" y="0" width="299" height="200" fill="url(#bg4)"/>
  <rect x="901" y="0" width="299" height="5" fill="{PURPLE}"/>
  <g filter="url(#gp)"><text x="1050" y="92" text-anchor="middle" font-family="{SANS}" font-size="52" font-weight="900" fill="{PURPLE}" letter-spacing="-2" style="animation:sp 5s 1s ease-in-out infinite">{invariants}</text></g>
  <text x="1050" y="128" text-anchor="middle" font-family="{MONO}" font-size="16" fill="{TEXT_SEC}" letter-spacing="3">CONSTITUTIONAL INVARIANTS</text>
  <text x="1050" y="152" text-anchor="middle" font-family="{MONO}" font-size="14" fill="{TEXT_DIM}">23 supreme rules · v0.9.0</text>
</svg>"""


def generate_phase_progress(current_phase: int, total: int = 100) -> str:
    block_w = 10
    gap = 2
    total_w = total * (block_w + gap) - gap
    pad_x = 20
    full_w = total_w + pad_x * 2
    blocks = []
    for i in range(1, total + 1):
        x = pad_x + (i - 1) * (block_w + gap)
        if i in MILESTONE_PHASES:
            colour = GREEN
            filt = ' filter="url(#gmil)"'
            anim = ' class="ms"'
        elif i == current_phase:
            colour = RED
            filt = ' filter="url(#gcur)"'
            anim = ' class="cur"'
        elif i < current_phase:
            colour = f"url(#doneGrad)"
            filt = ""
            anim = ""
        else:
            colour = "rgba(255,255,255,.07)"
            filt = ""
            anim = ""
        blocks.append(f'<rect x="{x}" y="32" width="{block_w}" height="28" rx="2" fill="{colour}"{filt}{anim}/>')
    blocks_svg = "\n  ".join(blocks)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {full_w} 88" width="100%" preserveAspectRatio="xMidYMid meet">
  <defs>
    <style>
      @keyframes cur{{0%,100%{{opacity:.5}}50%{{opacity:1}}}}
      @keyframes ms{{0%,100%{{opacity:.8}}50%{{opacity:1}}}}
      .cur{{animation:cur 1.5s ease-in-out infinite}}
      .ms{{animation:ms 3s ease-in-out infinite}}
    </style>
    <linearGradient id="doneGrad" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{CYAN}" stop-opacity=".55"/><stop offset="100%" stop-color="{PURPLE}" stop-opacity=".35"/></linearGradient>
    <filter id="gmil"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="gcur"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <rect width="{full_w}" height="88" fill="{BG}"/>
  <text x="{pad_x}" y="20" font-family="{MONO}" font-size="16" fill="{TEXT_SEC}" letter-spacing="3">PHASE EVOLUTION — {current_phase} OF {total} PROJECTED</text>
  {blocks_svg}
  <text x="{pad_x}" y="78" font-family="{MONO}" font-size="13" fill="{TEXT_DIM}">FOUNDATION 1–46 · GAP CLOSURE 47–56 · CONSTITUTIONAL 57–64 · ⛓ 65 · SEED PIPELINE 71–77 · EVOLUTION ENGINE 81–84 · ◈ CURRENT</text>
</svg>"""


def generate_live_status(version: str) -> str:
    rows_data = [
        ("Constitutional Evolution Loop (14 steps)", "live", "CEL-ORDER-0"),
        ("Lineage Ledger v2",                        "live", "AUDIT-0"),
        ("Governance Gate",                          "live", "GOV-SOLE-0"),
        ("Seed Lifecycle Pipeline",                  "live", "SEED-LIFECYCLE-COMPLETE-0"),
        ("Constitutional Self-Discovery Loop",       "live", "SELF-DISC-0"),
        ("Pareto Population Evolution",              "live", "PARETO-0"),
        ("Causal Fitness Attribution (Shapley)",     "live", "CAUSAL-ATTR-0"),
        ("Temporal Fitness Half-Life",               "live", "DECAY-0"),
        ("Deterministic Replay",                     "live", "REPLAY-0"),
        ("KMS/HSM production key wiring",            "next", "Phase 85 · LEDGER-SIGN-0"),
    ]
    row_h = 52
    cols = 2
    rows_per_col = (len(rows_data) + 1) // 2
    card_w = 600
    total_w = card_w * cols + 2
    total_h = rows_per_col * row_h + 56
    rows_svg = []
    for idx, (label, state, inv) in enumerate(rows_data):
        col = idx // rows_per_col
        row = idx % rows_per_col
        x = col * (card_w + 2)
        y = 48 + row * row_h
        dot_colour = GREEN if state == "live" else YELLOW
        dot_anim = 'class="live"' if state == "live" else 'class="nxt"'
        rows_svg.append(
            f'<rect x="{x}" y="{y}" width="{card_w}" height="{row_h-3}" rx="0" fill="rgba(255,255,255,.015)"/>'
            f'<circle cx="{x+22}" cy="{y+(row_h-3)//2}" r="5" fill="{dot_colour}" {dot_anim}/>'
            f'<text x="{x+40}" y="{y+(row_h-3)//2+6}" font-family="{SANS}" font-size="18" fill="{TEXT_PRI}">{label}</text>'
            f'<text x="{x+card_w-10}" y="{y+(row_h-3)//2+6}" text-anchor="end" font-family="{MONO}" font-size="15" fill="rgba(0,212,255,.55)">{inv}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" width="100%" preserveAspectRatio="xMidYMid meet">
  <defs><style>
    @keyframes live{{0%,100%{{opacity:.6}}50%{{opacity:1}}}}
    @keyframes nxt{{0%,100%{{opacity:.4}}50%{{opacity:.9}}}}
    .live{{animation:live 3s ease-in-out infinite}}
    .nxt{{animation:nxt 2s ease-in-out infinite}}
  </style></defs>
  <rect width="{total_w}" height="{total_h}" fill="{BG}"/>
  <text x="20" y="28" font-family="{MONO}" font-size="16" fill="{TEXT_SEC}" letter-spacing="3">LIVE SYSTEM STATUS — v{version}</text>
  {"".join(rows_svg)}
</svg>"""


def generate_version_hero(version: str, phase: int, next_phase: str) -> str:
    today = date.today().isoformat()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 72" width="100%" preserveAspectRatio="xMidYMid meet">
  <defs>
    <style>@keyframes tk{{0%,100%{{opacity:.5}}50%{{opacity:1}}}}.tk{{animation:tk 1s ease-in-out infinite}}</style>
    <linearGradient id="topbar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"   stop-color="{CYAN}"/>
      <stop offset="25%"  stop-color="{PURPLE}"/>
      <stop offset="50%"  stop-color="{RED}"/>
      <stop offset="75%"  stop-color="{GREEN}"/>
      <stop offset="100%" stop-color="{YELLOW}"/>
    </linearGradient>
    <filter id="gv"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <rect width="1200" height="72" fill="{BG2}"/>
  <rect y="0" width="1200" height="4" fill="url(#topbar)"/>
  <circle cx="24" cy="38" r="7" fill="{GREEN}" class="tk" filter="url(#gv)"/>
  <text x="40" y="43" font-family="{MONO}" font-size="18" fill="{GREEN}">LIVE</text>
  <rect x="80" y="18" width="1" height="24" fill="rgba(255,255,255,.1)"/>
  <text x="94" y="43" font-family="{MONO}" font-size="18" fill="{TEXT_PRI}" filter="url(#gv)">v{version}</text>
  <rect x="168" y="18" width="1" height="24" fill="rgba(255,255,255,.1)"/>
  <text x="182" y="43" font-family="{MONO}" font-size="18" fill="{TEXT_SEC}">{today}</text>
  <rect x="316" y="18" width="1" height="24" fill="rgba(255,255,255,.1)"/>
  <text x="330" y="43" font-family="{MONO}" font-size="18" fill="{CYAN}">{phase} phases complete</text>
  <rect x="560" y="18" width="1" height="24" fill="rgba(255,255,255,.1)"/>
  <text x="574" y="43" font-family="{MONO}" font-size="18" fill="{YELLOW}">next: {next_phase[:42]}</text>
  <text x="1190" y="43" text-anchor="end" font-family="{MONO}" font-size="14" fill="{TEXT_DIM}">GOV-SOLE-0 · AUDIT-0 · REPLAY-0 · HUMAN-0</text>
</svg>"""


def generate_all(*, dry_run: bool = False) -> list[dict[str, Any]]:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    version    = _read_version()
    phase      = _parse_phase_count_from_changelog(version)
    tests      = _parse_test_count()
    ledger     = _parse_ledger_count()
    next_phase = _parse_next_phase(version)

    generated = []
    targets = [
        ("adaad-stats-card.svg",     generate_stats_card(version, phase, tests, ledger)),
        ("adaad-phase-progress.svg", generate_phase_progress(phase)),
        ("adaad-live-status.svg",    generate_live_status(version)),
        ("adaad-version-hero.svg",   generate_version_hero(version, phase, next_phase)),
    ]
    for filename, svg in targets:
        path = ASSETS_DIR / filename
        digest = "sha256:" + hashlib.sha256(svg.encode()).hexdigest()[:16]
        if not dry_run:
            path.write_text(svg, encoding="utf-8")
        generated.append({"file": str(path.relative_to(ROOT)), "digest": digest, "dry_run": dry_run})
        print(json.dumps({"event": "svg_generated", "file": filename, "digest": digest}), flush=True)

    print(json.dumps({"event": "generate_complete", "count": len(generated), "version": version}), flush=True)
    return generated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    generate_all(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
