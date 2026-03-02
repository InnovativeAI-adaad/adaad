#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed verification for boot/CI critical signed artifacts."""

from __future__ import annotations
from runtime.boot.artifact_verifier import verify_required_artifacts


def main() -> int:
    try:
        checks = verify_required_artifacts()
    except ValueError as exc:
        raise SystemExit(f"critical_artifact_verification_failed:{exc}") from exc
    for name, fingerprint in sorted(checks.items()):
        print(f"{name}:{fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
