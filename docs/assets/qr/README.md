# QR Asset Registry and Regeneration Workflow

This directory is governed by a deterministic QR generation workflow.

## Registry

Source of truth: [`registry.json`](./registry.json)

Each active target maps to:

- `asset_path`: generated SVG path.
- `target_url`: exact URL/deep-link encoded in the QR code.
- `placement`: canonical medium key used by `canonical_query_ledger.by_placement`.
- `canonical_query_ledger`: expected campaign/query params used for drift checks.

## Regenerate QR SVG assets

```bash
python scripts/generate_qr_assets.py
```

This command deterministically rewrites all QR SVG files at `docs/assets/qr/*.svg` from `registry.json` using fixed settings:

- stable registry iteration order,
- fixed QR error correction level (`M`),
- fixed border (`3` modules),
- fixed module size and SVG serialization.

## Validate in CI / pre-commit

```bash
python scripts/generate_qr_assets.py --check
```

`--check` fails if committed QR SVGs differ from regenerated output.

## Validate QR drift and campaign params

```bash
python scripts/validate_qr_drift.py --format json
```

This validator:

- enumerates active QR assets and target URLs,
- checks URL reachability and status class (`2xx`, `3xx`, etc.),
- compares observed query params to `canonical_query_ledger`,
- reports mismatches with asset ID plus expected vs observed params.

## Updating destinations

1. Edit `registry.json`.
2. Run `python scripts/generate_qr_assets.py`.
3. Commit both registry and generated SVG changes together.
4. Ensure `python scripts/generate_qr_assets.py --check` passes.
