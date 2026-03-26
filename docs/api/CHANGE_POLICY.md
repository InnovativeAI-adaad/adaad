# API Change & Deprecation Policy

## Scope
This policy governs all HTTP and WebSocket endpoints exposed by ADAAD under:

- Legacy namespace: `/api/...`
- Versioned namespace: `/api/v1/...`

## Versioning Contract
- New public endpoints **must** be introduced under `/api/v1/...`.
- Existing `/api/...` routes remain available as compatibility aliases during migration.
- Backward-incompatible changes require a new major API namespace (for example `/api/v2/...`).

## Deprecation Lifecycle
1. **Announce**
   - Mark endpoint as deprecated in OpenAPI (`deprecated: true`).
   - Add migration guidance to `docs/api/V1_REFERENCE.md`.
2. **Warn**
   - Return `Deprecation: true` response header.
   - Return `Sunset: <RFC 7231 date>` response header.
3. **Sunset**
   - Minimum notice period: **90 days** for externally consumable endpoints.
   - Endpoint removal only after the announced sunset date.

## Non-Breaking Changes
The following are considered non-breaking for `v1`:
- Adding optional response fields.
- Adding new endpoints.
- Adding new optional request fields with safe defaults.

## Breaking Changes
The following require a new major namespace:
- Removing or renaming endpoint paths.
- Removing response fields.
- Changing response field types.
- Making previously optional request fields required.

## OpenAPI Artifact
The shipped contract artifact is `docs/api/openapi.v1.json` and is generated with:

```bash
python scripts/export_openapi.py
```

Any endpoint change must regenerate and commit this artifact in the same change set.
