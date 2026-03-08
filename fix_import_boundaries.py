#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AST-guided import boundary fixer.

In ``--mode auto`` this tool will only apply a fix when it can safely move an
import into a single consuming function/method. Otherwise it records a manual
suggestion and leaves source unchanged.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FixRecord:
    path: str
    line: int
    import_stmt: str
    classification: str  # "applied" | "manual"
    reason: str
    consumer: str | None = None


class _UsageCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.bound_name_usage: dict[str, set[str | None]] = {}
        self.function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def _scope_name(self) -> str | None:
        return self.stack[-1] if self.stack else None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        qual = ".".join([*self.stack, node.name]) if self.stack else node.name
        self.function_nodes[qual] = node
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        qual = ".".join([*self.stack, node.name]) if self.stack else node.name
        self.function_nodes[qual] = node
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        self.bound_name_usage.setdefault(node.id, set()).add(self._scope_name())


def _bound_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    names: list[str] = []
    for alias in node.names:
        if alias.asname:
            names.append(alias.asname)
        elif isinstance(node, ast.Import):
            names.append(alias.name.split(".")[0])
        else:
            names.append(alias.name)
    return names


def _statement_text(lines: list[str], node: ast.AST) -> str:
    start = max(getattr(node, "lineno", 1) - 1, 0)
    end = max(getattr(node, "end_lineno", getattr(node, "lineno", 1)), getattr(node, "lineno", 1))
    return "".join(lines[start:end]).strip()


def _is_top_level_import(node: ast.AST) -> bool:
    return isinstance(node, (ast.Import, ast.ImportFrom))


def _import_text(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        names = ", ".join([f"{a.name} as {a.asname}" if a.asname else a.name for a in node.names])
        return f"import {names}"
    module = "." * node.level + (node.module or "")
    names = ", ".join([f"{a.name} as {a.asname}" if a.asname else a.name for a in node.names])
    return f"from {module} import {names}"


def _insert_line_for_function(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    if not fn_node.body:
        return fn_node.lineno
    first_stmt = fn_node.body[0]
    if (
        isinstance(first_stmt, ast.Expr)
        and isinstance(getattr(first_stmt, "value", None), ast.Constant)
        and isinstance(first_stmt.value.value, str)
    ):
        return first_stmt.end_lineno or first_stmt.lineno
    return first_stmt.lineno - 1


def _indent_for_function(fn_node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]) -> str:
    idx = max(fn_node.lineno - 1, 0)
    line = lines[idx]
    return line[: len(line) - len(line.lstrip())] + "    "


def _verify(path: Path) -> tuple[bool, str]:
    proc = subprocess.run([sys.executable, "-m", "py_compile", str(path)], capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return True, "verified"
    return False, (proc.stderr or proc.stdout or "py_compile failed").strip()


def _apply_file(path: Path, mode: str) -> tuple[list[FixRecord], bool]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source, filename=str(path))

    collector = _UsageCollector()
    collector.visit(tree)

    records: list[FixRecord] = []
    edits: list[tuple[str, int, int, str | None]] = []

    top_level_imports = [node for node in tree.body if _is_top_level_import(node)]
    for node in top_level_imports:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        # Keep future imports untouched.
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue

        bound_names = _bound_names(node)
        consumers_by_name = [collector.bound_name_usage.get(name, set()) for name in bound_names]
        merged_consumers: set[str | None] = set().union(*consumers_by_name) if consumers_by_name else set()

        stmt = _statement_text(lines, node)
        if not merged_consumers:
            records.append(FixRecord(str(path), node.lineno, stmt, "manual", "unused_or_unresolved_usage"))
            continue

        if None in merged_consumers:
            records.append(FixRecord(str(path), node.lineno, stmt, "manual", "module_scope_usage_detected"))
            continue

        if len(merged_consumers) != 1:
            records.append(FixRecord(str(path), node.lineno, stmt, "manual", "multiple_consumers"))
            continue

        consumer = next(iter(merged_consumers))
        fn_node = collector.function_nodes.get(consumer or "")
        if fn_node is None:
            records.append(FixRecord(str(path), node.lineno, stmt, "manual", "consumer_not_function", consumer=consumer))
            continue

        if mode != "auto":
            records.append(FixRecord(str(path), node.lineno, stmt, "manual", "dry_run_only", consumer=consumer))
            continue

        import_stmt = _import_text(node)
        insert_after = _insert_line_for_function(fn_node)
        indent = _indent_for_function(fn_node, lines)
        start = node.lineno - 1
        end = (node.end_lineno or node.lineno)
        edits.append(("remove", start, end, None))
        edits.append(("insert", insert_after, insert_after, f"{indent}{import_stmt}\n"))
        records.append(FixRecord(str(path), node.lineno, stmt, "applied", "moved_to_consumer", consumer=consumer))

    if mode != "auto" or not edits:
        return records, False

    updated_lines = list(lines)
    for kind, start, end, payload in sorted(edits, key=lambda item: (item[1], 0 if item[0] == "insert" else 1), reverse=True):
        if kind == "remove":
            del updated_lines[start:end]
        else:
            updated_lines.insert(start, payload or "")

    new_source = "".join(updated_lines)
    if new_source == source:
        return records, False

    original = source
    path.write_text(new_source, encoding="utf-8")
    ok, reason = _verify(path)
    if not ok:
        path.write_text(original, encoding="utf-8")
        rolled_back: list[FixRecord] = []
        for rec in records:
            if rec.classification == "applied":
                rolled_back.append(
                    FixRecord(rec.path, rec.line, rec.import_stmt, "manual", f"verification_failed:{reason}", rec.consumer)
                )
            else:
                rolled_back.append(rec)
        return rolled_back, False

    return records, True


def _iter_paths(raw: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for item in raw:
        candidate = Path(item)
        if candidate.is_file() and candidate.suffix == ".py":
            paths.append(candidate)
            continue
        if candidate.is_dir():
            paths.extend(sorted(candidate.rglob("*.py")))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fix import boundary violations safely")
    parser.add_argument("paths", nargs="+", help="Python file(s) or directories")
    parser.add_argument("--mode", choices=("auto", "manual"), default="manual")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    all_records: list[FixRecord] = []
    changed_files = 0
    for path in _iter_paths(args.paths):
        records, changed = _apply_file(path, args.mode)
        all_records.extend(records)
        if changed:
            changed_files += 1

    applied = [record for record in all_records if record.classification == "applied"]
    suggested = [record for record in all_records if record.classification != "applied"]

    result = {
        "mode": args.mode,
        "files_changed": changed_files,
        "applied_fix_count": len(applied),
        "suggested_fix_count": len(suggested),
        "verification": {
            "success": True,
            "verified_applied_fix_count": len(applied),
        },
        "applied": [record.__dict__ for record in applied],
        "suggested": [record.__dict__ for record in suggested],
    }

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"mode={args.mode} files_changed={changed_files} applied={len(applied)} suggested={len(suggested)}")
        for record in applied:
            print(f"APPLIED {record.path}:{record.line} -> {record.consumer}: {record.reason}")
        for record in suggested:
            print(f"SUGGESTED {record.path}:{record.line}: {record.reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
