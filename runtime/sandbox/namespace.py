# SPDX-License-Identifier: Apache-2.0
"""Namespace isolation capability detection."""

from __future__ import annotations

import os


def namespace_isolation_available() -> bool:
    return os.name == "posix"


__all__ = ["namespace_isolation_available"]
