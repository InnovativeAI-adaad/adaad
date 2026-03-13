# SPDX-License-Identifier: Apache-2.0
"""Importability checks for the AST substrate package."""

from __future__ import annotations

import importlib


def test_runtime_mutation_ast_substrate_package_is_importable() -> None:
    module = importlib.import_module("runtime.mutation.ast_substrate")
    assert module is not None
