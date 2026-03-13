# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
"""


Canonical agent discovery for He65.

Supports both layouts:
  1) app/agents/<agent_id>/
  2) app/agents/<bucket>/<agent_id>/

An agent directory is defined by the presence of the REQUIRED_FILES set.
"""

_AGENT_CONTRACT_EXCLUDED = True  # utility module — not a governed agent contract

import json
from pathlib import Path
from typing import Iterable, Optional

REQUIRED_FILES = ("meta.json", "dna.json", "certificate.json")


def _is_excluded(entry: Path) -> bool:
    name = entry.name
    return name.startswith("__") or name.startswith(".") or name in {"lineage", "agent_template"}


def is_agent_dir(path: Path) -> bool:
    return path.is_dir() and all((path / req).exists() for req in REQUIRED_FILES)


def iter_agent_dirs(agents_root: Path) -> Iterable[Path]:
    """
    Deterministically yield agent directories, skipping non-agent folders.
    """
    if not agents_root.exists():
        return

    for entry in sorted(agents_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if _is_excluded(entry):
            continue

        if is_agent_dir(entry):
            yield entry
            continue

        # Treat as a bucket container; yield valid child agent dirs.
        for child in sorted(entry.iterdir(), key=lambda p: p.name):
            if not child.is_dir():
                continue
            if _is_excluded(child):
                continue
            if is_agent_dir(child):
                yield child


def resolve_agent_id(agent_dir: Path, agents_root: Path) -> str:
    """
    Stable identifier for ledger and metrics: relative path, slashes replaced by colons.
    """
    rel = agent_dir.resolve().relative_to(agents_root.resolve()).as_posix()
    return rel.replace("/", ":")


def agent_path_from_id(agent_id: str, agents_root: Path) -> Path:
    """
    Convert a canonical agent_id back to a filesystem path under agents_root.
    """
    return agents_root / agent_id.replace(":", "/")


def resolve_agent_module_entrypoint(agent_dir: Path) -> Optional[Path]:
    """
    Resolve an agent implementation module path for AST contract validation.

    Resolution order:
      1) <agent_dir>/__init__.py
      2) meta.json keys: module, module_path, entrypoint, python_module
         where values may be:
           - relative file path ("impl.py", "pkg/impl.py")
           - module path ("pkg.impl") -> pkg/impl.py or pkg/impl/__init__.py
    """
    init_py = agent_dir / "__init__.py"
    if init_py.exists():
        return init_py

    meta_path = agent_dir / "meta.json"
    if not meta_path.exists():
        return None

    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    for key in ("module", "module_path", "entrypoint", "python_module"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            continue

        candidate = value.strip()
        relative_file = (agent_dir / candidate).resolve()
        if relative_file.is_file() and relative_file.suffix == ".py":
            return relative_file

        module_parts = candidate.replace("/", ".").split(".")
        module_path = agent_dir.joinpath(*[part for part in module_parts if part])
        for possible in (module_path.with_suffix(".py"), module_path / "__init__.py"):
            if possible.exists() and possible.is_file():
                return possible

    return None
