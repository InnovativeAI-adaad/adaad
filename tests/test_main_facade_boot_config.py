# SPDX-License-Identifier: Apache-2.0
import pytest

from app.orchestration.boot_config import (
    build_init_state,
    dry_run_env_enabled,
    resolve_replay_mode,
    select_epoch,
)
from runtime.api.runtime_services import ReplayMode

pytestmark = pytest.mark.regression_standard


class _Args:
    verbose = True
    dry_run = False
    exit_after_boot = True
    verify_replay = False


def test_dry_run_env_enabled_contract() -> None:
    assert dry_run_env_enabled({"ADAAD_DRY_RUN": "true"}) is True
    assert dry_run_env_enabled({"ADAAD_DRY_RUN": "0"}) is False


def test_select_epoch_prefers_epoch_then_replay_epoch() -> None:
    assert select_epoch("epoch-a", "epoch-b") == "epoch-a"
    assert select_epoch("", " epoch-b ") == "epoch-b"


def test_build_init_state_reduces_implicit_cli_coupling() -> None:
    state = build_init_state(args=_Args(), dry_run_env=True, replay_mode=ReplayMode.AUDIT, selected_epoch="epoch-7")
    assert state.verbose is True
    assert state.dry_run is True
    assert state.replay_mode is ReplayMode.AUDIT
    assert state.replay_epoch == "epoch-7"
    assert state.exit_after_boot is True


def test_resolve_replay_mode_supports_aliases() -> None:
    assert resolve_replay_mode("full") is ReplayMode.AUDIT
