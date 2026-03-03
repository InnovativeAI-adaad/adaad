# SPDX-License-Identifier: Apache-2.0
"""ZIP intake helpers for staging repository inputs."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile


def _is_safe_member(member_name: str) -> bool:
    member_path = Path(member_name)
    if member_path.is_absolute():
        return False
    return ".." not in member_path.parts


def extract_zip_archive(zip_path: Path, destination: Path) -> list[Path]:
    extracted: list[Path] = []
    destination.mkdir(parents=True, exist_ok=True)

    with ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir() or not _is_safe_member(member.filename):
                continue
            archive.extract(member, path=destination)
            extracted.append(destination / member.filename)

    return extracted
