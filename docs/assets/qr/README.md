# QR Asset Registry and Regeneration Workflow

This directory is governed by a deterministic QR generation workflow.

## Registry

Source of truth: [`registry.json`](./registry.json)

Each asset ID maps to:

- `canonical_destination_url`: exact URL/deep-link encoded in the QR code.
- `purpose`: one of `apk`, `obtainium`, `pwa`, `fdroid`, `install_page`.
- `campaign_tags`: campaign metadata (kept sorted for deterministic diffs).

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

## Updating destinations

1. Edit `registry.json`.
2. Run `python scripts/generate_qr_assets.py`.
3. Commit both registry and generated SVG changes together.
4. Ensure `python scripts/generate_qr_assets.py --check` passes.
