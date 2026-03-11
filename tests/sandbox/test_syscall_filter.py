import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0
from runtime.sandbox.syscall_filter import enforce_syscall_allowlist_with_fingerprint


def test_syscall_allowlist_violation_detected():
    ok, denied, fp = enforce_syscall_allowlist_with_fingerprint(("openat", "execve"), ("openat", "read"))
    assert ok is False
    assert denied == ("execve",)
    assert fp.startswith("sha256:")


def test_syscall_fingerprint_is_stable_for_ordering_equivalence():
    allowlist = ("read", "openat", "write")
    first = enforce_syscall_allowlist_with_fingerprint(("openat", "execve", "socket", "execve"), allowlist)
    second = enforce_syscall_allowlist_with_fingerprint(("socket", "openat", "execve"), tuple(reversed(allowlist)))

    assert first[0] is False
    assert first[1] == ("execve", "socket")
    assert second[1] == first[1]
    assert first[2] == second[2]
