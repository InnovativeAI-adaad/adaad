#!/usr/bin/env python3
"""Deterministically generate QR SVG assets from docs/assets/qr/registry.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs/assets/qr/registry.json"
QR_OUTPUT_DIR = REPO_ROOT / "docs/assets/qr"

ALLOWED_PURPOSES = {"apk", "obtainium", "pwa", "fdroid", "install_page"}
BORDER_MODULES = 3


def _load_registry(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("QR registry root must be an object")

    normalized: dict[str, dict[str, Any]] = {}
    for asset_id in sorted(data):
        entry = data[asset_id]
        if not isinstance(entry, dict):
            raise ValueError(f"Registry entry for {asset_id!r} must be an object")

        destination = entry.get("canonical_destination_url")
        purpose = entry.get("purpose")
        campaign_tags = entry.get("campaign_tags")

        if not isinstance(destination, str) or not destination:
            raise ValueError(f"{asset_id!r} missing canonical_destination_url")
        if purpose not in ALLOWED_PURPOSES:
            raise ValueError(
                f"{asset_id!r} has invalid purpose {purpose!r}; allowed={sorted(ALLOWED_PURPOSES)}"
            )
        if not isinstance(campaign_tags, dict):
            raise ValueError(f"{asset_id!r} campaign_tags must be an object")

        normalized[asset_id] = {
            "canonical_destination_url": destination,
            "purpose": purpose,
            "campaign_tags": {k: campaign_tags[k] for k in sorted(campaign_tags)},
        }
    return normalized


def _svg_for_url(url: str) -> str:
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Missing dependency 'qrcode'. Install via requirements.dev.txt before running this script."
        ) from exc

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=1,
        border=BORDER_MODULES,
    )
    qr.add_data(url)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("QR matrix is not square")

    segments: list[str] = []
    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                segments.append(f"M{x},{y}H{x + 1}V{y + 1}H{x}z")

    path_d = "".join(segments)
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        f"<svg width=\"{size}mm\" height=\"{size}mm\" version=\"1.1\" "
        f"viewBox=\"0 0 {size} {size}\" xmlns=\"http://www.w3.org/2000/svg\">"
        f"<path d=\"{path_d}\" id=\"qr-path\" fill=\"#000000\" fill-opacity=\"1\" "
        "fill-rule=\"nonzero\" stroke=\"none\"/></svg>\n"
    )


def _write_or_diff(expected: str, destination: Path, check: bool) -> bool:
    current = destination.read_text(encoding="utf-8") if destination.exists() else None
    if current == expected:
        return False
    if check:
        return True
    destination.write_text(expected, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed QR SVG assets match deterministic regeneration output.",
    )
    args = parser.parse_args()

    registry = _load_registry(REGISTRY_PATH)
    changed_assets: list[str] = []

    for asset_id, entry in registry.items():
        output_path = QR_OUTPUT_DIR / f"{asset_id}.svg"
        expected_svg = _svg_for_url(entry["canonical_destination_url"])
        if _write_or_diff(expected_svg, output_path, args.check):
            changed_assets.append(str(output_path.relative_to(REPO_ROOT)))

    if args.check and changed_assets:
        print("QR asset drift detected:")
        for path in changed_assets:
            print(f" - {path}")
        return 1

    if changed_assets:
        mode = "Verified (would update)" if args.check else "Generated"
        print(f"{mode} {len(changed_assets)} QR assets:")
        for path in changed_assets:
            print(f" - {path}")
    else:
        print("QR assets are up to date.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
