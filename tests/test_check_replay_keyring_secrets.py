# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
from pathlib import Path


SCRIPT = Path("scripts/check_replay_keyring_secrets.py")


def test_secret_guard_passes_for_repo_baseline() -> None:
    result = subprocess.run(["python", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "replay_keyring_secret_guard:ok" in result.stdout


def test_secret_guard_detects_forbidden_fields(tmp_path: Path) -> None:
    keyring_path = tmp_path / "replay_proof_keyring.json"
    keyring_path.write_text(
        json.dumps({"keys": {"proof-key": {"algorithm": "hmac-sha256", "hmac_secret": "raw-secret"}}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python", str(SCRIPT), "--path", str(keyring_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "forbidden_secret_field" in result.stdout
