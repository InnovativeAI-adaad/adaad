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
`PR-PHASE65-01`.
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
    expected_next_pr: "Phase 65 — First Autonomous Capability Evolution"
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
    "phase_sequence": [57, 58, 59, 60, 61, 62, 63, 64, 65],
    "next_pr": "PR-PHASE65-01",
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
`PR-PHASE66-01`.
`docs/governance/ADAAD_PR_PROCESSION_2026-03.md` is the source of truth.
""",
    )
    _write(
        tmp_path / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
        """# Procession
**Milestone:** `v8.6.0` (Phase 63 complete — Constitutional Closure)
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
| 64 | v8.7.0 | Phase 63 | next |
| 65 | v9.0.0 | Phase 64 | pending |
- Next: **Phase 66** (PR-PHASE65-01 — First Autonomous Capability Evolution).
All CI tiers green on a single tagged commit — Tier 0 through Tier 2.
```yaml
adaad_pr_procession_contract:
  active_phase: "phase64_complete"
  milestone: "v8.7.0"
  state_alignment:
    expected_next_pr: "Phase 65 — First Autonomous Capability Evolution"
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
**Milestone:** `v8.6.0` (Phase 63 complete — Constitutional Closure)
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
    expected_next_pr: "Phase 65 — First Autonomous Capability Evolution"
```
This document supersedes `docs/governance/ADAAD_PR_PROCESSION_2026-03.md` (archived).
""",
    )

    errors = validate(repo_root=tmp_path, rules_path=rules)

    messages = [e.message for e in errors]
    assert any("prose milestone phase mismatch" in msg for msg in messages)
    assert any("prose milestone version mismatch" in msg for msg in messages)
