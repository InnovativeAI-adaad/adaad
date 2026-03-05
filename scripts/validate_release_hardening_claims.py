#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail release validation when release notes over-claim unavailable sandbox hardening."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.sandbox.isolation import runtime_hardening_capabilities

RELEASE_NOTES_DIR = Path("docs/releases")

HARDENING_CLAIM_PATTERNS = {
    "kernel_seccomp_filter_enforcement": (
        "in-kernel seccomp",
        "kernel seccomp",
        "seccomp filter enforced in-kernel",
        "fully hardened seccomp",
    ),
    "namespace_cgroup_hard_isolation": (
        "hard namespace isolation",
        "namespace hard isolation",
        "hard cgroup isolation",
        "namespace/cgroup hard isolation",
        "fully hardened sandbox isolation",
    ),
}


def _iter_release_notes() -> list[Path]:
    if not RELEASE_NOTES_DIR.exists():
        return []
    return sorted(path for path in RELEASE_NOTES_DIR.glob("*.md") if path.is_file())


def main() -> int:
    runtime_caps = runtime_hardening_capabilities(container_rollout_enabled=False)
    errors: list[str] = []

    for note in _iter_release_notes():
        text = note.read_text(encoding="utf-8").lower()
        for capability, patterns in HARDENING_CLAIM_PATTERNS.items():
            if any(pattern in text for pattern in patterns):
                enabled = bool(runtime_caps[capability]["implemented"])
                if not enabled:
                    errors.append(
                        f"{note}: claims '{capability}' hardening but runtime capability checks report disabled status"
                    )

    if errors:
        print("Release hardening claim validation failed:")
        for err in errors:
            print(f" - {err}")
        return 1

    print("Release hardening claim validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
