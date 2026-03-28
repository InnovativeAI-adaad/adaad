import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from scripts.validate_governance_doc_consistency import validate


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_docs(tmp_path: Path) -> Path:
    _write(
        tmp_path / "docs/CONSTITUTION.md",
        """# Constitution
### Tier 0: Production
### Tier 1: Stable
### Tier 2: Sandbox
""",
    )
    _write(tmp_path / "docs/ARCHITECTURE_CONTRACT.md", "# Architecture\n")
    _write(tmp_path / "docs/governance/SECURITY_INVARIANTS_MATRIX.md", "# Security\n")
    _write(
        tmp_path / "docs/governance/ci-gating.md",
        """# CI
All CI tiers green on a single tagged commit — Tier 0 through Tier 3.
`PR-PHASE94-01`.
""",
    )
    _write(
        tmp_path / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
        """# Procession
**Milestone:** `v9.26.0` (Phase 93 complete — INNOV-09 Aesthetic Fitness Signal)
57 → 58 → 59 → 60 → 61 → 62 → 63 → 64 → 65 → 66 → 67 → 68 → 69 → 70 → 71 → 72 → 73 → 74 → 75 → 76 → 77 → 78 → 79 → 80 → 81 → 82 → 83 → 84 → 85 → 86 → 87 → 88 → 89 → 90 → 91 → 92 → 93
| Phase | Version | Depends on | Status |
|---|---|---|---|
| 57 | v8.0.0 | Phase 53 complete | shipped |
| 58 | v8.1.0 | Phase 57 | shipped |
| 59 | v8.2.0 | Phase 58 | shipped |
| 60 | v8.3.0 | Phase 59 | shipped |
| 61 | v8.4.0 | Phase 60 | shipped |
| 62 | v8.5.0 | Phase 61 | shipped |
| 63 | v8.6.0 | Phase 62 | shipped |
| 64 | v8.7.0 | Phase 63 | shipped |
| 65 | v9.0.0 | Phase 64 | shipped |
| 66 | v9.1.0 | Phase 65 | shipped |
| 67 | v9.2.0 | Phase 66 | shipped |
| 68 | v9.3.0 | Phase 67 | shipped |
| 69 | v9.4.0 | Phase 68 | shipped |
| 70 | v9.5.0 | Phase 69 | shipped |
| 71 | v9.6.0 | Phase 70 | shipped |
| 72 | v9.7.0 | Phase 71 | shipped |
| 73 | v9.8.0 | Phase 72 | shipped |
| 74 | v9.9.0 | Phase 73 | shipped |
| 75 | v9.10.0 | Phase 74 | shipped |
| 76 | v9.11.0 | Phase 75 | shipped |
| 77 | v9.13.0 | Phase 76 | shipped |
| 78 | v9.14.0 | Phase 77 | shipped |
| 79 | v9.14.0 | Phase 78 | shipped |
| 80 | v9.15.0 | Phase 79 | shipped |
| 81 | v9.16.0 | Phase 80 | shipped |
| 82 | v9.16.0 | Phase 81 | shipped |
| 83 | v9.16.0 | Phase 82 | shipped |
| 84 | v9.16.0 | Phase 83 | shipped |
| 85 | v9.17.0 | Phase 84 | shipped |
| 86 | v9.17.0 | Phase 85 | shipped |
| 87 | v9.18.0 | Phase 86 | shipped |
| 88 | v9.19.0 | Phase 87 | shipped |
| 89 | v9.22.0 | Phase 88 | shipped |
| 90 | v9.24.0 | Phase 89 | shipped |
| 91 | v9.24.1 | Phase 90 | shipped |
| 92 | v9.25.0 | Phase 91 | shipped |
| 93 | v9.26.0 | Phase 92 | shipped |
- Next: **Phase 94** — INNOV-10 roadmap execution.
All CI tiers green on a single tagged commit — Tier 0 through Tier 3.
```yaml
adaad_pr_procession_contract:
  active_phase: "phase93_complete"
  milestone: "v9.26.0"
  state_alignment:
    expected_next_pr: "Phase 94 — INNOV-10 roadmap execution"
```
This document supersedes `docs/governance/ADAAD_PR_PROCESSION_2026-03.md` (archived).
""",
    )
    _write(
        tmp_path / "scripts/governance_doc_invariants.json",
        """{
  "documents": {
    "constitution": "docs/CONSTITUTION.md",
    "architecture_contract": "docs/ARCHITECTURE_CONTRACT.md",
    "security_invariants": "docs/governance/SECURITY_INVARIANTS_MATRIX.md",
    "ci_gating": "docs/governance/ci-gating.md",
    "procession_v2": "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md"
  },
  "supersession": {
    "active_source": "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
    "archived_source": "docs/governance/ADAAD_PR_PROCESSION_2026-03.md",
    "active_context_markers": ["source of truth", "controlling source", "canonical source"],
    "archive_context_markers": ["archived", "supersede", "superseded", "supersedes"]
  },
  "canonical": {
    "phase_sequence": [57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93],
    "next_pr": "Phase 94 — INNOV-10 roadmap execution",
    "required_ci_tiers": [0, 1, 2, 3]
  }
}
""",
    )
    return tmp_path / "scripts/governance_doc_invariants.json"


def test_validator_accepts_consistent_docs(tmp_path: Path) -> None:
    rules = _seed_docs(tmp_path)
    errors = validate(repo_root=tmp_path, rules_path=rules)
    assert errors == []


def test_validator_rejects_conflicting_docs(tmp_path: Path) -> None:
    rules = _seed_docs(tmp_path)
    _write(
        tmp_path / "docs/governance/ci-gating.md",
        """# CI
`PR-PHASE95-01`.
`docs/governance/ADAAD_PR_PROCESSION_2026-03.md` is the source of truth.
""",
    )
    _write(
        tmp_path / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
        """# Procession
**Milestone:** `v9.25.0` (Phase 92 complete — INNOV-08 AFRT)
57 → 58 → 59 → 60 → 61 → 62 → 63 → 64 → 65 → 66 → 67 → 68 → 69 → 70 → 71 → 72 → 73 → 74 → 75 → 76 → 77 → 78 → 79 → 80 → 81 → 82 → 83 → 84 → 85 → 86 → 87 → 88 → 89 → 90 → 91 → 92 → 93
| Phase | Version | Depends on | Status |
|---|---|---|---|
| 57 | v8.0.0 | Phase 53 complete | shipped |
| 58 | v8.1.0 | Phase 57 | shipped |
| 59 | v8.2.0 | Phase 58 | shipped |
| 60 | v8.3.0 | Phase 59 | shipped |
| 61 | v8.4.0 | Phase 60 | shipped |
| 62 | v8.5.0 | Phase 61 | shipped |
| 63 | v8.6.0 | Phase 62 | shipped |
| 64 | v8.7.0 | Phase 63 | shipped |
| 65 | v9.0.0 | Phase 64 | shipped |
| 66 | v9.1.0 | Phase 65 | shipped |
| 67 | v9.2.0 | Phase 66 | shipped |
| 68 | v9.3.0 | Phase 67 | shipped |
| 69 | v9.4.0 | Phase 68 | shipped |
| 70 | v9.5.0 | Phase 69 | shipped |
| 71 | v9.6.0 | Phase 70 | shipped |
| 72 | v9.7.0 | Phase 71 | shipped |
| 73 | v9.8.0 | Phase 72 | shipped |
| 74 | v9.9.0 | Phase 73 | shipped |
| 75 | v9.10.0 | Phase 74 | shipped |
| 76 | v9.11.0 | Phase 75 | shipped |
| 77 | v9.13.0 | Phase 76 | shipped |
| 78 | v9.14.0 | Phase 77 | shipped |
| 79 | v9.14.0 | Phase 78 | shipped |
| 80 | v9.15.0 | Phase 79 | shipped |
| 81 | v9.16.0 | Phase 80 | shipped |
| 82 | v9.16.0 | Phase 81 | shipped |
| 83 | v9.16.0 | Phase 82 | shipped |
| 84 | v9.16.0 | Phase 83 | shipped |
| 85 | v9.17.0 | Phase 84 | shipped |
| 86 | v9.17.0 | Phase 85 | shipped |
| 87 | v9.18.0 | Phase 86 | shipped |
| 88 | v9.19.0 | Phase 87 | shipped |
| 89 | v9.22.0 | Phase 88 | shipped |
| 90 | v9.24.0 | Phase 89 | shipped |
| 91 | v9.24.1 | Phase 90 | shipped |
| 92 | v9.25.0 | Phase 91 | next |
| 93 | v9.26.0 | Phase 92 | pending |
- Next: **Phase 95** — Cross-Epoch Dream State.
All CI tiers green on a single tagged commit — Tier 0 through Tier 2.
```yaml
adaad_pr_procession_contract:
  active_phase: "phase93_complete"
  milestone: "v9.26.0"
  state_alignment:
    expected_next_pr: "Phase 94 — INNOV-10 roadmap execution"
```
This document supersedes `docs/governance/ADAAD_PR_PROCESSION_2026-03.md` (archived).
""",
    )

    errors = validate(repo_root=tmp_path, rules_path=rules)

    messages = [e.message for e in errors]
    assert any("required CI tiers mismatch" in msg for msg in messages)
    assert any("conflicting next PR" in msg for msg in messages)
    assert any("archived procession doc as active source-of-truth" in msg for msg in messages)
    assert any("prose milestone phase mismatch" in msg for msg in messages)
    assert any("prose milestone version mismatch" in msg for msg in messages)
    assert any("prose next phase mismatch" in msg for msg in messages)
    assert any("phase summary table has stale next markers" in msg for msg in messages)


def test_validator_rejects_prose_yaml_milestone_divergence(tmp_path: Path) -> None:
    rules = _seed_docs(tmp_path)
    _write(
        tmp_path / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
        """# Procession
**Milestone:** `v9.25.0` (Phase 92 complete — INNOV-08 AFRT)
57 → 58 → 59 → 60 → 61 → 62 → 63 → 64 → 65 → 66 → 67 → 68 → 69 → 70 → 71 → 72 → 73 → 74 → 75 → 76 → 77 → 78 → 79 → 80 → 81 → 82 → 83 → 84 → 85 → 86 → 87 → 88 → 89 → 90 → 91 → 92 → 93
| Phase | Version | Depends on | Status |
|---|---|---|---|
| 57 | v8.0.0 | Phase 53 complete | shipped |
| 58 | v8.1.0 | Phase 57 | shipped |
| 59 | v8.2.0 | Phase 58 | shipped |
| 60 | v8.3.0 | Phase 59 | shipped |
| 61 | v8.4.0 | Phase 60 | shipped |
| 62 | v8.5.0 | Phase 61 | shipped |
| 63 | v8.6.0 | Phase 62 | shipped |
| 64 | v8.7.0 | Phase 63 | shipped |
| 65 | v9.0.0 | Phase 64 | shipped |
| 66 | v9.1.0 | Phase 65 | shipped |
| 67 | v9.2.0 | Phase 66 | shipped |
| 68 | v9.3.0 | Phase 67 | shipped |
| 69 | v9.4.0 | Phase 68 | shipped |
| 70 | v9.5.0 | Phase 69 | shipped |
| 71 | v9.6.0 | Phase 70 | shipped |
| 72 | v9.7.0 | Phase 71 | shipped |
| 73 | v9.8.0 | Phase 72 | shipped |
| 74 | v9.9.0 | Phase 73 | shipped |
| 75 | v9.10.0 | Phase 74 | shipped |
| 76 | v9.11.0 | Phase 75 | shipped |
| 77 | v9.13.0 | Phase 76 | shipped |
| 78 | v9.14.0 | Phase 77 | shipped |
| 79 | v9.14.0 | Phase 78 | shipped |
| 80 | v9.15.0 | Phase 79 | shipped |
| 81 | v9.16.0 | Phase 80 | shipped |
| 82 | v9.16.0 | Phase 81 | shipped |
| 83 | v9.16.0 | Phase 82 | shipped |
| 84 | v9.16.0 | Phase 83 | shipped |
| 85 | v9.17.0 | Phase 84 | shipped |
| 86 | v9.17.0 | Phase 85 | shipped |
| 87 | v9.18.0 | Phase 86 | shipped |
| 88 | v9.19.0 | Phase 87 | shipped |
| 89 | v9.22.0 | Phase 88 | shipped |
| 90 | v9.24.0 | Phase 89 | shipped |
| 91 | v9.24.1 | Phase 90 | shipped |
| 92 | v9.25.0 | Phase 91 | shipped |
| 93 | v9.26.0 | Phase 92 | shipped |
- Next: **Phase 94** — INNOV-10 roadmap execution.
All CI tiers green on a single tagged commit — Tier 0 through Tier 3.
```yaml
adaad_pr_procession_contract:
  active_phase: "phase93_complete"
  milestone: "v9.26.0"
  state_alignment:
    expected_next_pr: "Phase 94 — INNOV-10 roadmap execution"
```
This document supersedes `docs/governance/ADAAD_PR_PROCESSION_2026-03.md` (archived).
""",
    )

    errors = validate(repo_root=tmp_path, rules_path=rules)

    messages = [e.message for e in errors]
    assert any("prose milestone phase mismatch" in msg for msg in messages)
    assert any("prose milestone version mismatch" in msg for msg in messages)


def test_validator_accepts_legacy_pr_id_in_state_alignment(tmp_path: Path) -> None:
    rules = _seed_docs(tmp_path)
    _write(
        tmp_path / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
        """# Procession
**Milestone:** `v8.7.0` (Phase 64 complete — Constitutional Closure)
57 → 58 → 59 → 60 → 61 → 62 → 63 → 64 → 65
| Phase | Version | Depends on | Status |
|---|---|---|---|
| 57 | v8.0.0 | Phase 53 complete | shipped |
| 58 | v8.1.0 | Phase 57 | shipped |
| 59 | v8.2.0 | Phase 58 | shipped |
| 60 | v8.3.0 | Phase 59 | shipped |
| 61 | v8.4.0 | Phase 60 | shipped |
| 62 | v8.5.0 | Phase 61 | shipped |
| 63 | v8.6.0 | Phase 62 | shipped |
| 64 | v8.7.0 | Phase 63 | shipped |
| 65 | v9.0.0 | Phase 64 | next |
- Next: **Phase 65** (PR-PHASE65-01 — First Autonomous Capability Evolution).
All CI tiers green on a single tagged commit — Tier 0 through Tier 3.
```yaml
adaad_pr_procession_contract:
  active_phase: "phase64_complete"
  milestone: "v8.7.0"
  state_alignment:
    expected_next_pr: "PR-PHASE65-01"
```
This document supersedes `docs/governance/ADAAD_PR_PROCESSION_2026-03.md` (archived).
""",
    )
    errors = validate(repo_root=tmp_path, rules_path=rules)
    assert errors == []


def test_validator_accepts_phase_label_with_legacy_canonical(tmp_path: Path) -> None:
    rules = _seed_docs(tmp_path)
    errors = validate(repo_root=tmp_path, rules_path=rules)
    assert errors == []


def test_validator_reports_mixed_format_next_pr_mismatch_with_exact_values(tmp_path: Path) -> None:
    rules = _seed_docs(tmp_path)
    _write(
        rules,
        """{
  "documents": {
    "constitution": "docs/CONSTITUTION.md",
    "architecture_contract": "docs/ARCHITECTURE_CONTRACT.md",
    "security_invariants": "docs/governance/SECURITY_INVARIANTS_MATRIX.md",
    "ci_gating": "docs/governance/ci-gating.md",
    "procession_v2": "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md"
  },
  "supersession": {
    "active_source": "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
    "archived_source": "docs/governance/ADAAD_PR_PROCESSION_2026-03.md",
    "active_context_markers": ["source of truth", "controlling source", "canonical source"],
    "archive_context_markers": ["archived", "supersede", "superseded", "supersedes"]
  },
  "canonical": {
    "phase_sequence": [57, 58, 59, 60, 61, 62, 63, 64, 65],
    "next_pr": "PR-PHASE66-01",
    "required_ci_tiers": [0, 1, 2, 3]
  }
}
""",
    )
    _write(
        tmp_path / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
        """# Procession
**Milestone:** `v8.7.0` (Phase 64 complete — Constitutional Closure)
57 → 58 → 59 → 60 → 61 → 62 → 63 → 64 → 65
| Phase | Version | Depends on | Status |
|---|---|---|---|
| 57 | v8.0.0 | Phase 53 complete | shipped |
| 58 | v8.1.0 | Phase 57 | shipped |
| 59 | v8.2.0 | Phase 58 | shipped |
| 60 | v8.3.0 | Phase 59 | shipped |
| 61 | v8.4.0 | Phase 60 | shipped |
| 62 | v8.5.0 | Phase 61 | shipped |
| 63 | v8.6.0 | Phase 62 | shipped |
| 64 | v8.7.0 | Phase 63 | shipped |
| 65 | v9.0.0 | Phase 64 | next |
- Next: **Phase 65** (PR-PHASE65-01 — First Autonomous Capability Evolution).
All CI tiers green on a single tagged commit — Tier 0 through Tier 3.
```yaml
adaad_pr_procession_contract:
  active_phase: "phase64_complete"
  milestone: "v8.7.0"
  state_alignment:
    expected_next_pr: "Phase 94 — Contradictory Fixture"
```
This document supersedes `docs/governance/ADAAD_PR_PROCESSION_2026-03.md` (archived).
""",
    )
    errors = validate(repo_root=tmp_path, rules_path=rules)
    messages = [e.message for e in errors]
    assert any(
        "next PR mismatch: extracted='Phase 94 — Contradictory Fixture', expected_canonical='PR-PHASE66-01'" in msg
        for msg in messages
    )
