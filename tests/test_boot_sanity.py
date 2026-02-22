# SPDX-License-Identifier: Apache-2.0

from runtime.constitution import boot_sanity_check


def test_boot_sanity_check_returns_ok() -> None:
    assert boot_sanity_check() == {"ok": True}
