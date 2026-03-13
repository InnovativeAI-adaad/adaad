#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail CI if committed replay keyring files contain raw secret fields."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACKED_KEYRING_FILES = [
    REPO_ROOT / "security" / "replay_proof_keyring.json",
]
FORBIDDEN_SECRET_FIELDS = frozenset({"hmac_secret", "private_key"})


def _forbidden_paths(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, dict):
        return []
    violations: list[str] = []
    for key_id, key_payload in keys.items():
        if not isinstance(key_payload, dict):
            continue
        for field in sorted(FORBIDDEN_SECRET_FIELDS):
            if field in key_payload:
                try:
                    location = str(path.relative_to(REPO_ROOT))
                except ValueError:
                    location = str(path)
                violations.append(f"{location}:{key_id}.{field}")
    return violations


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail if replay keyring files contain committed secrets.")
    parser.add_argument("--path", action="append", default=[], help="Optional keyring path override (repeatable).")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    file_paths = [Path(item) for item in args.path] or TRACKED_KEYRING_FILES
    violations: list[str] = []
    for file_path in file_paths:
        violations.extend(_forbidden_paths(file_path))
    if violations:
        print("replay_keyring_secret_guard:failed")
        for violation in violations:
            print(f"- forbidden_secret_field:{violation}")
        return 1
    print("replay_keyring_secret_guard:ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
