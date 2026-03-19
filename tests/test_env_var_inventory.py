# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.generate_env_var_inventory import (
    INVENTORY_END,
    INVENTORY_START,
    _extract_default,
    _is_adaad_var,
    _render_table,
    _splice_into_doc,
    EnvRef,
    EnvVarEntry,
)


def test_is_adaad_var_prefixes_and_builtins() -> None:
    assert _is_adaad_var("ADAAD_ENV")
    assert _is_adaad_var("CRYOVANT_DEV_MODE")
    assert not _is_adaad_var("PATH")
    assert not _is_adaad_var("CUSTOM_VAR")


def test_extract_default_string_literal() -> None:
    assert _extract_default('os.getenv("ADAAD_ENV", "dev")', "ADAAD_ENV") == "dev"
    assert _extract_default('os.getenv("ADAAD_ENV")', "ADAAD_ENV") == ""


def test_render_table_sorted() -> None:
    a = EnvVarEntry("ADAAD_Z", [EnvRef("ADAAD_Z", "app/a.py", 2, "", "os.getenv")])
    b = EnvVarEntry("ADAAD_A", [EnvRef("ADAAD_A", "app/a.py", 1, "", "os.getenv")])
    table = _render_table({"ADAAD_Z": a, "ADAAD_A": b})
    assert table.index("ADAAD_A") < table.index("ADAAD_Z")


def test_splice_missing_sentinel_fails_closed(tmp_path: Path) -> None:
    doc = tmp_path / "ENVIRONMENT_VARIABLES.md"
    doc.write_text("# missing markers\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        _splice_into_doc(doc, "table\n")


def test_splice_between_markers(tmp_path: Path) -> None:
    doc = tmp_path / "ENVIRONMENT_VARIABLES.md"
    doc.write_text(f"before\n{INVENTORY_START}\nold\n{INVENTORY_END}\nafter\n", encoding="utf-8")
    new_content, changed = _splice_into_doc(doc, "new\n")
    assert changed
    assert "new" in new_content


def test_validator_delegates_to_generate_check() -> None:
    with patch("scripts.generate_env_var_inventory.main", return_value=0) as mocked:
        from scripts.validate_env_var_inventory import main

        assert main() == 0
        mocked.assert_called_once_with(["--check", "--format", "json"])
