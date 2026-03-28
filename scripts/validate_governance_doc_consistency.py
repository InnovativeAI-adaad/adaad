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
    shipped_phases = [
        int(match.group("phase"))
        for match in re.finditer(
            r'^\|\s*(?P<phase>\d+)\s*\|\s*[^|]+\|\s*[^|]+\|\s*shipped\s*\|$',
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    ]
    if shipped_phases:
        unique_shipped = sorted(set(shipped_phases))
        if unique_shipped == list(range(unique_shipped[0], unique_shipped[-1] + 1)):
            return unique_shipped
        return shipped_phases

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
    expected_match = re.search(r'^\s*expected_next_pr:\s*"(?P<next>[^"]+)"', text, flags=re.MULTILINE)
    if expected_match:
        return expected_match.group("next")
    next_line_match = re.search(r"Next:\s*\*\*Phase\s*\d+\*\*(?:\s*[-—]\s*[^.\n]+)?", text, flags=re.IGNORECASE)
    if next_line_match:
        return next_line_match.group(0).split(":", maxsplit=1)[1].strip().strip(".")
    next_pr_id_match = re.search(r"Next:\s*\*\*Phase\s*\d+\*\*.*?(PR-PHASE\d+-\d+)", text, flags=re.IGNORECASE)
    if next_pr_id_match:
        return next_pr_id_match.group(1)
    match = re.search(r"PR-PHASE\d+-\d+", text)
    return match.group(0) if match else None


def _extract_phase_from_next_identifier(value: str | None) -> int | None:
    if not value:
        return None
    pr_id_match = re.search(r"PR-PHASE(?P<phase>\d+)-\d+", value, flags=re.IGNORECASE)
    if pr_id_match:
        return int(pr_id_match.group("phase"))
    phase_label_match = re.search(r"\bPhase\s+(?P<phase>\d+)\b", value, flags=re.IGNORECASE)
    if phase_label_match:
        return int(phase_label_match.group("phase"))
    return None


def _extract_pr_ids(text: str) -> list[str]:
    return re.findall(r"PR-PHASE\d+-\d+", text)


def _extract_prose_milestone(text: str) -> tuple[int, str] | None:
    match = re.search(
        r"^\*\*Milestone:\*\*\s*`(?P<version>[^`]+)`\s*\(Phase\s+(?P<phase>\d+)\s+complete\b",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None
    return int(match.group("phase")), match.group("version")


def _extract_contract_active_phase(text: str) -> int | None:
    match = re.search(r'^\s*active_phase:\s*"phase(?P<phase>\d+)_complete"', text, flags=re.MULTILINE)
    if not match:
        return None
    return int(match.group("phase"))


def _extract_contract_milestone(text: str) -> str | None:
    match = re.search(r'^\s*milestone:\s*"(?P<milestone>[^"]+)"', text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group("milestone")


def _extract_state_alignment_next(text: str) -> str | None:
    match = re.search(r'^\s*expected_next_pr:\s*"(?P<next>[^"]+)"', text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group("next")


def _extract_prose_next_phase(text: str) -> int | None:
    match = re.search(r'^-\s+Next:\s+\*\*Phase\s+(?P<phase>\d+)\*\*', text, flags=re.MULTILINE)
    if not match:
        return None
    return int(match.group("phase"))


def _extract_phase_table_statuses(text: str) -> dict[int, str]:
    statuses: dict[int, str] = {}
    for match in re.finditer(
        r'^\|\s*(?P<phase>\d+)\s*\|\s*[^|]+\|\s*[^|]+\|\s*(?P<status>[^|]+?)\s*\|$',
        text,
        flags=re.MULTILINE,
    ):
        statuses[int(match.group("phase"))] = match.group("status").strip().lower()
    return statuses


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

    prose_milestone = _extract_prose_milestone(procession_text)
    contract_active_phase = _extract_contract_active_phase(procession_text)
    contract_milestone = _extract_contract_milestone(procession_text)
    if prose_milestone and contract_active_phase is not None and prose_milestone[0] != contract_active_phase:
        errors.append(
            ValidationError(
                f"{docs['procession_v2'][0]} prose milestone phase mismatch: expected Phase {contract_active_phase} got Phase {prose_milestone[0]}"
            )
        )
    if prose_milestone and contract_milestone and prose_milestone[1] != contract_milestone:
        errors.append(
            ValidationError(
                f"{docs['procession_v2'][0]} prose milestone version mismatch: expected {contract_milestone} got {prose_milestone[1]}"
            )
        )

    procession_next_pr = _extract_next_pr(procession_text)
    canonical_next_pr = canonical["next_pr"]
    procession_next_phase = _extract_phase_from_next_identifier(procession_next_pr)
    canonical_next_phase = _extract_phase_from_next_identifier(canonical_next_pr)
    if procession_next_pr != canonical_next_pr and procession_next_phase != canonical_next_phase:
        errors.append(
            ValidationError(
                f"{docs['procession_v2'][0]} next PR mismatch: expected {canonical_next_pr} got {procession_next_pr}"
            )
        )

    ci_pr_ids = _extract_pr_ids(ci_text)
    ci_declares_next_pr = bool(
        re.search(r"\b(next\s+pr|expected_next_pr)\b", ci_text, flags=re.IGNORECASE) or len(set(ci_pr_ids)) == 1
    )
    canonical_ci_pr_matches = [pr_id for pr_id in ci_pr_ids if _extract_phase_from_next_identifier(pr_id) == canonical_next_phase]
    if ci_declares_next_pr and ci_pr_ids and canonical_next_pr not in ci_pr_ids and not canonical_ci_pr_matches:
        errors.append(
            ValidationError(
                f"{docs['ci_gating'][0]} references conflicting next PR set: expected to include {canonical_next_pr} got {sorted(set(ci_pr_ids))}"
            )
        )

    prose_next_phase = _extract_prose_next_phase(procession_text)
    state_alignment_next = _extract_state_alignment_next(procession_text)
    if prose_next_phase is not None and state_alignment_next is not None:
        state_alignment_next_phase = _extract_phase_from_next_identifier(state_alignment_next)
        if state_alignment_next_phase != prose_next_phase:
            errors.append(
                ValidationError(
                    f"{docs['procession_v2'][0]} prose next phase mismatch: expected state_alignment.expected_next_pr phase {prose_next_phase!r} got {state_alignment_next!r}"
                )
            )

    phase_table_statuses = _extract_phase_table_statuses(procession_text)
    if contract_active_phase is not None and phase_table_statuses:
        active_status = phase_table_statuses.get(contract_active_phase)
        if active_status == "next":
            errors.append(
                ValidationError(
                    f"{docs['procession_v2'][0]} phase summary table marks active phase {contract_active_phase} as next"
                )
            )
        stale_next = [phase for phase, status in phase_table_statuses.items() if phase <= contract_active_phase and status == "next"]
        if stale_next:
            errors.append(
                ValidationError(
                    f"{docs['procession_v2'][0]} phase summary table has stale next markers at phases {sorted(stale_next)}"
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
