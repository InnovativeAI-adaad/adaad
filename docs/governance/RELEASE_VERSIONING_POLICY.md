# Release Versioning Policy

## Purpose

Define one canonical release version source and enforce deterministic synchronization
across packaging metadata and release-facing documentation.

## Canonical Sources

1. `VERSION` is the canonical runtime release semver (`X.Y.Z`).
2. `pyproject.toml` (`[project].version`) must match `VERSION` exactly.

Any divergence is a blocking release/process failure.

## Managed Documentation Surfaces

The version sync guard currently manages these release-facing markers:

- `README.md`
  - ADAAD version badge (`img.shields.io/badge/ADAAD-vX.Y.Z-...`)
  - Hero alt-text version (`ADAAD vX.Y.Z — ...`)
- `docs/README.md`
  - ADAAD version badges
  - Intro runtime version reference (`ADAAD vX.Y.Z · Phase ...`)
  - Architecture map runtime header (`ADAAD vX.Y.Z Runtime`)
  - Footer runtime tag (`<code>ADAAD vX.Y.Z</code>`)
- `docs/governance/ARCHITECT_SPEC_v3.1.0.md`
  - Version badge label (`![Version: X.Y.Z]`)
  - Badge URL (`img.shields.io/badge/version-X.Y.Z-...`)

## Enforcement

- Sync/update command:
  - `python scripts/sync_versions.py`
- CI drift gate:
  - `python scripts/sync_versions.py --check`

`--check` fails when:

- `VERSION` is not strict semver.
- `pyproject.toml` version differs from `VERSION`.
- Any managed documentation marker differs from `VERSION`.

## Operational Rule

When bumping a release version:

1. Update `VERSION`.
2. Update `pyproject.toml` to the same value.
3. Run `python scripts/sync_versions.py`.
4. Commit all resulting docs changes in the same change set.
5. Ensure `python scripts/sync_versions.py --check` passes locally and in CI.
