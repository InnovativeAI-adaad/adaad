# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import importlib.util
import pathlib


SCRIPT_PATH = pathlib.Path("scripts/check_dependency_baseline.py")


def _load_guard_module():
    spec = importlib.util.spec_from_file_location("check_dependency_baseline", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_requirements_flags_non_pinned_tracked_packages(tmp_path):
    guard = _load_guard_module()
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text(
        "# comment\nfastapi>=0.1\nuvicorn==0.30.6\nanthropic==0.40.0\n",
        encoding="utf-8",
    )

    pins, violations = guard._parse_requirements(requirements_file)

    assert pins["uvicorn"] == "0.30.6"
    assert pins["anthropic"] == "0.40.0"
    assert violations["fastapi"] == "fastapi>=0.1"


def test_main_fails_when_required_pin_missing(tmp_path, monkeypatch):
    guard = _load_guard_module()
    runtime = tmp_path / "requirements.server.txt"
    archive = tmp_path / "archives/backend/requirements.txt"
    archive.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text("fastapi==1\nuvicorn==2\nanthropic==3\n", encoding="utf-8")
    archive.write_text("fastapi==1\nuvicorn==2\n", encoding="utf-8")

    monkeypatch.setattr(guard, "RUNTIME_REQUIREMENTS", runtime)
    monkeypatch.setattr(guard, "ARCHIVE_REQUIREMENTS", archive)

    assert guard.main() == 1


def test_main_succeeds_on_matching_exact_pins(tmp_path, monkeypatch):
    guard = _load_guard_module()
    runtime = tmp_path / "requirements.server.txt"
    archive = tmp_path / "archives/backend/requirements.txt"
    archive.parent.mkdir(parents=True, exist_ok=True)
    content = "fastapi==0.115.5\nuvicorn==0.30.6\nanthropic==0.40.0\n"
    runtime.write_text(content, encoding="utf-8")
    archive.write_text(content, encoding="utf-8")

    monkeypatch.setattr(guard, "RUNTIME_REQUIREMENTS", runtime)
    monkeypatch.setattr(guard, "ARCHIVE_REQUIREMENTS", archive)

    assert guard.main() == 0
