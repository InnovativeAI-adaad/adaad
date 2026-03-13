# SPDX-License-Identifier: Apache-2.0
"""
Sandbox test fixtures.

Phase 49 made ContainerIsolationBackend the default when ADAAD_FORCE_TIER=SANDBOX
and container rollout is enabled.  The test environment has no Docker runtime and
no container profile env-vars, so tests that expect ProcessIsolationBackend would
fail with sandbox_policy_unenforceable:container_runtime.

Fix: disable container rollout for the entire test module via an autouse session
fixture.  Per-test overrides via monkeypatch.setenv still take effect because
monkeypatch runs *after* this fixture restores the env var.
"""
import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def _disable_container_rollout_in_tests():
    """Force ProcessIsolationBackend for sandbox tests unless a test explicitly
    overrides ADAAD_SANDBOX_CONTAINER_ROLLOUT via monkeypatch."""
    prev = os.environ.get("ADAAD_SANDBOX_CONTAINER_ROLLOUT")
    os.environ["ADAAD_SANDBOX_CONTAINER_ROLLOUT"] = "off"
    yield
    if prev is None:
        os.environ.pop("ADAAD_SANDBOX_CONTAINER_ROLLOUT", None)
    else:
        os.environ["ADAAD_SANDBOX_CONTAINER_ROLLOUT"] = prev
