# SPDX-License-Identifier: Apache-2.0

from runtime.sandbox.manifest import SandboxManifest
from runtime.sandbox.policy import default_sandbox_policy
from runtime.sandbox.preflight import analyze_execution_plan


def _manifest(*, command: tuple[str, ...]) -> SandboxManifest:
    policy = default_sandbox_policy()
    return SandboxManifest(
        mutation_id="m1",
        epoch_id="e1",
        replay_seed="0000000000000001",
        command=command,
        env=(("PYTHONDONTWRITEBYTECODE", "1"),),
        mounts=("reports",),
        allowed_write_paths=policy.write_path_allowlist,
        allowed_network_hosts=policy.network_egress_allowlist,
        cpu_seconds=policy.cpu_seconds,
        memory_mb=policy.memory_mb,
        disk_mb=policy.disk_mb,
        timeout_s=policy.timeout_s,
        deterministic_clock=True,
        deterministic_random=True,
    )


def test_disallowed_fragment_detection_truncates_payload_value():
    policy = default_sandbox_policy()
    token = "x" * 120 + "&&"
    manifest = _manifest(command=(token,))

    preflight = analyze_execution_plan(manifest=manifest, policy=policy)

    assert preflight["ok"] is False
    assert preflight["violations"] == (f"disallowed_command_token:{token[:80]}",)


def test_oversized_token_rejection_uses_token_length_payload():
    policy = default_sandbox_policy()
    token = "x" * 513
    manifest = _manifest(command=(token,))

    preflight = analyze_execution_plan(manifest=manifest, policy=policy)

    assert preflight["ok"] is False
    assert preflight["violations"] == ("oversized_command_token:513",)


def test_violation_ordering_is_deterministic_for_replay():
    policy = default_sandbox_policy()
    oversized_disallowed = "x" * 600 + "&&"
    manifest = _manifest(command=(oversized_disallowed, "ok", "bad|token"))

    preflight = analyze_execution_plan(manifest=manifest, policy=policy)

    assert preflight["violations"] == (
        f"disallowed_command_token:{oversized_disallowed[:80]}",
        f"oversized_command_token:{len(oversized_disallowed)}",
        "disallowed_command_token:bad|token",
    )
