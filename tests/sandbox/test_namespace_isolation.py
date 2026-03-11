import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0
from runtime.sandbox import namespace as namespace_mod


def test_namespace_isolation_available_non_linux(monkeypatch):
    monkeypatch.setattr(namespace_mod.sys, "platform", "darwin")
    assert namespace_mod.namespace_isolation_available() is False

    with namespace_mod.enter_user_namespace() as details:
        assert details["entered"] is False
        assert details["reason"] == "non_linux"


def test_namespace_isolation_linux_path_callable(monkeypatch):
    monkeypatch.setattr(namespace_mod.sys, "platform", "linux")
    monkeypatch.setattr(namespace_mod.shutil, "which", lambda _: "/usr/bin/unshare")

    class _Result:
        returncode = 0

    monkeypatch.setattr(namespace_mod.subprocess, "run", lambda *args, **kwargs: _Result())

    with namespace_mod.enter_user_namespace() as details:
        assert details["entered"] is True
        assert details["reason"] == "unshare_probe_ok"
