# SPDX-License-Identifier: Apache-2.0
"""Shared pytest fixtures for ADAAD governance endpoint tests.

Provides reusable fixtures and helpers so per-endpoint test modules do
not duplicate auth/client setup boilerplate.

Usage
-----
Any test module that needs a FastAPI TestClient with ``audit:read`` scope:

    from tests.conftest import make_audit_client, AUTH_HEADERS

Or simply let pytest collect fixtures automatically (autouse fixtures are
defined per-module, not here, to preserve token isolation).

Test ID convention: T<NN>-EP-<seq>
"""

from __future__ import annotations

import json
from typing import Generator

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Token / scope constants
# ---------------------------------------------------------------------------

AUDIT_SCOPE = "audit:read"
OTHER_SCOPE = "other:scope"
BAD_SCOPE_TOKEN = "conftest-bad-scope-token"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def auth_headers(token: str) -> dict[str, str]:
    """Return Authorization header dict for the given token."""
    return {"Authorization": f"Bearer {token}"}


def audit_env(token: str, scope: str = AUDIT_SCOPE) -> str:
    """Return JSON string for ADAAD_AUDIT_TOKENS env var."""
    return json.dumps({token: [scope]})


def make_audit_client(token: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a TestClient with audit:read scope wired for *token*."""
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", audit_env(token))
    from server import app
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Session-scoped app import (avoids repeated module reloads in large runs)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _app():
    from server import app
    return app


# ---------------------------------------------------------------------------
# Shared assertion helpers (importable)
# ---------------------------------------------------------------------------

def assert_schema_version(resp_json: dict, expected: str = "1.0") -> None:
    assert resp_json.get("schema_version") == expected, (
        f"Expected schema_version={expected!r}, got {resp_json.get('schema_version')!r}"
    )


def assert_required_keys(data: dict, required: frozenset[str]) -> None:
    missing = required - data.keys()
    assert not missing, f"Missing data keys: {missing}"


def assert_rate_complement(rate_a: float, rate_b: float, tol: float = 1e-5) -> None:
    """Assert two rates sum to 1.0 within tolerance."""
    total = rate_a + rate_b
    assert abs(total - 1.0) < tol, f"Complement invariant violated: {rate_a} + {rate_b} = {total}"


def assert_nonneg_int(value: object, name: str) -> None:
    assert isinstance(value, int) and value >= 0, f"{name} must be a non-negative int, got {value!r}"


def assert_sha256_prefix(value: object, name: str = "hash") -> None:
    assert isinstance(value, str) and value.startswith("sha256:"), (
        f"{name} must be a sha256:-prefixed string, got {value!r}"
    )
