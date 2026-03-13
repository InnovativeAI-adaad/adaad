# SPDX-License-Identifier: Apache-2.0
"""
Module: test_phase67_improvements
Purpose: Validate Phase 3 (67) improvements:
  - M-01: lint_import_paths inline suppression + --fix mode
  - M-06: enforce_redteam_retention size-cap sentinel
  - Error budget tracker rolling-window fail-closed counter
Author: ADAAD / InnovativeAI-adaad
Integration points:
  - Imports from: tools.lint_import_paths, scripts.enforce_redteam_retention,
                  runtime.governance.error_budget
  - Consumed by: pytest
  - Governance impact: low — test-only; no mutation authority
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# M-01: lint_import_paths inline suppression
# ---------------------------------------------------------------------------

class TestInlineSuppression:
    """Verify _is_suppressed() honours valid inline suppression tokens."""

    def _write_py(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "subject.py"
        p.write_text(content, encoding="utf-8")
        return p

    def test_valid_suppression_token_accepted(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from lint_import_paths import _is_suppressed
        f = self._write_py(tmp_path, "import governance  # adaad: import-boundary-ok:test-only adapter\n")
        suppressed, reason = _is_suppressed(f, 1)
        assert suppressed
        assert "test-only adapter" in reason

    def test_missing_reason_not_suppressed(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from lint_import_paths import _is_suppressed
        f = self._write_py(tmp_path, "import governance  # adaad: import-boundary-ok:\n")
        suppressed, _ = _is_suppressed(f, 1)
        assert not suppressed

    def test_no_token_not_suppressed(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from lint_import_paths import _is_suppressed
        f = self._write_py(tmp_path, "import governance\n")
        suppressed, _ = _is_suppressed(f, 1)
        assert not suppressed

    def test_wrong_line_not_suppressed(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from lint_import_paths import _is_suppressed
        f = self._write_py(tmp_path, "# adaad: import-boundary-ok:reason\nimport governance\n")
        # Token is on line 1, violation is on line 2
        suppressed, _ = _is_suppressed(f, 2)
        assert not suppressed

    def test_fix_mode_annotates_violation_lines(self, tmp_path: Path) -> None:
        """--fix mode should append suppression stub to flagged lines."""
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import lint_import_paths as lip
        # Create a file with a known violation (archive import)
        subject = tmp_path / "fixme.py"
        subject.write_text("from archives import something\n", encoding="utf-8")
        # Patch REPO_ROOT so relative paths resolve correctly
        with patch.object(lip, "REPO_ROOT", tmp_path):
            result = lip.main(["--fix", str(subject)])
        assert result == 1  # still fails — reason is a stub placeholder
        updated = subject.read_text(encoding="utf-8")
        assert "import-boundary-ok" in updated
        assert "<reason-required>" in updated

    def test_json_output_includes_suppressed_count(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import lint_import_paths as lip
        subject = tmp_path / "clean.py"
        subject.write_text("x = 1  # adaad: import-boundary-ok:no import here\n", encoding="utf-8")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with patch.object(lip, "REPO_ROOT", tmp_path):
                lip.main(["--format=json", str(subject)])
        import json
        data = json.loads(buf.getvalue())
        assert "suppressed_count" in data


# ---------------------------------------------------------------------------
# M-06: enforce_redteam_retention
# ---------------------------------------------------------------------------

class TestRedteamRetention:
    """Verify size-cap sentinel and rotation logic."""

    def _script_path(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "enforce_redteam_retention.py"

    def _import_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("enforce_redteam_retention", self._script_path())
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    def test_dry_run_does_not_delete_files(self, tmp_path: Path) -> None:
        mod = self._import_module()
        redteam = tmp_path / "reports" / "redteam"
        redteam.mkdir(parents=True)
        old_file = redteam / "old.json"
        old_file.write_text("{}", encoding="utf-8")
        # Set mtime to 200 days ago
        old_ts = time.time() - 200 * 86400
        os.utime(old_file, (old_ts, old_ts))

        with patch.object(mod, "REDTEAM_DIR", redteam), \
             patch.object(mod, "SENTINEL_PATH", redteam / ".sentinel.json"), \
             patch.dict(os.environ, {"ADAAD_REDTEAM_EVIDENCE_RETENTION_DAYS": "90"}):
            result = mod.main(["--dry-run"])

        assert old_file.exists()  # not deleted in dry-run

    def test_rotation_deletes_old_files(self, tmp_path: Path) -> None:
        mod = self._import_module()
        redteam = tmp_path / "reports" / "redteam"
        redteam.mkdir(parents=True)
        old_file = redteam / "stale.json"
        old_file.write_text("{}", encoding="utf-8")
        old_ts = time.time() - 200 * 86400
        os.utime(old_file, (old_ts, old_ts))

        with patch.object(mod, "REDTEAM_DIR", redteam), \
             patch.object(mod, "SENTINEL_PATH", redteam / ".sentinel.json"), \
             patch.dict(os.environ, {"ADAAD_REDTEAM_EVIDENCE_RETENTION_DAYS": "90"}):
            result = mod.main([])

        assert not old_file.exists()

    def test_size_cap_exceeded_returns_nonzero(self, tmp_path: Path) -> None:
        mod = self._import_module()
        redteam = tmp_path / "reports" / "redteam"
        redteam.mkdir(parents=True)
        # Write a 2-byte file but set cap to 1 byte
        (redteam / "big.json").write_text("{}", encoding="utf-8")

        with patch.object(mod, "REDTEAM_DIR", redteam), \
             patch.object(mod, "SENTINEL_PATH", redteam / ".sentinel.json"), \
             patch.dict(os.environ, {"ADAAD_REDTEAM_EVIDENCE_SIZE_CAP_MB": "0.000001"}):
            result = mod.main(["--check-only"])

        assert result == 1

    def test_within_cap_returns_zero(self, tmp_path: Path) -> None:
        mod = self._import_module()
        redteam = tmp_path / "reports" / "redteam"
        redteam.mkdir(parents=True)

        with patch.object(mod, "REDTEAM_DIR", redteam), \
             patch.object(mod, "SENTINEL_PATH", redteam / ".sentinel.json"), \
             patch.dict(os.environ, {"ADAAD_REDTEAM_EVIDENCE_SIZE_CAP_MB": "500"}):
            result = mod.main(["--check-only"])

        assert result == 0


# ---------------------------------------------------------------------------
# Error budget tracker
# ---------------------------------------------------------------------------

class TestErrorBudgetTracker:
    """Verify rolling-window fail-closed event counting."""

    def _fresh(self):
        from runtime.governance.error_budget import ErrorBudgetTracker
        return ErrorBudgetTracker()

    def test_records_events_within_window(self) -> None:
        t = self._fresh()
        t.record_fail_closed("replay_divergence")
        t.record_fail_closed("governance_gate_reject")
        assert t.count_in_window() == 2

    def test_budget_not_exceeded_below_threshold(self) -> None:
        with patch.dict(os.environ, {"ADAAD_ERROR_BUDGET_THRESHOLD": "5"}):
            t = self._fresh()
            for _ in range(4):
                t.record_fail_closed("test_event")
            assert not t.is_budget_exceeded()

    def test_budget_exceeded_at_threshold(self) -> None:
        with patch.dict(os.environ, {"ADAAD_ERROR_BUDGET_THRESHOLD": "3"}):
            t = self._fresh()
            for _ in range(3):
                t.record_fail_closed("test_event")
            assert t.is_budget_exceeded()

    def test_reset_clears_all_events(self) -> None:
        t = self._fresh()
        t.record_fail_closed("event_a")
        t.record_fail_closed("event_b")
        t.reset()
        assert t.count_in_window() == 0

    def test_snapshot_includes_reason_breakdown(self) -> None:
        t = self._fresh()
        t.record_fail_closed("reason_a")
        t.record_fail_closed("reason_a")
        t.record_fail_closed("reason_b")
        snap = t.snapshot()
        assert snap["reason_breakdown"]["reason_a"] == 2
        assert snap["reason_breakdown"]["reason_b"] == 1
        assert snap["count_in_window"] == 3

    def test_singleton_returns_same_instance(self) -> None:
        from runtime.governance.error_budget import get_error_budget_tracker
        a = get_error_budget_tracker()
        b = get_error_budget_tracker()
        assert a is b

    def test_snapshot_budget_exceeded_field(self) -> None:
        with patch.dict(os.environ, {"ADAAD_ERROR_BUDGET_THRESHOLD": "2"}):
            t = self._fresh()
            t.record_fail_closed("x")
            t.record_fail_closed("x")
            snap = t.snapshot()
            assert snap["budget_exceeded"] is True
