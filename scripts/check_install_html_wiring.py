#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_HTML = ROOT / "docs" / "install.html"


REQUIRED_DOM_IDS = (
    "apk-btn",
    "apk-fallback-msg",
    "obtainium-btn",
    "fdroid-copy-btn",
    "fdroid-copied",
)

REQUIRED_SCRIPT_SNIPPETS = (
    "function warnInstallIssue(",
    "function showInstallDebugHint(",
    "new URLSearchParams(window.location.search).has('debug-install')",
    "obBtn.addEventListener('click'",
    "function copyFdroid()",
)


def main() -> int:
    html = INSTALL_HTML.read_text(encoding="utf-8")
    missing: list[str] = []

    for dom_id in REQUIRED_DOM_IDS:
        token = f'id="{dom_id}"'
        if token not in html:
            missing.append(f"missing DOM id: {dom_id}")

    for snippet in REQUIRED_SCRIPT_SNIPPETS:
        if snippet not in html:
            missing.append(f"missing script wiring: {snippet}")

    payload = {
        "validator": "install_html_wiring",
        "ok": not missing,
        "missing": missing,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
