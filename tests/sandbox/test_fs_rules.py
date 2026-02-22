from runtime.sandbox.fs_rules import enforce_write_path_allowlist


def test_write_rules_block_outside_workspace():
    ok, violations = enforce_write_path_allowlist(("/etc/passwd",), ("/workspace",))
    assert ok is False
    assert violations
