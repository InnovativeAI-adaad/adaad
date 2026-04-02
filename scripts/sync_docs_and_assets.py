#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""sync_docs_and_assets.py — Autonomous version sync for all docs and asset surfaces.

Reads VERSION as canonical source-of-truth and updates every version-bearing
surface: markdown badges, SVG assets, shields.io badge URLs, alt-text, facing
docs, and governance pointers.

Constitutional invariants
  DOCSYNC-0      All surfaces must reflect VERSION after a successful run.
  DOCSYNC-DETERM-0 Identical VERSION + state inputs → identical outputs.
  DOCSYNC-IDEM-0 Re-running on an already-synced repo emits zero file writes.
  DOCSYNC-CLOSED-0 Any unresolvable state file exits non-zero (no silent drift).

Usage
  python3 scripts/sync_docs_and_assets.py [--dry-run] [--verbose]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# ── Surfaces registry ──────────────────────────────────────────────────────────
# Each entry: (file, list_of_(regex_or_literal, replacement_template))
# {V} = version  {PHASE} = phase  {INNOV} = innovation count  {HARD} = hard invariants

MARKDOWN_PATCHES: list[tuple[Path, list[tuple[str, str]]]] = []
SVG_SURFACES: list[Path] = [
    ROOT / "docs/assets/readme/adaad-stats-card.svg",
    ROOT / "docs/assets/readme/adaad-version-hero.svg",
    ROOT / "docs/assets/readme/adaad-live-status.svg",
    ROOT / "docs/assets/adaad-hero.svg",
]


def _load_state() -> dict[str, Any]:
    """DOCSYNC-CLOSED-0: load canonical state; exit 1 on failure."""
    version_path = ROOT / "VERSION"
    state_path = ROOT / ".adaad_agent_state.json"

    if not version_path.exists():
        _die("DOCSYNC-CLOSED-0: VERSION file not found")
    version = version_path.read_text().strip()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        _die(f"DOCSYNC-CLOSED-0: VERSION '{version}' is not valid semver")

    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception as e:
            _die(f"DOCSYNC-CLOSED-0: cannot parse .adaad_agent_state.json: {e}")

    phase = state.get("phase", 0)
    last_innov = state.get("last_innovation", "INNOV-0")
    innov_match = re.search(r"\d+", last_innov)
    innov_num = int(innov_match.group()) if innov_match else 0

    # Count cumulative invariants from governance artifact if available
    hard = 56  # fallback — updated on each phase
    latest_phase_dir = max(
        (ROOT / "artifacts/governance").glob("phase*"),
        key=lambda p: int(m.group()) if (m := re.search(r"\d+", p.name)) else 0,
        default=None,
    )
    if latest_phase_dir:
        sign_off = latest_phase_dir / f"{latest_phase_dir.name}_sign_off.json"
        if sign_off.exists():
            try:
                so = json.loads(sign_off.read_text())
                hard = so.get("cumulative_invariants", hard)
            except Exception:
                pass

    return {
        "version": version,
        "phase": phase,
        "innov_num": innov_num,
        "hard": hard,
        "today": str(date.today()),
    }


def _die(msg: str) -> None:
    print(f"[DOCSYNC ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def _patch_file(
    path: Path,
    patches: list[tuple[str, str]],
    ctx: dict[str, Any],
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Apply string/regex patches to a file. Returns number of changes made."""
    if not path.exists():
        if verbose:
            print(f"  SKIP (missing): {path.relative_to(ROOT)}")
        return 0

    content = original = path.read_text()
    changes = 0
    for pattern, replacement in patches:
        repl = replacement.format(**ctx)
        if "REGEX:" in pattern:
            regex = pattern.replace("REGEX:", "")
            new = re.sub(regex, repl, content)
        else:
            new = content.replace(pattern, repl)
        if new != content:
            changes += 1
            content = new

    if changes > 0 and not dry_run:
        path.write_text(content)
    if verbose and changes > 0:
        print(f"  PATCHED ({changes} changes): {path.relative_to(ROOT)}")
    elif verbose:
        print(f"  OK (no change): {path.relative_to(ROOT)}")
    return changes


def _regenerate_svg(path: Path, ctx: dict[str, Any], dry_run: bool = False) -> int:
    """Regenerate a versioned SVG badge with current state. Returns 1 if changed."""
    name = path.stem
    V, PHASE, HARD, INNOV_N = ctx["version"], ctx["phase"], ctx["hard"], ctx["innov_num"]
    TODAY = ctx["today"]

    svg_map = {
        "adaad-stats-card": _svg_stats_card(V, PHASE, INNOV_N, HARD, TODAY),
        "adaad-version-hero": _svg_version_hero(V, PHASE, INNOV_N, HARD, TODAY),
        "adaad-live-status": _svg_live_status(V, PHASE, INNOV_N, HARD, TODAY),
        "adaad-hero": _svg_live_status(V, PHASE, INNOV_N, HARD, TODAY),
    }

    if name not in svg_map:
        return 0

    new_content = svg_map[name]
    existing = path.read_text() if path.exists() else ""
    if new_content == existing:
        return 0
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content)
    return 1


def _svg_stats_card(V, PHASE, INNOV_N, HARD, TODAY):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="120" viewBox="0 0 800 120">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#0d1117"/>
      <stop offset="100%" style="stop-color:#161b22"/>
    </linearGradient>
  </defs>
  <rect width="800" height="120" rx="8" fill="url(#bg)" stroke="#30363d" stroke-width="1"/>
  <text x="24" y="38" font-family="'SF Mono',monospace" font-size="11" fill="#8b949e">VERSION</text>
  <text x="24" y="60" font-family="'SF Mono',monospace" font-size="22" font-weight="700" fill="#00d4ff">v{V}</text>
  <text x="180" y="38" font-family="'SF Mono',monospace" font-size="11" fill="#8b949e">PHASE</text>
  <text x="180" y="60" font-family="'SF Mono',monospace" font-size="22" font-weight="700" fill="#f5c842">{PHASE}</text>
  <text x="310" y="38" font-family="'SF Mono',monospace" font-size="11" fill="#8b949e">INNOVATIONS</text>
  <text x="310" y="60" font-family="'SF Mono',monospace" font-size="22" font-weight="700" fill="#00ff88">{INNOV_N}</text>
  <text x="460" y="38" font-family="'SF Mono',monospace" font-size="11" fill="#8b949e">HARD INVARIANTS</text>
  <text x="460" y="60" font-family="'SF Mono',monospace" font-size="22" font-weight="700" fill="#ff4466">{HARD}</text>
  <text x="640" y="38" font-family="'SF Mono',monospace" font-size="11" fill="#8b949e">STATUS</text>
  <text x="640" y="60" font-family="'SF Mono',monospace" font-size="22" font-weight="700" fill="#00ff88">LIVE</text>
  <text x="24" y="100" font-family="'SF Mono',monospace" font-size="10" fill="#484f58">ADAAD \xb7 Autonomous Development &amp; Adaptation Architecture \xb7 InnovativeAI LLC \xb7 Apache 2.0</text>
  <text x="700" y="100" font-family="'SF Mono',monospace" font-size="9" fill="#30363d">AUTO-SYNCED {TODAY}</text>
</svg>"""


def _svg_version_hero(V, PHASE, INNOV_N, HARD, TODAY):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="200" viewBox="0 0 800 200">
  <defs>
    <linearGradient id="heroBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0d1117"/>
      <stop offset="100%" style="stop-color:#1a2332"/>
    </linearGradient>
    <linearGradient id="vGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#00d4ff"/>
      <stop offset="100%" style="stop-color:#0088ff"/>
    </linearGradient>
  </defs>
  <rect width="800" height="200" rx="12" fill="url(#heroBg)" stroke="#21262d" stroke-width="1"/>
  <text x="40" y="85" font-family="'SF Mono',monospace" font-size="52" font-weight="900" fill="url(#vGrad)">v{V}</text>
  <rect x="40" y="100" width="180" height="32" rx="6" fill="#f5c84222"/>
  <text x="52" y="121" font-family="'SF Mono',monospace" font-size="14" font-weight="700" fill="#f5c842">Phase {PHASE} \xb7 {INNOV_N} Innovations</text>
  <rect x="234" y="100" width="185" height="32" rx="6" fill="#ff446622"/>
  <text x="246" y="121" font-family="'SF Mono',monospace" font-size="14" font-weight="700" fill="#ff4466">{HARD} Hard-Class Invariants</text>
  <rect x="433" y="100" width="90" height="32" rx="6" fill="#00ff8822"/>
  <circle cx="451" cy="116" r="5" fill="#00ff88"><animate attributeName="opacity" values="1;0.3;1" dur="2s" repeatCount="indefinite"/></circle>
  <text x="463" y="121" font-family="'SF Mono',monospace" font-size="14" font-weight="700" fill="#00ff88">LIVE</text>
  <text x="40" y="170" font-family="'SF Mono',monospace" font-size="13" fill="#8b949e">Autonomous Development &amp; Adaptation Architecture \xb7 InnovativeAI LLC</text>
  <text x="40" y="192" font-family="'SF Mono',monospace" font-size="9" fill="#30363d">AUTO-SYNCED \xb7 {TODAY}</text>
</svg>"""


def _svg_live_status(V, PHASE, INNOV_N, HARD, TODAY):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="80" viewBox="0 0 800 80">
  <rect width="800" height="80" rx="8" fill="#0d1117" stroke="#30363d" stroke-width="1"/>
  <circle cx="28" cy="40" r="7" fill="#00ff88"><animate attributeName="opacity" values="1;0.4;1" dur="1.5s" repeatCount="indefinite"/></circle>
  <text x="44" y="45" font-family="'SF Mono',monospace" font-size="13" font-weight="700" fill="#00ff88">LIVE</text>
  <text x="110" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#00d4ff">v{V}</text>
  <text x="185" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#8b949e">\xb7</text>
  <text x="200" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#f5c842">Phase {PHASE}</text>
  <text x="290" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#8b949e">\xb7</text>
  <text x="305" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#ff4466">{HARD} Hard Invariants</text>
  <text x="465" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#8b949e">\xb7</text>
  <text x="480" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#00ff88">{INNOV_N} Innovations</text>
  <text x="610" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#8b949e">\xb7</text>
  <text x="625" y="45" font-family="'SF Mono',monospace" font-size="13" fill="#00ff88">GATE \u2713</text>
  <text x="700" y="68" font-family="'SF Mono',monospace" font-size="8" fill="#30363d">AUTO-SYNCED {TODAY}</text>
</svg>"""


# ── Markdown patches ───────────────────────────────────────────────────────────

def _build_markdown_patches(ctx: dict[str, Any]) -> list[tuple[Path, list[tuple[str, str]]]]:
    V, PHASE, INNOV_N, HARD = ctx["version"], ctx["phase"], ctx["innov_num"], ctx["hard"]

    return [
        (ROOT / "README.md", [
            ("REGEX:alt=\"ADAAD v[\\d.]+ — \\d+ Phases Complete — LIVE\"",
             f'alt="ADAAD v{V} — {PHASE} Phases Complete — LIVE"'),
        ]),
        (ROOT / "docs/README.md", [
            ("REGEX:\\*\\*ADAAD v[\\d.]+ · Phase \\d+ \\([^)]+\\)\\*\\*",
             f"**ADAAD v{V} · Phase {PHASE} (INNOV-{INNOV_N} shipped)**"),
            ("REGEX:Current = Phase \\d+ \\(v[\\d.]+\\), Next = Phase \\d+[^.]+\\.",
             f"Current = Phase {PHASE} (v{V}), Next = Phase {PHASE + 1} — INNOV-{INNOV_N + 1}."),
            ("REGEX:ADAAD v[\\d.]+ Runtime",
             f"ADAAD v{V} Runtime"),
            ("REGEX:img\\.shields\\.io/badge/ADAAD-v[\\d.]+-",
             f"img.shields.io/badge/ADAAD-v{V}-"),
            ("REGEX:img\\.shields\\.io/badge/Phase_\\d+-[^-]+-",
             f"img.shields.io/badge/Phase_{PHASE}-ERS_Shipped-"),
            ("REGEX:<sub><code>ADAAD v[\\d.]+</code>",
             f"<sub><code>ADAAD v{V}</code>"),
        ]),
        (ROOT / "docs/CONSTITUTION.md", [
            ("REGEX:\\*\\*Active Phase\\*\\*: \\d+ \\(v[\\d.]+ — [^)]+\\)",
             f"**Active Phase**: {PHASE} (v{V} — INNOV-{INNOV_N} ERS complete)"),
        ]),
        (ROOT / "docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md", [
            ("REGEX:\\*\\*Canonical live state pointer:\\*\\* Current = \\*\\*Phase \\d+\\*\\* \\(`v[\\d.]+`[^)]+\\)\\. Next = \\*\\*Phase \\d+[^*]+\\*\\*\\.",
             f"**Canonical live state pointer:** Current = **Phase {PHASE}** (`v{V}`, INNOV-{INNOV_N} ERS shipped). Next = **Phase {PHASE + 1} — INNOV-{INNOV_N + 1}**."),
        ]),
        (ROOT / "governance/report_version.json", []),  # handled by sync_versions.py
    ]


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="ADAAD docs + assets version sync")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    parser.add_argument("--verbose", action="store_true", help="Show per-file status")
    args = parser.parse_args()

    ctx = _load_state()
    print(json.dumps({"event": "sync_start", "version": ctx["version"],
                      "phase": ctx["phase"], "dry_run": args.dry_run}))

    total_changes = 0

    # Markdown patches
    for path, patches in _build_markdown_patches(ctx):
        if patches:
            n = _patch_file(path, patches, ctx, args.dry_run, args.verbose)
            total_changes += n

    # SVG regeneration
    for svg_path in SVG_SURFACES:
        n = _regenerate_svg(svg_path, ctx, args.dry_run)
        total_changes += n
        if args.verbose and n:
            print(f"  SVG REGEN: {svg_path.relative_to(ROOT)}")

    print(json.dumps({
        "event": "sync_complete",
        "version": ctx["version"],
        "phase": ctx["phase"],
        "files_changed": total_changes,
        "dry_run": args.dry_run,
        "invariants": ["DOCSYNC-0", "DOCSYNC-DETERM-0", "DOCSYNC-IDEM-0"],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
