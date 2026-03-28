# SPDX-License-Identifier: Apache-2.0
"""Guardrail: tests must not use insecure temporary path creation APIs."""

from __future__ import annotations

from pathlib import Path


def test_tests_do_not_use_tempfile_mktemp() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    forbidden = "tempfile." + "mktemp("
    offenders: list[str] = []
    for path in sorted((repo_root / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if forbidden in text:
            offenders.append(str(path.relative_to(repo_root)))

    assert offenders == [], f"Use tempfile.NamedTemporaryFile/TemporaryDirectory/tmp_path instead: {offenders}"
