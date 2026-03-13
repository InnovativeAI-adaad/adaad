# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.evolution import replay_attestation


def _write_keyring(path: Path, secret_value: str) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "1",
                "keys": {
                    "proof-key": {
                        "algorithm": "hmac-sha256",
                        "hmac_secret": secret_value,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_load_replay_keyring_prefers_env_over_secret_mount_and_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "replay_proof_keyring.json"
    local = tmp_path / "replay_proof_keyring.local.json"
    secret_mount = tmp_path / "mount.json"
    _write_keyring(base, "base-secret")
    _write_keyring(local, "local-secret")
    _write_keyring(secret_mount, "mounted-secret")

    monkeypatch.setenv("ADAAD_ENV", "staging")
    monkeypatch.setenv("ADAAD_REPLAY_PROOF_KEYRING_PATH", str(base))
    monkeypatch.setenv("ADAAD_REPLAY_PROOF_KEYRING_LOCAL_PATH", str(local))
    monkeypatch.setenv("ADAAD_REPLAY_PROOF_KEYRING_SECRET_PATH", str(secret_mount))
    monkeypatch.setenv("ADAAD_REPLAY_PROOF_HMAC_SECRET_PROOF_KEY", "env-secret")

    loaded = replay_attestation._load_replay_proof_keyring()
    assert loaded["proof-key"]["hmac_secret"] == "env-secret"


def test_load_replay_keyring_rejects_placeholder_secrets_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "production")
    monkeypatch.setenv("ADAAD_REPLAY_PROOF_HMAC_SECRET_PROOF_KEY", "placeholder-secret")

    with pytest.raises(RuntimeError, match="replay_proof_keyring_placeholder_secret"):
        replay_attestation._load_replay_proof_keyring()

