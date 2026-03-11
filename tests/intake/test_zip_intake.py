# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from pathlib import Path
from zipfile import ZipFile

from runtime.intake.zip_intake import extract_zip_archive


def test_extract_zip_archive_skips_unsafe_members(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("safe/file.txt", "ok")
        archive.writestr("../escape.txt", "no")

    destination = tmp_path / "out"
    extracted = extract_zip_archive(zip_path, destination)

    assert (destination / "safe/file.txt").exists()
    assert not (tmp_path / "escape.txt").exists()
    assert [path.relative_to(destination).as_posix() for path in extracted] == ["safe/file.txt"]
