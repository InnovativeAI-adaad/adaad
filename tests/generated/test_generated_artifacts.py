# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import os
from pathlib import Path

from tests.generated.parsers import canonical_sha256, read_json


FIXTURE = os.environ.get("GENERATED_FIXTURE", "solo_agent_loop")
EVIDENCE_DIR = Path(os.environ.get("GENERATED_EVIDENCE_DIR", f"tests/generated/evidence/{FIXTURE}"))


def test_expected_files_exist() -> None:
    assert (EVIDENCE_DIR / "run.log").is_file()
    assert (EVIDENCE_DIR / "agents" / "solo_agent" / "meta.json").is_file()
    assert (EVIDENCE_DIR / "agents" / "solo_agent" / "certificate.json").is_file()


def test_single_agent_metadata_is_deterministic_shape() -> None:
    meta = read_json(EVIDENCE_DIR / "agents" / "solo_agent" / "meta.json")
    assert meta["id"] == "solo_agent"
    assert meta["resource_envelope"]["profile"] == "sandbox"
    assert "network" in meta["dream_scope"]["deny"]


def test_certificate_hash_has_sha256_prefix() -> None:
    cert = read_json(EVIDENCE_DIR / "agents" / "solo_agent" / "certificate.json")
    lineage_hash = str(cert.get("lineage_hash", ""))
    assert len(lineage_hash) == 64
    assert all(ch in "0123456789abcdef" for ch in lineage_hash)


def test_run_log_has_stable_hash() -> None:
    digest = canonical_sha256(EVIDENCE_DIR / "run.log")
    assert len(digest) == 64
