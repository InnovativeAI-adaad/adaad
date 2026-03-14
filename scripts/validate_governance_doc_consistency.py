#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate governance docs for stale references and contradictory canonical values."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ValidationError:
    message: str


def _load_rules(rules_path: Path) -> dict[str, Any]:
    try:
        return json.loads(rules_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"[ADAAD BLOCKED] rules file missing: {rules_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[ADAAD BLOCKED] invalid JSON rules file {rules_path}: {exc}") from exc


def _load_documents(repo_root: Path, docs_config: dict[str, str]) -> dict[str, tuple[Path, str]]:
    loaded: dict[str, tuple[Path, str]] = {}
    for doc_id, rel_path in docs_config.items():
        path = repo_root / rel_path
        try:
            loaded[doc_id] = (path, path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SystemExit(f"[ADAAD BLOCKED] required governance document missing: {rel_path}") from exc
    return loaded


def _extract_phase_sequence(text: str) -> list[int] | None:
    match = re.search(r"(\d+\s*→\s*\d+(?:\s*→\s*\d+)+)", text)
    if not match:
        return None
    return [int(num) for num in re.findall(r"\d+", match.group(1))]


def _extract_required_tiers(text: str) -> list[int] | None:
    through_pattern = re.search(r"Tier\s+0\s+through\s+Tier\s+3", text, flags=re.IGNORECASE)
    if through_pattern:
        return [0, 1, 2, 3]
    ordered_tiers = [int(num) for num in re.findall(r"Tier\s+([0-3])", text)]
    if not ordered_tiers:
        return None
    unique_ordered = sorted(set(ordered_tiers))
    return unique_ordered if all(t in unique_ordered for t in (0, 1, 2, 3)) else None


def _has_required_tier_headings(text: str) -> bool:
    return all(re.search(rf"^###\s+Tier\s+{tier}\b", text, flags=re.MULTILINE) for tier in (0, 1, 2))


def _extract_next_pr(text: str) -> str | None:
    expected_match = re.search(r"expected_next_pr:\s*\"?(PR-PHASE\d+-\d+)", text)
    if expected_match:
        return expected_match.group(1)
    next_line_match = re.search(r"Next:\s*\*\*Phase\s*\d+\*\*.*?(PR-PHASE\d+-\d+)", text, flags=re.IGNORECASE)
    if next_line_match:
        return next_line_match.group(1)
    match = re.search(r"PR-PHASE\d+-\d+", text)
    return match.group(0) if match else None


def _extract_pr_ids(text: str) -> list[str]:
    return re.findall(r"PR-PHASE\d+-\d+", text)


def _find_stale_source_violations(
    loaded_docs: dict[str, tuple[Path, str]],
    archived_source: str,
    active_context_markers: list[str],
    archive_context_markers: list[str],
) -> list[ValidationError]:
    violations: list[ValidationError] = []
    for path, text in loaded_docs.values():
        for idx, line in enumerate(text.splitlines(), start=1):
            line_lower = line.lower()
            if archived_source.lower() not in line_lower:
                continue
            has_active_marker = any(marker in line_lower for marker in active_context_markers)
            has_archive_marker = any(marker in line_lower for marker in archive_context_markers)
            if has_active_marker and not has_archive_marker:
                violations.append(
                    ValidationError(
                        f"{path}:{idx} references archived procession doc as active source-of-truth: {line.strip()}"
                    )
                )
            if has_active_marker and "not" in line_lower and "archived" not in line_lower:
                violations.append(
                    ValidationError(
                        f"{path}:{idx} archived procession context is ambiguous and treated as stale-active: {line.strip()}"
                    )
                )
    return violations


def validate(repo_root: Path, rules_path: Path) -> list[ValidationError]:
    rules = _load_rules(rules_path)
    docs = _load_documents(repo_root, rules["documents"])
    canonical = rules["canonical"]

    errors: list[ValidationError] = []

    procession_text = docs["procession_v2"][1]
    ci_text = docs["ci_gating"][1]
    constitution_text = docs["constitution"][1]

    phase_sequence = _extract_phase_sequence(procession_text)
    if phase_sequence != canonical["phase_sequence"]:
        errors.append(
            ValidationError(
                f"{docs['procession_v2'][0]} phase sequence mismatch: expected {canonical['phase_sequence']} got {phase_sequence}"
            )
        )

    procession_next_pr = _extract_next_pr(procession_text)
    if procession_next_pr != canonical["next_pr"]:
        errors.append(
            ValidationError(
                f"{docs['procession_v2'][0]} next PR mismatch: expected {canonical['next_pr']} got {procession_next_pr}"
            )
        )

    ci_pr_ids = _extract_pr_ids(ci_text)
    if ci_pr_ids and canonical["next_pr"] not in ci_pr_ids:
        errors.append(
            ValidationError(
                f"{docs['ci_gating'][0]} references conflicting next PR set: expected to include {canonical['next_pr']} got {sorted(set(ci_pr_ids))}"
            )
        )

    required_tiers = canonical["required_ci_tiers"]
    procession_tiers = _extract_required_tiers(procession_text)
    if procession_tiers != required_tiers:
        errors.append(
            ValidationError(
                f"{docs['procession_v2'][0]} required CI tiers mismatch: expected {required_tiers} got {procession_tiers}"
            )
        )

    if not _has_required_tier_headings(constitution_text):
        errors.append(
            ValidationError(
                f"{docs['constitution'][0]} missing one or more canonical constitutional tier headings (Tier 0/1/2)"
            )
        )

    supersession = rules["supersession"]
    errors.extend(
        _find_stale_source_violations(
            docs,
            archived_source=supersession["archived_source"],
            active_context_markers=[m.lower() for m in supersession["active_context_markers"]],
            archive_context_markers=[m.lower() for m in supersession["archive_context_markers"]],
        )
    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="repository root path")
    parser.add_argument(
        "--rules",
        default="scripts/governance_doc_invariants.json",
        help="path to governance doc invariants rule file",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    rules_path = (repo_root / args.rules).resolve()
    errors = validate(repo_root=repo_root, rules_path=rules_path)

    if errors:
        print("[ADAAD BLOCKED] governance document consistency validation failed:")
        for error in errors:
            print(f" - {error.message}")
        return 1

    print("governance document consistency validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
