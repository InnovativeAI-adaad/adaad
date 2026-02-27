#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SNIPPETS = {
    "README.md": [
        "Governance & Determinism Guarantees (Current State)",
        "ADAAD_DISPATCH_LATENCY_BUDGET_MS",
        "ADAAD_DETERMINISTIC_LOCK",
    ],
    "runtime/README.md": [
        "Deterministic Guarantees",
    ],
    "ui/README.md": [
        "Aponi URL is derived from runtime constants",
    ],
    "docs/releases/RELEASE_AUDIT_CHECKLIST.md": [
        "Replay on two independent environments",
        "Constitution checksum verified",
    ],
}


def main() -> int:
    missing: list[str] = []
    for rel, snippets in REQUIRED_SNIPPETS.items():
        path = ROOT / rel
        if not path.exists():
            missing.append(f"missing_file:{rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                missing.append(f"missing_snippet:{rel}:{snippet}")
    if missing:
        for item in missing:
            print(item)
        return 1
    print("readme_alignment_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
