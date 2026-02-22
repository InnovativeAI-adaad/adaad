from runtime.sandbox.syscall_filter import enforce_syscall_allowlist_with_fingerprint


def test_syscall_allowlist_violation_detected():
    ok, denied, fp = enforce_syscall_allowlist_with_fingerprint(("openat", "execve"), ("openat", "read"))
    assert ok is False
    assert "execve" in denied
    assert fp
