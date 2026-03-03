# SPDX-License-Identifier: Apache-2.0
"""Default repository scanning rules for intake workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ScanRules:
    skip_dirs: set[str] = field(default_factory=lambda: {".git", "__pycache__", ".venv"})
    skip_suffixes: set[str] = field(default_factory=lambda: {".pyc", ".pyo"})
    max_flag_file_size_bytes: int = 1_000_000

    def should_skip(self, path: Path) -> bool:
        return any(part in self.skip_dirs for part in path.parts) or path.suffix in self.skip_suffixes
