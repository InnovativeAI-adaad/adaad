#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_HTML = ROOT / "docs" / "install.html"

SCRIPT_BLOCK_PATTERN = re.compile(r"<script>(?P<body>[\s\S]*?)</script>", re.IGNORECASE)
CATCH_BLOCK_PATTERN = re.compile(r"\.catch\s*\(\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{(?P<body>[\s\S]*?)\}\s*\)")
COMMENT_PATTERN = re.compile(r"/\*[\s\S]*?\*/|//[^\n]*")

CRITICAL_MARKERS = (
    "releases/latest",
    "copyFdroid",
    "serviceWorker.register",
)


def _strip_js_comments(source: str) -> str:
    return COMMENT_PATTERN.sub("", source)


def _is_effectively_empty(block_body: str) -> bool:
    return _strip_js_comments(block_body).strip() == ""


def main() -> int:
    html = INSTALL_HTML.read_text(encoding="utf-8")
    script_match = SCRIPT_BLOCK_PATTERN.search(html)
    if not script_match:
        print(json.dumps({"validator": "qa_install_html", "ok": False, "findings": ["missing <script> block"]}, sort_keys=True))
        return 1

    script_body = script_match.group("body")
    findings: list[str] = []

    for marker in CRITICAL_MARKERS:
        if marker not in script_body:
            findings.append(f"missing critical install marker: {marker}")

    for match in CATCH_BLOCK_PATTERN.finditer(script_body):
        body = match.group("body")
        if _is_effectively_empty(body):
            snippet = match.group(0).replace("\n", " ").strip()
            findings.append(f"empty catch block in install logic: {snippet}")

    payload = {
        "validator": "qa_install_html",
        "ok": not findings,
        "findings": findings,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
