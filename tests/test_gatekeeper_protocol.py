# SPDX-License-Identifier: Apache-2.0

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from security.gatekeeper_protocol import _tree_manifest, run_gatekeeper


@contextmanager
def _in_temp_repo():
    prev_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            for path in ("app", "runtime", "security/ledger", "security/keys"):
                Path(path).mkdir(parents=True, exist_ok=True)
            yield Path(tmp)
        finally:
            os.chdir(prev_cwd)


class GatekeeperProtocolTest(unittest.TestCase):
    def test_tree_manifest_skips_out_of_tree_symlink_target(self) -> None:
        with _in_temp_repo() as repo_root:
            Path("app/alpha.txt").write_text("stable", encoding="utf-8")
            outside_file = repo_root.parent / "outside-target.txt"
            outside_file.write_text("outside", encoding="utf-8")
            Path("app/outside_link.txt").symlink_to(outside_file)

            manifest = _tree_manifest(Path("app"))

            self.assertEqual([item["path"] for item in manifest], ["app/alpha.txt"])

    def test_tree_manifest_is_deterministic_with_symlink_present(self) -> None:
        with _in_temp_repo():
            Path("app/beta.txt").write_text("beta", encoding="utf-8")
            Path("app/alpha.txt").write_text("alpha", encoding="utf-8")
            Path("app/link.txt").symlink_to("alpha.txt")

            first_manifest = _tree_manifest(Path("app"))
            second_manifest = _tree_manifest(Path("app"))

            self.assertEqual(first_manifest, second_manifest)

    def test_no_drift_persists_manifest_snapshot(self) -> None:
        with _in_temp_repo():
            Path("app/alpha.txt").write_text("stable", encoding="utf-8")

            first = run_gatekeeper()
            second = run_gatekeeper()

            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            self.assertNotIn("drift", second)
            self.assertEqual(second["reasons"], [])
            self.assertIsNone(second["persistence_error"])
            self.assertEqual(second["schema_version"], 2)
            self.assertEqual(second["manifest_version"], "gatekeeper_manifest_v2")
            self.assertEqual(second["provenance"]["changed_count"], 0)
            self.assertEqual(second["provenance"]["sample_changed_paths"], [])
            self.assertTrue(Path("security/ledger/gate_manifest_snapshot.json").exists())

    def test_single_file_changed_reports_provenance_and_drift_metadata(self) -> None:
        with _in_temp_repo():
            target = Path("app/alpha.txt")
            target.write_text("version-a", encoding="utf-8")
            run_gatekeeper()

            target.write_text("version-b", encoding="utf-8")
            updated = run_gatekeeper()

            self.assertFalse(updated["ok"])
            self.assertTrue(updated.get("drift"))
            self.assertIn("drift_detected", updated["reasons"])
            self.assertEqual(updated["drift_report"]["changed_count"], 1)
            self.assertEqual(updated["drift_report"]["changed_paths"], ["app/alpha.txt"])
            self.assertEqual(updated["provenance"]["changed_count"], 1)
            self.assertEqual(updated["provenance"]["sample_changed_paths"], ["app/alpha.txt"])

            lines = Path("security/ledger/gatekeeper_events.jsonl").read_text(encoding="utf-8").splitlines()
            event = json.loads(lines[-1])
            self.assertEqual(event["schema_version"], 2)
            self.assertEqual(event["manifest_version"], "gatekeeper_manifest_v2")
            self.assertTrue(event["drift"])
            self.assertEqual(event["provenance"]["changed_count"], 1)

    def test_excluded_files_are_ignored(self) -> None:
        with _in_temp_repo():
            Path("app/alpha.txt").write_text("stable", encoding="utf-8")
            run_gatekeeper()

            Path("app/.localstate").write_text("editor", encoding="utf-8")
            Path("runtime/.gitkeep").write_text("", encoding="utf-8")
            Path("security/ledger/gate_hash.txt").write_text("tampered", encoding="utf-8")
            result = run_gatekeeper()

            self.assertTrue(result["ok"])
            self.assertNotIn("drift", result)
            self.assertEqual(result["reasons"], [])

    def test_deterministic_ordering_of_reported_changes(self) -> None:
        with _in_temp_repo():
            Path("app/zeta.txt").write_text("old", encoding="utf-8")
            Path("runtime/mid.txt").write_text("old", encoding="utf-8")
            Path("security/alpha.txt").write_text("old", encoding="utf-8")
            run_gatekeeper()

            Path("app/a_add.txt").write_text("new", encoding="utf-8")
            Path("app/zeta.txt").unlink()
            Path("runtime/mid.txt").write_text("updated", encoding="utf-8")
            Path("security/alpha.txt").write_text("updated", encoding="utf-8")
            result = run_gatekeeper()

            self.assertTrue(result["drift"])
            self.assertEqual(result["drift_report"]["added_paths"], ["app/a_add.txt"])
            self.assertEqual(result["drift_report"]["removed_paths"], ["app/zeta.txt"])
            self.assertEqual(
                result["drift_report"]["changed_paths"],
                ["runtime/mid.txt", "security/alpha.txt"],
            )

    def test_missing_paths_reason_code(self) -> None:
        with _in_temp_repo():
            Path("security/keys").rmdir()
            payload = run_gatekeeper()

            self.assertFalse(payload["ok"])
            self.assertIn("missing_paths", payload["reasons"])
            self.assertIn("security/keys", payload["missing"])

    def test_readonly_ledger_path_fails_closed(self) -> None:
        with _in_temp_repo():
            Path("app/alpha.txt").write_text("stable", encoding="utf-8")
            run_gatekeeper()

            with patch("pathlib.Path.write_text", side_effect=PermissionError("readonly")):
                payload = run_gatekeeper()

            self.assertFalse(payload["ok"])
            self.assertIn("hash_persist_failed", payload["reasons"])
            self.assertIsNotNone(payload["persistence_error"])
            self.assertEqual(payload["persistence_reason_code"], "hash_persist_failed")

    def test_invalid_ledger_path_fails_closed(self) -> None:
        with _in_temp_repo():
            Path("app/alpha.txt").write_text("stable", encoding="utf-8")
            run_gatekeeper()

            ledger_dir = Path("security/ledger")
            ledger_dir.rename("security/ledger_backup")
            ledger_dir.write_text("not-a-directory", encoding="utf-8")
            payload = run_gatekeeper()

            self.assertFalse(payload["ok"])
            self.assertIn("hash_persist_failed", payload["reasons"])
            self.assertIsNotNone(payload["persistence_error"])
            self.assertEqual(payload["persistence_reason_code"], "hash_persist_failed")


    def test_invalid_snapshot_payload_reports_structured_failure(self) -> None:
        with _in_temp_repo():
            Path("app/alpha.txt").write_text("stable", encoding="utf-8")
            run_gatekeeper()
            Path("security/ledger/gate_manifest_snapshot.json").write_text("{not-json", encoding="utf-8")

            payload = run_gatekeeper()

            self.assertFalse(payload["ok"])
            self.assertIn("hash_persist_failed", payload["reasons"])
            self.assertEqual(payload["persistence_reason_code"], "snapshot_load_failed")
            self.assertIn("JSONDecodeError", payload["persistence_error"])


if __name__ == "__main__":
    unittest.main()
