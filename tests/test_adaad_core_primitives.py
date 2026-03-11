# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from adaad.core.cryovant import deterministic_source_hash


def test_deterministic_source_hash_smoke() -> None:
    digest = deterministic_source_hash("runtime.manifest.generator")
    assert len(digest) == 64
