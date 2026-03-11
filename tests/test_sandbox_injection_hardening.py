# SPDX-License-Identifier: Apache-2.0
"""Tests: C-02 sandbox command-injection hardening (phase0/complete-all-advances)."""
from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard
from runtime.sandbox.preflight import _validate_command_token, analyze_execution_plan
from runtime.sandbox.manifest import SandboxManifest
from runtime.sandbox.policy import SandboxPolicy


def _policy():
    return SandboxPolicy(
        profile_id="test",
        syscall_allowlist=(),
        write_path_allowlist=("/tmp/sandbox",),
        network_egress_allowlist=(),
        dns_resolution_allowed=False,
        capability_drop=(),
        cpu_seconds=30,
        memory_mb=512,
        disk_mb=100,
        timeout_s=60,
    )


def _manifest(command, env=()):
    return SandboxManifest(
        mutation_id="test-mutation",
        epoch_id="test-epoch",
        replay_seed="test-seed",
        command=tuple(str(t) for t in command),
        env=tuple((str(k), str(v)) for k, v in env),
        mounts=(),
        allowed_write_paths=("/tmp/sandbox",),
        allowed_network_hosts=(),
        cpu_seconds=30,
        memory_mb=512,
        disk_mb=100,
        timeout_s=60,
        deterministic_clock=True,
        deterministic_random=True,
    )


# --- Token-level unit tests (fast, no SandboxManifest needed) ---

@pytest.mark.parametrize("fragment", [
    "echo&&id", "foo||bar", "cmd;id", "foo|bar", "echo`id`",
    "foo$(id)", "foo${bar}", "cmd>file", "cmd<file", "cmd<<EOF",
    "echo$IFSid", "echo${IFS}id",
    "eval malicious", "exec malicious", "source evil.sh",
    "%00inject",
])
def test_disallowed_fragment_detected(fragment):
    violations = _validate_command_token(fragment)
    assert violations, f"Expected violation for: {fragment!r}"


def test_clean_token_passes():
    assert _validate_command_token("python") == ()
    assert _validate_command_token("run.py") == ()
    assert _validate_command_token("--verbose") == ()


def test_oversized_token_detected():
    violations = _validate_command_token("A" * 600)
    assert any("oversized" in v for v in violations)


# --- Integration tests through analyze_execution_plan ---

def test_clean_command_accepted():
    result = analyze_execution_plan(
        manifest=_manifest(["python", "run.py"]),
        policy=_policy(),
    )
    assert result["ok"] is True


def test_shell_metacharacter_blocked_integration():
    result = analyze_execution_plan(
        manifest=_manifest(["sh", "echo&&id"]),
        policy=_policy(),
    )
    assert not result["ok"]
    assert any("disallowed_command_token" in v for v in result["violations"])


def test_disallowed_env_keys_blocked():
    for key in ("LD_PRELOAD", "PYTHONINSPECT", "LD_LIBRARY_PATH"):
        result = analyze_execution_plan(
            manifest=_manifest(["python", "run.py"], env=[(key, "evil")]),
            policy=_policy(),
        )
        assert not result["ok"], f"Expected {key} to be blocked"
        assert any("disallowed_env" in v for v in result["violations"])
