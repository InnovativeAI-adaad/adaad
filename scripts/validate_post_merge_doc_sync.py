#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate post-merge docs sync contract consistency for phase-governance PRs."""

from __future__ import annotations

import re
from pathlib import Path

CONTRACT_PATH = Path("docs/governance/post_merge_doc_sync_contract.yaml")
ROADMAP_PATH = Path("ROADMAP.md")
PROCESSION_PATH = Path("docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md")
EVIDENCE_MATRIX_PATH = Path("docs/comms/claims_evidence_matrix.md")


def _parse_contract(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise ValueError(f"missing contract file: {path.as_posix()}")

    contracts: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    active_list_key: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        if raw_line.startswith("contracts:"):
            continue

        if raw_line.startswith("  - pr_id:"):
            if current:
                contracts.append(current)
            current = {
                "pr_id": raw_line.split(":", 1)[1].strip(),
                "required_docs": [],
                "required_gates": [],
                "evidence_claim_ids": [],
            }
            active_list_key = None
            continue

        if current is None:
            continue

        stripped = raw_line.strip()
        if stripped.endswith(":"):
            key = stripped[:-1]
            if key in {"required_docs", "required_gates", "evidence_claim_ids"}:
                active_list_key = key
                continue

        if stripped.startswith("-") and active_list_key:
            value = stripped[1:].strip().strip('"')
            list_values = current.setdefault(active_list_key, [])
            assert isinstance(list_values, list)
            list_values.append(value)
            continue

        active_list_key = None
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip().strip('"')

    if current:
        contracts.append(current)

    if not contracts:
        raise ValueError("contract file defines no PR contracts")
    return contracts


def _extract_phase_status(line: str) -> str | None:
    lowered = line.lower()
    for token in ("next", "pending", "active", "shipped", "merged", "complete"):
        if token in lowered:
            return token
    return None


def _find_phase_line(text: str, phase_id: str, release_version: str) -> str | None:
    for line in text.splitlines():
        if f"| {phase_id} |" in line and release_version in line:
            return line
    return None


def _collect_evidence_completion_status(text: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|.*\|\s*([^|]+)\s*\|\s*$")
    for line in text.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        statuses[match.group(1).strip()] = match.group(2).strip()
    return statuses


def main() -> int:
    errors: list[str] = []

    try:
        contracts = _parse_contract(CONTRACT_PATH)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    roadmap_text = ROADMAP_PATH.read_text(encoding="utf-8")
    procession_text = PROCESSION_PATH.read_text(encoding="utf-8")
    evidence_statuses = _collect_evidence_completion_status(
        EVIDENCE_MATRIX_PATH.read_text(encoding="utf-8")
    )

    for contract in contracts:
        pr_id = str(contract.get("pr_id", "")).strip()
        merge_state = str(contract.get("merge_state", "pending")).strip().lower()
        phase_id = str(contract.get("phase_id", "")).strip()
        release_version = str(contract.get("release_version", "")).strip()
        expected_phase_status = str(contract.get("expected_phase_status", "")).strip().lower()

        if not pr_id:
            errors.append("contract entry missing pr_id")
            continue

        docs = contract.get("required_docs", [])
        if isinstance(docs, list):
            for doc in docs:
                doc_path = Path(str(doc))
                if not doc_path.exists():
                    errors.append(f"{pr_id}: required doc is missing: {doc_path.as_posix()}")

        for gate in contract.get("required_gates", []):
            gate_token = str(gate)
            if gate_token.lower() == "evidence complete":
                continue
            if gate_token not in roadmap_text:
                errors.append(f"{pr_id}: gate token missing from ROADMAP.md: {gate_token}")
            if gate_token not in procession_text:
                errors.append(
                    f"{pr_id}: gate token missing from ADAAD procession doc: {gate_token}"
                )

        if merge_state != "merged":
            continue

        if not phase_id or not release_version:
            errors.append(f"{pr_id}: merged contracts require phase_id and release_version")
            continue

        roadmap_line = _find_phase_line(roadmap_text, phase_id, release_version)
        procession_line = _find_phase_line(procession_text, phase_id, release_version)

        if roadmap_line is None:
            errors.append(f"{pr_id}: no roadmap phase row found for phase {phase_id} v{release_version}")
        if procession_line is None:
            errors.append(
                f"{pr_id}: no procession phase row found for phase {phase_id} v{release_version}"
            )

        if roadmap_line and procession_line:
            roadmap_status = _extract_phase_status(roadmap_line)
            procession_status = _extract_phase_status(procession_line)
            if roadmap_status != procession_status:
                errors.append(
                    f"{pr_id}: phase status misalignment roadmap={roadmap_status!r} "
                    f"procession={procession_status!r}"
                )
            if expected_phase_status and roadmap_status != expected_phase_status:
                errors.append(
                    f"{pr_id}: roadmap phase status {roadmap_status!r} does not match "
                    f"expected {expected_phase_status!r}"
                )

        release_note_path = Path(f"docs/releases/{release_version}.md")
        if not release_note_path.exists():
            errors.append(f"{pr_id}: release note missing: {release_note_path.as_posix()}")
        else:
            note_text = release_note_path.read_text(encoding="utf-8")
            if release_version not in note_text:
                errors.append(
                    f"{pr_id}: release note {release_note_path.as_posix()} does not mention {release_version}"
                )

        claim_ids = contract.get("evidence_claim_ids", [])
        if isinstance(claim_ids, list):
            for claim_id in claim_ids:
                claim_status = evidence_statuses.get(str(claim_id), "")
                if claim_status.lower() != "complete":
                    errors.append(
                        f"{pr_id}: evidence claim {claim_id!r} is not Complete (status={claim_status!r})"
                    )

    if errors:
        print("Post-merge docs sync contract validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(
        "Post-merge docs sync contract validation passed: "
        f"{len(contracts)} contract(s) checked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
