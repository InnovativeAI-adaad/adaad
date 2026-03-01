# SPDX-License-Identifier: MIT
"""
Fail-fast license guardrail.

Checks:
- No CC-license references in repository-authored files.
- No HTTP Apache license URLs.
- Root licensing artifacts align with MIT baseline.
- Python files that declare SPDX use an approved identifier.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APACHE_HTTP = "http" + "://www.apache.org/licenses"
CC_TOKEN = "Creative" + " Commons"
CC0_TOKEN = "CC" + "0"
VALID_SPDX_TAGS = {
    "# SPDX-License-Identifier: MIT",
    "# SPDX-License-Identifier: Apache-2.0",
}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".pdf", ".mp4", ".mov", ".sqlite", ".db"}


def tracked_files(root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    files: list[Path] = []
    for line in completed.stdout.splitlines():
        path = root / line.strip()
        if path.is_file():
            files.append(path)
    return files


def _check_mit_baseline(failures: list[str]) -> None:
    license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8", errors="ignore")
    if "MIT License" not in license_text:
        failures.append("Root LICENSE does not contain MIT License header")

    licenses_md = (REPO_ROOT / "LICENSES.md").read_text(encoding="utf-8", errors="ignore")
    if "MIT" not in licenses_md:
        failures.append("LICENSES.md does not reference MIT baseline")

    notice_text = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8", errors="ignore")
    if "MIT License" not in notice_text:
        failures.append("NOTICE does not reference MIT License")


def main() -> int:
    failures: list[str] = []

    _check_mit_baseline(failures)

    for path in tracked_files(REPO_ROOT):
        if path.name == "check_licenses.py":
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if CC_TOKEN in text or CC0_TOKEN in text:
            failures.append(f"CC-license reference found in {path.relative_to(REPO_ROOT)}")
        if APACHE_HTTP in text:
            failures.append(f"HTTP Apache URL found in {path.relative_to(REPO_ROOT)}")

        if path.suffix == ".py":
            head = text.splitlines()[:25]
            spdx_lines = [line for line in head if "SPDX-License-Identifier:" in line]
            if spdx_lines and not any(any(tag in line for tag in VALID_SPDX_TAGS) for line in spdx_lines):
                failures.append(f"Invalid SPDX tag in {path.relative_to(REPO_ROOT)}")

    if failures:
        for line in failures:
            print(line)
        return 1
    print("License checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
