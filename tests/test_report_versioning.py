# SPDX-License-Identifier: Apache-2.0

from runtime import report_version


def test_build_snapshot_metadata_includes_branch_tag_and_short_sha(monkeypatch):
    monkeypatch.setattr(report_version, "load_report_version", lambda: "9.9.9")
    monkeypatch.setattr(
        report_version,
        "current_git_metadata",
        lambda: {"branch": "feature/test", "tag": "v9.9.9", "short_sha": "abc1234"},
    )

    metadata = report_version.build_snapshot_metadata()

    assert metadata == {
        "report_version": "9.9.9",
        "branch": "feature/test",
        "tag": "v9.9.9",
        "short_sha": "abc1234",
    }


def test_build_snapshot_metadata_normalizes_missing_tag(monkeypatch):
    monkeypatch.setattr(report_version, "load_report_version", lambda: "1.0.0")
    monkeypatch.setattr(
        report_version,
        "current_git_metadata",
        lambda: {"branch": "main", "tag": "", "short_sha": "deadbee"},
    )

    metadata = report_version.build_snapshot_metadata()

    assert metadata["tag"] == "(none)"
