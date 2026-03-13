# Migration Record — Deprecated Import Surfaces (2026-03-13)

## Scope

This migration records the deprecation decision for legacy import trees and documents the compatibility behavior.

## Deprecated trees

- `app/agents/*` → migrate to `adaad/agents/*`
- `app/root.py` → migrate to `adaad/core/root.py`

## Compatibility policy

- Deprecated modules are retained as redirect stubs.
- Redirect stubs emit `DeprecationWarning` at import time.
- New imports from deprecated paths are blocked by static import-boundary checks in `tools/lint_import_paths.py`.

## Required migration actions for callers

1. Replace imports from `app.agents.*` with `adaad.agents.*`.
2. Replace `from app.root import ...` with `from adaad.core.root import ...`.
3. Run `python tools/lint_import_paths.py` to verify no deprecated imports remain.

## Notes

This record satisfies governance deprecation traceability and compatibility communication requirements.
