import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import unittest

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

sys.path.append(str(ROOT))

from security import cryovant  # noqa: E402
from security.ledger import journal  # noqa: E402


class CryovantEnvironmentTest(unittest.TestCase):
    def test_ledger_and_keys_present(self):
        self.assertTrue(cryovant.validate_environment())
        ledger_file = journal.ensure_ledger()
        self.assertTrue(ledger_file.exists())
        self.assertTrue(os.access(ledger_file.parent, os.W_OK))
        keys_dir = ROOT / "security" / "keys"
        self.assertTrue(keys_dir.exists())

    def test_ledger_bootstrap_failure_is_terminal_fail_closed(self):
        with patch("security.cryovant.journal.ensure_ledger", side_effect=OSError("disk-full")):
            with self.assertRaises(RuntimeError) as exc:
                cryovant.validate_environment()

        self.assertEqual(str(exc.exception), "cryovant_bootstrap_failed:ledger_bootstrap_failed")


    def test_touch_non_functional_metadata_updates_timestamp_without_resign(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir) / "agent-x"
            agent_dir.mkdir(parents=True, exist_ok=True)
            certificate_path = agent_dir / "certificate.json"
            certificate_path.write_text(
                json.dumps(
                    {
                        "signature": "cryovant-dev-seed",
                        "lineage_hash": "lineage-1",
                        "issued_at": "2025-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            before_certificate = certificate_path.read_text(encoding="utf-8")
            registry_path = Path(tmpdir) / "security" / "ledger" / "non_functional_metadata_registry.json"

            with (
                patch("security.cryovant.LEDGER_DIR", registry_path.parent),
                patch("security.cryovant.journal.write_entry") as write_entry,
                patch("security.cryovant.metrics.log") as metrics_log,
            ):
                result = cryovant.touch_non_functional_metadata(
                    "agent-x",
                    agent_dir,
                    metadata_version=4,
                    mutation_count=8,
                    metadata_last_mutation="2025-01-02T00:00:00Z",
                )

            after_certificate = certificate_path.read_text(encoding="utf-8")
            self.assertEqual(after_certificate, before_certificate)
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(registry["agent-x"]["metadata_version"], 4)
            self.assertEqual(registry["agent-x"]["metadata_mutation_count"], 8)
            self.assertEqual(registry["agent-x"]["metadata_touched_at"], "2025-01-02T00:00:00Z")
            self.assertEqual(registry["agent-x"]["signature"], "cryovant-dev-seed")
            self.assertEqual(registry["agent-x"]["lineage_hash"], "lineage-1")
            self.assertEqual(result["status"], "metadata_touched")
            self.assertEqual(result["signature"], "cryovant-dev-seed")
            self.assertEqual(result["lineage_hash"], "lineage-1")
            self.assertEqual(result["registry_path"], str(registry_path))
            write_entry.assert_called_once()
            metrics_log.assert_called_once()


if __name__ == "__main__":
    unittest.main()
