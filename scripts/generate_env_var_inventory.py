#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate deterministic env-var inventory into docs/ENVIRONMENT_VARIABLES.md."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_START = "<!-- ENV_VAR_INVENTORY:START -->"
INVENTORY_END = "<!-- ENV_VAR_INVENTORY:END -->"
SCAN_ROOTS: tuple[str, ...] = ("app", "runtime", "security", "scripts")
SCAN_EXTENSIONS: frozenset[str] = frozenset({".py", ".sh", ".yml", ".yaml"})
SKIP_PREFIXES: tuple[str, ...] = (
    ".git/",
    ".venv/",
    "venv/",
    "node_modules/",
    "dist/",
    "build/",
    "site-packages/",
    "archives/",
)

_PYTHON_PATTERNS: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r'os\.getenv\(\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "os.getenv"),
    (re.compile(r'os\.environ\.get\(\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "os.environ.get"),
    (re.compile(r'os\.environ\[\s*["\']([A-Z][A-Z0-9_]{2,})["\']\s*\]'), 1, "os.environ[key]"),
    (re.compile(r'os\.environ\.setdefault\(\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "os.environ.setdefault"),
    (re.compile(r'_env_true\(\s*\w+\s*,\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "_env_true"),
    (re.compile(r'_is_truthy_env\(\s*os\.getenv\(\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "_is_truthy_env(os.getenv)"),
    (re.compile(r'\benv\.get\(\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "env.get"),
    (re.compile(r'_parse_csv_env\(\s*os\.getenv\(\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "_parse_csv_env(os.getenv)"),
    (re.compile(r'_bound_from_env\(\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "_bound_from_env"),
    (re.compile(r'_legacy_feature_enabled\(\s*["\']([A-Z][A-Z0-9_]{2,})["\']'), 1, "_legacy_feature_enabled"),
]

_SHELL_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r'\$\{?([A-Z][A-Z0-9_]{2,})\}?'), 1),
    (re.compile(r':\s+["\']?\$\{([A-Z][A-Z0-9_]{2,})'), 1),
]

_BUILTIN_SKIP: frozenset[str] = frozenset(
    {
        "HOME",
        "PATH",
        "PYTHONPATH",
        "CI",
        "GITHUB_OUTPUT",
        "GITHUB_STEP_SUMMARY",
        "GITHUB_SHA",
        "GITHUB_REF",
        "GITHUB_ACTOR",
        "GITHUB_TOKEN",
        "GITHUB_WORKSPACE",
        "GITHUB_EVENT_NAME",
        "GITHUB_RUN_ID",
        "IFS",
        "PWD",
        "OLDPWD",
        "TERM",
        "USER",
        "SHELL",
        "LANG",
        "VIRTUAL_ENV",
        "VIRTUAL_ENV_PROMPT",
    }
)
_REQUIRED_PREFIXES: tuple[str, ...] = ("ADAAD_", "CRYOVANT_", "GITHUB_WEBHOOK_")


@dataclass(frozen=True, order=True)
class EnvRef:
    var_name: str
    source_file: str
    line_number: int
    default_value: str
    pattern_tag: str


@dataclass
class EnvVarEntry:
    var_name: str
    refs: list[EnvRef] = field(default_factory=list)

    @property
    def defaults(self) -> list[str]:
        return sorted({r.default_value for r in self.refs if r.default_value})

    @property
    def files(self) -> list[str]:
        return sorted({r.source_file for r in self.refs})


def _fatal(code: str, message: str) -> None:
    print(json.dumps({"event": code, "message": message}), flush=True)
    raise SystemExit(1)


def _emit(event: str, payload: dict[str, object]) -> None:
    print(json.dumps({"event": event, **payload}), flush=True)


def _is_adaad_var(name: str) -> bool:
    if name in _BUILTIN_SKIP:
        return False
    return any(name.startswith(prefix) for prefix in _REQUIRED_PREFIXES)


def _extract_default(line: str, var_name: str) -> str:
    pattern = re.compile(
        r'["\']' + re.escape(var_name) + r'["\']' + r'\s*,\s*' + r'["\']([^"\']*)["\']'
    )
    match = pattern.search(line)
    return match.group(1) if match else ""


def _scan_python_file(path: Path) -> Iterator[EnvRef]:
    rel = path.relative_to(ROOT).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        _fatal("ENV_INV_ERROR_READ", f"Cannot read {rel}: {exc}")

    try:
        ast.parse(source)
    except SyntaxError:
        pass

    for line_number, line in enumerate(source.splitlines(), start=1):
        for pattern, group, tag in _PYTHON_PATTERNS:
            for match in pattern.finditer(line):
                var_name = match.group(group)
                if _is_adaad_var(var_name):
                    yield EnvRef(
                        var_name=var_name,
                        source_file=rel,
                        line_number=line_number,
                        default_value=_extract_default(line, var_name),
                        pattern_tag=tag,
                    )


def _scan_shell_file(path: Path) -> Iterator[EnvRef]:
    rel = path.relative_to(ROOT).as_posix()
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _fatal("ENV_INV_ERROR_READ", f"Cannot read {rel}: {exc}")

    for line_number, line in enumerate(source.splitlines(), start=1):
        if line.strip().startswith("#"):
            continue
        for pattern, group in _SHELL_PATTERNS:
            for match in pattern.finditer(line):
                var_name = match.group(group)
                if _is_adaad_var(var_name):
                    yield EnvRef(
                        var_name=var_name,
                        source_file=rel,
                        line_number=line_number,
                        default_value="",
                        pattern_tag="shell",
                    )


def _collect_refs() -> dict[str, EnvVarEntry]:
    entries: dict[str, EnvVarEntry] = {}

    def add_ref(ref: EnvRef) -> None:
        entries.setdefault(ref.var_name, EnvVarEntry(var_name=ref.var_name)).refs.append(ref)

    for root_name in SCAN_ROOTS:
        root = ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if any(rel.startswith(prefix) for prefix in SKIP_PREFIXES):
                continue
            if path.suffix not in SCAN_EXTENSIONS:
                continue
            if path.suffix == ".py":
                for ref in _scan_python_file(path):
                    add_ref(ref)
            else:
                for ref in _scan_shell_file(path):
                    add_ref(ref)

    return entries


_TABLE_HEADER = """<!-- DO NOT EDIT BETWEEN THESE MARKERS — regenerate with: -->
<!--   python scripts/generate_env_var_inventory.py           -->

| Variable | Default | Source files | Line(s) |
| --- | --- | --- | --- |"""


def _render_table(entries: dict[str, EnvVarEntry]) -> str:
    rows = [_TABLE_HEADER]
    for var_name in sorted(entries):
        entry = entries[var_name]
        defaults = ", ".join(f"`{value}`" for value in entry.defaults) or "_(none)_"
        files = ", ".join(f"`{file_name}`" for file_name in entry.files)
        line_map: dict[str, list[int]] = {}
        for ref in sorted(entry.refs):
            line_map.setdefault(ref.source_file, []).append(ref.line_number)
        lines = " · ".join(
            f"`{file_name}`:{','.join(str(n) for n in sorted(set(line_numbers)))}"
            for file_name, line_numbers in sorted(line_map.items())
        )
        rows.append(f"| `{var_name}` | {defaults} | {files} | {lines} |")
    return "\n".join(rows) + "\n"


def _splice_into_doc(doc_path: Path, table: str) -> tuple[str, bool]:
    try:
        original = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        _fatal("ENV_INV_ERROR_READ", f"Cannot read {doc_path}: {exc}")

    start = original.find(INVENTORY_START)
    end = original.find(INVENTORY_END)
    if start == -1 or end == -1 or end <= start:
        try:
            label = doc_path.relative_to(ROOT).as_posix()
        except ValueError:
            label = str(doc_path)
        _fatal(
            "ENV_INV_ERROR_SENTINEL",
            f"{label} is missing sentinel markers {INVENTORY_START!r} / {INVENTORY_END!r}.",
        )

    before = original[: start + len(INVENTORY_START)]
    after = original[end:]
    new_content = f"{before}\n{table}{after}"
    return new_content, new_content != original


def _content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate env-var inventory into docs/ENVIRONMENT_VARIABLES.md"
    )
    parser.add_argument("--check", action="store_true", help="Exit non-zero if inventory is stale")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)

    doc_path = ROOT / "docs" / "ENVIRONMENT_VARIABLES.md"
    if not doc_path.exists():
        _fatal("ENV_INV_ERROR_MISSING_DOC", f"{doc_path} does not exist.")

    _emit("scan_start", {"roots": list(SCAN_ROOTS)})
    entries = _collect_refs()
    _emit("scan_complete", {"unique_vars": len(entries)})
    table = _render_table(entries)
    new_content, changed = _splice_into_doc(doc_path, table)

    if args.check:
        if changed:
            _emit(
                "stale",
                {
                    "message": "docs/ENVIRONMENT_VARIABLES.md inventory is stale. Run generator.",
                    "unique_vars": len(entries),
                },
            )
            return 1
        _emit("fresh", {"unique_vars": len(entries), "sha256": _content_sha256(new_content)})
        return 0

    if changed:
        doc_path.write_text(new_content, encoding="utf-8")
        _emit(
            "written",
            {
                "file": "docs/ENVIRONMENT_VARIABLES.md",
                "unique_vars": len(entries),
                "sha256": _content_sha256(new_content),
            },
        )
    else:
        _emit("no_change", {"unique_vars": len(entries)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
