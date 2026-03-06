#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate active phase/PR alignment and canonical-spec consistency across active docs."""

from __future__ import annotations

import json
import re
from pathlib import Path

AGENTS_PATH = Path("AGENTS.md")
STATE_PATH = Path(".adaad_agent_state.json")
SPEC_PATH = Path("docs/governance/ARCHITECT_SPEC_v3.0.0.md")
CANONICAL_SPEC_PATH = "docs/governance/ARCHITECT_SPEC_v3.0.0.md"
CANONICAL_SPEC_BASENAME = "ARCHITECT_SPEC_v3.0.0.md"

HIGH_VISIBILITY_ENTRYPOINTS = [
    Path("README.md"),
    Path("docs/README.md"),
    Path("docs/manifest.txt"),
]


def _extract_agents_next_heading(text: str) -> str | None:
    match = re.search(r"^###\s+(.+?)\s+\(next\)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_first_pr_id_from_next_table(text: str) -> str | None:
    heading_match = re.search(r"^###\s+.+?\s+\(next\)\s*$", text, flags=re.MULTILINE)
    if not heading_match:
        return None
    tail = text[heading_match.end() :]
    row_match = re.search(r"^\|\s*(PR-[A-Z0-9-]+)\s*\|", tail, flags=re.MULTILINE)
    return row_match.group(1).strip() if row_match else None


def _extract_phase5_first_pr_from_spec(text: str) -> str | None:
    section = re.search(
        r"^##\s+5\.\s+Phase 5 PR Sequence\s*$([\s\S]*?)(?:^##\s+|\Z)",
        text,
        flags=re.MULTILINE,
    )
    if not section:
        return None
    pr_match = re.search(r"^###\s+(PR-PHASE5-\d{2})\s*:", section.group(1), flags=re.MULTILINE)
    return pr_match.group(1).strip() if pr_match else None


def _validate_canonical_spec_claims(errors: list[str]) -> None:
    for entrypoint in HIGH_VISIBILITY_ENTRYPOINTS:
        text = entrypoint.read_text(encoding="utf-8")
        if CANONICAL_SPEC_BASENAME not in text:
            errors.append(f"{entrypoint}: missing active canonical spec reference: {CANONICAL_SPEC_PATH}")

    docs_root = Path("docs")
    for path in docs_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        rel = path.as_posix()
        if rel.startswith("docs/archive/"):
            continue

        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            if "canonical" in lower and "architect_spec_v2.0.0.md" in lower:
                if "superseded" not in lower and "historical" not in lower:
                    errors.append(
                        f"{path}:{line_no}: canonical claim points to v2 without explicit historical/superseded labeling"
                    )


def main() -> int:
    errors: list[str] = []

    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: missing file: {STATE_PATH}")
        return 1

    agents_text = AGENTS_PATH.read_text(encoding="utf-8")
    spec_text = SPEC_PATH.read_text(encoding="utf-8")

    state_next_pr = str(state.get("next_pr", "")).strip()
    state_active_phase = str(state.get("active_phase", "")).strip()

    agents_next_heading = _extract_agents_next_heading(agents_text)
    agents_next_pr = _extract_first_pr_id_from_next_table(agents_text)
    spec_phase5_first_pr = _extract_phase5_first_pr_from_spec(spec_text)

    if not state_next_pr:
        errors.append(".adaad_agent_state.json: next_pr is empty")

    if not agents_next_heading:
        errors.append("AGENTS.md: unable to locate '(next)' phase heading")

    if not agents_next_pr:
        errors.append("AGENTS.md: unable to locate first PR in the '(next)' phase table")

    if not spec_phase5_first_pr:
        errors.append("ARCHITECT_SPEC_v3.0.0.md: unable to locate first PR in section '5. Phase 5 PR Sequence'")

    if agents_next_heading and "phase 5" not in agents_next_heading.lower():
        errors.append(f"AGENTS.md: active '(next)' heading is not Phase 5: {agents_next_heading!r}")

    if state_active_phase and "phase 5" not in state_active_phase.lower():
        errors.append(".adaad_agent_state.json: active_phase does not indicate Phase 5")

    if state_next_pr and state_active_phase and state_next_pr not in state_active_phase:
        errors.append(
            ".adaad_agent_state.json: active_phase does not include next_pr token "
            f"({state_next_pr})"
        )

    if state_next_pr and agents_next_pr and state_next_pr != agents_next_pr:
        errors.append(
            f"state/AGENTS mismatch: state next_pr={state_next_pr!r}, AGENTS next table first PR={agents_next_pr!r}"
        )

    if state_next_pr and spec_phase5_first_pr and state_next_pr != spec_phase5_first_pr:
        errors.append(
            "state/spec mismatch: "
            f"state next_pr={state_next_pr!r}, spec phase-5 first PR={spec_phase5_first_pr!r}"
        )

    _validate_canonical_spec_claims(errors)

    if errors:
        print("Phase sequence consistency validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(
        "Phase sequence consistency validation passed: "
        f"active_phase=Phase 5, next_pr={state_next_pr}, spec_first_pr={spec_phase5_first_pr}, "
        f"canonical_spec={CANONICAL_SPEC_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
