#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import qrcode
import qrcode.image.svg

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs/assets/qr/registry.json"


def main() -> int:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    targets = payload.get("targets", [])
    generated = 0

    for target in targets:
        if not isinstance(target, dict) or not target.get("active"):
            continue
        asset_path = ROOT / str(target["asset_path"])
        target_url = str(target["target_url"])
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=3, box_size=10)
        qr.add_data(target_url)
        qr.make(fit=True)
        image = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        image.save(asset_path)
        generated += 1

    print(f"Generated {generated} QR assets from {REGISTRY_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
