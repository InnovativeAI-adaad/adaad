#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate active phase/PR alignment and canonical-spec consistency across active docs.

Updated for v3.0.0: validator is now phase-agnostic (previously hardcoded to Phase 5).
It reads the active phase from .adaad_agent_state.json and validates that AGENTS.md
(next) heading and next_pr are internally consistent — without requiring a specific
phase number to be active.
"""

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
    tail = text[heading_match.end():]
    row_match = re.search(r"^\|\s*(PR-[A-Z0-9-]+)\s*\|", tail, flags=re.MULTILINE)
    return row_match.group(1).strip() if row_match else None


def _extract_active_phase_label(state_active_phase: str) -> str:
    """Extract a short phase label like 'phase 5' or 'phase 6' from active_phase string."""
    match = re.search(r"phase\s+(\d+)", state_active_phase, flags=re.IGNORECASE)
    if match:
        return f"phase {match.group(1)}"
    return ""


def _validate_canonical_spec_claims(errors: list[str]) -> None:
    for entrypoint in HIGH_VISIBILITY_ENTRYPOINTS:
        if not entrypoint.exists():
            continue
        text = entrypoint.read_text(encoding="utf-8")
        if CANONICAL_SPEC_BASENAME not in text:
            errors.append(
                f"{entrypoint}: missing active canonical spec reference: {CANONICAL_SPEC_PATH}"
            )

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
                        f"{path}:{line_no}: canonical claim points to v2 without "
                        "explicit historical/superseded labeling"
                    )


def main() -> int:
    errors: list[str] = []

    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: missing file: {STATE_PATH}")
        return 1

    agents_text = AGENTS_PATH.read_text(encoding="utf-8")

    state_next_pr = str(state.get("next_pr", "")).strip()
    state_active_phase = str(state.get("active_phase", "")).strip()
    active_phase_label = _extract_active_phase_label(state_active_phase)

    agents_next_heading = _extract_agents_next_heading(agents_text)
    agents_next_pr = _extract_first_pr_id_from_next_table(agents_text)

    if not state_next_pr:
        errors.append(".adaad_agent_state.json: next_pr is empty")

    if not agents_next_heading:
        errors.append("AGENTS.md: unable to locate '(next)' phase heading")

    if not agents_next_pr:
        errors.append("AGENTS.md: unable to locate first PR in the '(next)' phase table")

    # Phase label consistency: state active_phase and AGENTS (next) heading must agree
    if active_phase_label and agents_next_heading:
        if active_phase_label.lower() not in agents_next_heading.lower():
            errors.append(
                f"AGENTS.md: active '(next)' heading phase label ({agents_next_heading!r}) "
                f"does not match state active_phase label ({active_phase_label!r})"
            )

    # next_pr must match AGENTS (next) table first PR
    if state_next_pr and agents_next_pr and state_next_pr != agents_next_pr:
        errors.append(
            f"state/AGENTS mismatch: state next_pr={state_next_pr!r}, "
            f"AGENTS next table first PR={agents_next_pr!r}"
        )

    _validate_canonical_spec_claims(errors)

    if errors:
        print("Phase sequence consistency validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(
        "Phase sequence consistency validation passed: "
        f"active_phase={active_phase_label or state_active_phase!r}, "
        f"next_pr={state_next_pr}, "
        f"AGENTS_next={agents_next_heading!r}, "
        f"canonical_spec={CANONICAL_SPEC_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
