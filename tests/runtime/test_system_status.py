# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from runtime.system_status import load_live_version, read_gate_state


def test_read_gate_state_respects_env_flag_lock_behavior(tmp_path: Path) -> None:
    unlocked = read_gate_state(
        gate_lock_file=tmp_path / "missing.lock",
        environ={"ADAAD_GATE_LOCKED": "false", "ADAAD_GATE_REASON": "maintenance"},
    )
    assert unlocked["locked"] is False
    assert unlocked["source"] == "env"
    assert unlocked["reason"] == "maintenance"

    locked = read_gate_state(
        gate_lock_file=tmp_path / "missing.lock",
        environ={"ADAAD_GATE_LOCKED": "1", "ADAAD_GATE_REASON": "maintenance"},
    )
    assert locked["locked"] is True
    assert locked["source"] == "env"
    assert locked["reason"] == "maintenance"


def test_read_gate_state_prefers_lockfile_reason_over_env_reason(tmp_path: Path) -> None:
    lockfile = tmp_path / "gate.lock"
    lockfile.write_text("locked-by-file", encoding="utf-8")

    result = read_gate_state(
        gate_lock_file=lockfile,
        environ={"ADAAD_GATE_LOCKED": "1", "ADAAD_GATE_REASON": "locked-by-env"},
    )

    assert result["locked"] is True
    assert result["source"] == "file"
    assert result["reason"] == "locked-by-file"


def test_load_live_version_degrades_when_version_and_report_are_missing(tmp_path: Path) -> None:
    result = load_live_version(
        version_path=tmp_path / "VERSION",
        report_version_path=tmp_path / "report_version.json",
        constitution_version_provider=lambda: "constitution-test",
    )
    assert result["adaad_version"] == "unknown"
    assert result["last_sync_sha"] == "unknown"
    assert result["last_sync_date"] == "unknown"
    assert result["report_version"] == "unknown"
    assert result["constitution_version"] == "constitution-test"


def test_load_live_version_degrades_when_report_file_invalid_json(tmp_path: Path) -> None:
    version_path = tmp_path / "VERSION"
    version_path.write_text("9.0.0", encoding="utf-8")
    report_path = tmp_path / "report_version.json"
    report_path.write_text("{invalid", encoding="utf-8")

    result = load_live_version(
        version_path=version_path,
        report_version_path=report_path,
        constitution_version_provider=lambda: "constitution-test",
    )
    assert result["adaad_version"] == "9.0.0"
    assert result["last_sync_sha"] == "unknown"
    assert result["last_sync_date"] == "unknown"
    assert result["report_version"] == "9.0.0"
