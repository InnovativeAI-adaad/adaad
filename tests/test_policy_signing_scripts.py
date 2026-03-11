# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
import os
import subprocess
from pathlib import Path


SIGN_SCRIPT = Path("scripts/sign_policy_artifact.sh")
VERIFY_SCRIPT = Path("scripts/verify_policy_artifact.sh")
SIGN_ARTIFACT_SCRIPT = Path("scripts/sign_artifact.sh")


def test_sign_and_verify_policy_scripts_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "policy.json"
    signed = tmp_path / "policy.signed.json"
    source.write_text(Path("governance/governance_policy_v1.json").read_text(encoding="utf-8"), encoding="utf-8")

    env = dict(os.environ)
    env["ADAAD_POLICY_ARTIFACT_SIGNING_KEY"] = "script-test-signing-key"
    env["ADAAD_POLICY_SIGNER_KEY_ID"] = "script-signer"

    sign = subprocess.run(
        [str(SIGN_SCRIPT), str(source), str(signed)],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    assert str(signed) in sign.stdout

    artifact = json.loads(signed.read_text(encoding="utf-8"))
    assert artifact["signer"]["key_id"] == "script-signer"
    assert artifact["signer"]["algorithm"] == "hmac-sha256"
    assert artifact["signature"].startswith("sha256:")

    verify = subprocess.run(
        [str(VERIFY_SCRIPT), str(signed)],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    assert verify.stdout.strip().startswith("sha256:")


def test_sign_artifact_uses_rotation_metadata_for_deterministic_key_selection(tmp_path: Path) -> None:
    source = tmp_path / "policy.json"
    signed = tmp_path / "policy.signed.json"
    rotation = tmp_path / "rotation.json"
    source.write_text(Path("governance/governance_policy_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    rotation.write_text(
        json.dumps(
            {
                "active_key_id": "policy-signer-b",
                "trusted_key_ids": ["policy-signer-b", "policy-signer-a"],
                "overlap_key_ids": ["policy-signer-a"],
                "overlap_until_epoch": 10,
            }
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["ADAAD_POLICY_ARTIFACT_SIGNING_KEY"] = "script-test-signing-key"
    env["ADAAD_ARTIFACT_SIGNER_KEY_ID"] = ""
    env["ADAAD_ARTIFACT_ROTATION_METADATA"] = str(rotation)

    subprocess.run(
        [str(SIGN_ARTIFACT_SCRIPT), "policy_artifact", str(source), str(signed)],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    artifact = json.loads(signed.read_text(encoding="utf-8"))
    assert artifact["signer"]["key_id"] == "policy-signer-b"
    assert artifact["signer"]["trusted_key_ids"] == ["policy-signer-a", "policy-signer-b"]


def test_verify_script_rejects_tampered_signed_policy(tmp_path: Path) -> None:
    source = tmp_path / "policy.json"
    signed = tmp_path / "policy.signed.json"
    source.write_text(Path("governance/governance_policy_v1.json").read_text(encoding="utf-8"), encoding="utf-8")

    env = dict(os.environ)
    env["ADAAD_POLICY_ARTIFACT_SIGNING_KEY"] = "script-test-signing-key"
    env["ADAAD_POLICY_SIGNER_KEY_ID"] = "script-signer"
    subprocess.run([str(SIGN_SCRIPT), str(source), str(signed)], env=env, check=True, text=True, capture_output=True)

    artifact = json.loads(signed.read_text(encoding="utf-8"))
    artifact["payload"]["determinism_window"] = 999
    signed.write_text(json.dumps(artifact), encoding="utf-8")

    verify = subprocess.run([str(VERIFY_SCRIPT), str(signed)], env=env, text=True, capture_output=True)
    assert verify.returncode != 0
