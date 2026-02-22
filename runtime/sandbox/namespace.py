# SPDX-License-Identifier: Apache-2.0
"""Namespace isolation capability detection."""

from __future__ import annotations

from contextlib import contextmanager
import shutil
import subprocess
import sys
from typing import Iterator



def namespace_isolation_available() -> bool:
    return sys.platform.startswith("linux")


@contextmanager
def enter_user_namespace() -> Iterator[dict[str, object]]:
    """Best-effort user namespace entry with deterministic graceful fallback.

    This helper never raises on unsupported platforms or missing utilities.
    """

    if not namespace_isolation_available():
        yield {"entered": False, "reason": "non_linux", "fallback": "no_op"}
        return

    unshare_bin = shutil.which("unshare")
    if not unshare_bin:
        yield {"entered": False, "reason": "unshare_unavailable", "fallback": "no_op"}
        return

    try:
        probe = subprocess.run(
            [unshare_bin, "--user", "--map-root-user", "true"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        yield {"entered": False, "reason": "unshare_exec_error", "fallback": "no_op"}
        return

    if probe.returncode != 0:
        yield {
            "entered": False,
            "reason": "unshare_failed",
            "returncode": probe.returncode,
            "fallback": "no_op",
        }
        return

    yield {"entered": True, "reason": "unshare_probe_ok"}


__all__ = ["enter_user_namespace", "namespace_isolation_available"]
