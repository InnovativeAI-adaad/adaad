import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))


# Approved top-level namespaces for in-repo imports.
# To add a new namespace:
# 1) Create the top-level package/module at the repo root.
# 2) Add the new namespace to APPROVED_ROOTS below.
# 3) Ensure imports use the new root instead of legacy ones.
#
# Implementation note: validation uses ast.parse() + ast.walk() to extract
# Import and ImportFrom nodes. This eliminates the class of false positives
# caused by regex scanning (docstrings, comments, string literals that happen
# to start with "from " or "import ").
#
# Optional external dependencies that are guarded by try/except in source
# (e.g. `import jsonschema`) are listed in APPROVED_OPTIONAL_EXTERNALS.
# They are not required to be installed — only to be explicitly acknowledged.
APPROVED_ROOTS = {
    "adaad", "app", "core", "evolution", "governance", "memory",
    "nexus_setup", "runtime", "sandbox", "scripts", "security",
    "server", "tests", "tools", "ui", "warnings", "cryptography",
}
# Optional third-party packages used under try/except guards in source.
# These are acknowledged as intentional optional dependencies.
APPROVED_OPTIONAL_EXTERNALS = {
    "jsonschema",  # tools/interactive_onboarding.py, runtime/governance/simulation/profile_exporter.py
}
STDLIB_ROOTS = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)
SITE_PACKAGES_MARKERS = ("site-packages", "dist-packages")
EXCLUDED_DIRS = {".venv", "venv", "__pycache__", ".tox", ".mypy_cache", "build", "dist", "archives"}


def is_excluded_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _extract_import_roots(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (lineno, root_module, original_module_string) for every
    import statement in *path* using AST parsing.

    Relative imports (level > 0) are skipped — they are always intra-package
    and cannot reference a disallowed root.

    Imports nested inside Try nodes are also skipped: they are optional
    best-effort imports guarded by except clauses and are enumerated in
    APPROVED_OPTIONAL_EXTERNALS separately.

    SyntaxError / UnicodeDecodeError files are silently skipped; they are
    caught by separate linting gates and would cause false positives here.
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    # Collect line numbers of import nodes that live inside Try blocks
    try_import_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    try_import_lines.add(child.lineno)

    results: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if node.lineno in try_import_lines:
                continue
            for alias in node.names:
                root = alias.name.split(".")[0]
                results.append((node.lineno, root, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import
            if node.lineno in try_import_lines:
                continue
            module = node.module or ""
            if not module:
                continue
            root = module.split(".")[0]
            results.append((node.lineno, root, module))
    return results


class ImportRootTest(unittest.TestCase):
    def test_no_legacy_import_roots(self) -> None:
        failures: list[str] = []
        all_approved = APPROVED_ROOTS | APPROVED_OPTIONAL_EXTERNALS | STDLIB_ROOTS
        for path in ROOT.rglob("*.py"):
            if is_excluded_path(path):
                continue
            for lineno, root, full_module in _extract_import_roots(path):
                if root in all_approved:
                    continue
                spec = importlib.util.find_spec(root)
                if spec is not None:
                    origin = spec.origin or ""
                    if origin == "built-in":
                        continue
                    if any(marker in origin for marker in SITE_PACKAGES_MARKERS):
                        continue
                failures.append(f"{path}:{lineno}:import {full_module}")
        self.assertFalse(
            failures,
            "Disallowed import roots found:\n" + "\n".join(sorted(failures)),
        )


if __name__ == "__main__":
    unittest.main()
