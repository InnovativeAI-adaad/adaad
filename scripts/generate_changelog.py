#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate deterministic CHANGELOG.md from merged phase metadata."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

PROCESSION_PATH = Path("docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md")
EVIDENCE_MATRIX_PATH = Path("docs/comms/claims_evidence_matrix.md")
POST_MERGE_CONTRACT_PATH = Path("docs/governance/post_merge_doc_sync_contract.yaml")
RELEASE_NOTES_DIR = Path("docs/releases")
CHANGELOG_PATH = Path("CHANGELOG.md")


@dataclass(frozen=True)
class PhaseEntry:
    phase_id: int
    version: str
    status: str
    ci_tier: str
    title: str


def _extract_contract_yaml_block(text: str) -> str:
    in_fence = False
    collecting = False
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if line.strip().startswith("```"):
            if collecting:
                break
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        if line.strip().startswith("adaad_pr_procession_contract:"):
            collecting = True
        if collecting:
            lines.append(line)
    if not lines:
        raise ValueError("unable to locate adaad_pr_procession_contract YAML block")
    return "\n".join(lines)


def _parse_phase_entries(contract_yaml: str) -> list[PhaseEntry]:
    entries: list[PhaseEntry] = []
    lines = contract_yaml.splitlines()
    in_phase_nodes = False
    current_phase: int | None = None
    current: dict[str, str] = {}

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped == "phase_nodes:":
            in_phase_nodes = True
            continue
        if not in_phase_nodes:
            continue

        phase_match = re.match(r"\s{4}phase(\d+):\s*$", line)
        if phase_match:
            if current_phase is not None:
                entries.append(
                    PhaseEntry(
                        phase_id=current_phase,
                        version=current.get("version", "").lstrip("v"),
                        status=current.get("status", ""),
                        ci_tier=current.get("ci_tier", ""),
                        title=current.get("title", f"Phase {current_phase}"),
                    )
                )
            current_phase = int(phase_match.group(1))
            current = {}
            continue

        if current_phase is None:
            continue

        if re.match(r"\s{2}\w", line):
            break

        kv_match = re.match(r"\s{6}([a-z_]+):\s*(.+)\s*$", line)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip().strip('"')
            current[key] = value

    if current_phase is not None:
        entries.append(
            PhaseEntry(
                phase_id=current_phase,
                version=current.get("version", "").lstrip("v"),
                status=current.get("status", ""),
                ci_tier=current.get("ci_tier", ""),
                title=current.get("title", f"Phase {current_phase}"),
            )
        )

    merged = [entry for entry in entries if entry.status == "merged" and entry.version]
    if not merged:
        raise ValueError("no merged phase entries found in procession contract")
    return merged


def _parse_release_dates() -> dict[str, str]:
    release_dates: dict[str, str] = {}
    for release_path in sorted(RELEASE_NOTES_DIR.glob("*.md")):
        version = release_path.stem
        text = release_path.read_text(encoding="utf-8")
        match = re.search(r"^\*\*Released:\*\*\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*$", text, flags=re.M)
        if match:
            release_dates[version] = match.group(1)
    return release_dates


def _parse_evidence_refs_by_phase() -> dict[int, list[str]]:
    refs: dict[int, list[str]] = {}
    pattern = re.compile(r"\|\s*`(phase(\d+)-[^`]+)`\s*\|.*\|\s*(Complete|Pending)\s*\|\s*$")
    for line in EVIDENCE_MATRIX_PATH.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        claim_id = match.group(1)
        phase_id = int(match.group(2))
        refs.setdefault(phase_id, []).append(claim_id)
    for phase_id in refs:
        refs[phase_id] = sorted(set(refs[phase_id]))
    return refs


def _parse_pr_ids_by_phase() -> dict[int, str]:
    phase_pr_map: dict[int, str] = {}
    if not POST_MERGE_CONTRACT_PATH.exists():
        return phase_pr_map

    current_phase: int | None = None
    current_pr_id: str | None = None
    for raw_line in POST_MERGE_CONTRACT_PATH.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- pr_id:"):
            current_pr_id = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("phase_id:"):
            phase_text = stripped.split(":", 1)[1].strip().strip('"')
            if phase_text.isdigit() and current_pr_id:
                current_phase = int(phase_text)
                phase_pr_map[current_phase] = current_pr_id
    return phase_pr_map


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def render_changelog() -> str:
    procession_text = PROCESSION_PATH.read_text(encoding="utf-8")
    contract_yaml = _extract_contract_yaml_block(procession_text)
    phases = _parse_phase_entries(contract_yaml)
    release_dates = _parse_release_dates()
    evidence_refs = _parse_evidence_refs_by_phase()
    pr_ids = _parse_pr_ids_by_phase()

    sections: list[str] = [
        "# CHANGELOG",
        "",
        "Generated deterministically from merged governance metadata.",
        "",
    ]

    for phase in sorted(phases, key=lambda item: _version_key(item.version), reverse=True):
        release_date = release_dates.get(phase.version, "unknown-date")
        pr_id = pr_ids.get(phase.phase_id, f"PR-PHASE{phase.phase_id}-01")
        evidence = evidence_refs.get(phase.phase_id, [])
        evidence_text = ", ".join(f"`{claim}`" for claim in evidence) if evidence else "_none_"

        sections.extend(
            [
                f"## [{phase.version}] — {release_date} — Phase {phase.phase_id}",
                "",
                f"- PR ID: `{pr_id}`",
                f"- Title: {phase.title}",
                f"- Lane/Tier: `governance` / `{phase.ci_tier}`",
                f"- Evidence refs: {evidence_text}",
                "",
            ]
        )

    return "\n".join(sections).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if CHANGELOG.md is stale")
    parser.add_argument("--output", type=Path, default=CHANGELOG_PATH, help="Output changelog path")
    args = parser.parse_args()

    rendered = render_changelog()
    existing = args.output.read_text(encoding="utf-8") if args.output.exists() else ""

    if args.check:
        if existing != rendered:
            print(f"CHANGELOG stale: regenerate with python scripts/generate_changelog.py --output {args.output}")
            return 1
        print("CHANGELOG is up to date.")
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
