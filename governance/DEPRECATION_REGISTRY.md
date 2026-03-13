# DEPRECATION REGISTRY

- **record_type**: deprecation_registry
- **schema_version**: 2.0.0
- **registry_status**: active
- **maintainer_group**: governance-council
- **last_updated**: 2026-03-13

## Process Metadata

- **governance_workflow**: propose-review-deprecate-retire
- **required_approvals**: 2
- **signature_scheme**: ed25519
- **signature_threshold**: 2-of-3
- **registry_artifact**: governance/attestations/deprecation_registry.json

## Active Deprecations

| item_id | description | replaced_by | deprecation_state | effective_at |
|---------|-------------|-------------|-------------------|--------------|
| `root-governance-impl` | Implementation logic in root `governance/` | `runtime/governance/` canonical layer | retired | 2025-12-01 |
| `archives/adad_core` | Legacy monolithic core module | Distributed `runtime/` subsystems | retired | 2025-11-01 |
| `archives/backend` | Legacy backend scaffolding | `app/main.py` + `runtime/` | retired | 2025-11-01 |
| `archives/dashboard` | Legacy dashboard | `ui/aponi_dashboard.py` | retired | 2025-12-01 |
| `app/root.py` | Legacy root wiring shim | `adaad/core/root.py` canonical import target | deprecated | 2026-03-13 |
| `adaad/agents/` | Legacy agent stubs (pre-AI pipeline) | `runtime/autonomy/ai_mutation_proposer.py` | deprecated | 2026-03-06 |
| `app/agents/` | Legacy agent namespace compatibility tree | `adaad/agents/` canonical namespace | deprecated | 2026-03-13 |
| `docs/archive/EPIC_*.md` | Per-epic planning docs | `CHANGELOG.md` + `docs/releases/` | archived | 2026-03-06 |
| `docs/archive/PR_v1.0.0_body.md` | PR body artifact | `docs/releases/1.0.0.md` | archived | 2026-03-06 |

## Notes

Items in state `retired` have been moved to `archives/` or deleted.
Items in state `deprecated` are still present but must not be extended.
Items in state `archived` are preserved in `docs/archive/` for audit lineage.

### 2026-03-13 migration decision

- `app/agents/*` and `app/root.py` remain import-compatibility redirect stubs only.
- Stubs now emit `DeprecationWarning` to guide migration toward canonical imports.
- New production imports from deprecated surfaces are blocked by static lint (`tools/lint_import_paths.py`).
