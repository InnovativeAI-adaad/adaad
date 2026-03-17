# SPDX-License-Identifier: Apache-2.0
import pytest
from unittest import mock

from app.main import main

pytestmark = pytest.mark.regression_standard


def test_main_verify_replay_uses_facade_init_state() -> None:
    fake_orchestrator = mock.Mock()
    with mock.patch("app.main.build_orchestrator", return_value=fake_orchestrator) as build_orchestrator:
        with mock.patch("sys.argv", ["app.main", "--verify-replay"]):
            main()
    build_orchestrator.assert_called_once()
    fake_orchestrator.verify_replay_only.assert_called_once()
    fake_orchestrator.boot.assert_not_called()
