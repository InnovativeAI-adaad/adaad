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
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from security import cryovant


class CryovantDevSignatureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_root = Path(self.tmp.name)

        self._orig_keys_dir = cryovant.KEYS_DIR
        cryovant.KEYS_DIR = self.tmp_root / "keys"
        self.addCleanup(setattr, cryovant, "KEYS_DIR", self._orig_keys_dir)
        cryovant.KEYS_DIR.mkdir(parents=True, exist_ok=True)

        self._orig_adaad_env = os.environ.get("ADAAD_ENV")
        self._orig_dev_mode = os.environ.get("CRYOVANT_DEV_MODE")
        self.addCleanup(self._restore_env)

    def _restore_env(self) -> None:
        if self._orig_adaad_env is None:
            os.environ.pop("ADAAD_ENV", None)
        else:
            os.environ["ADAAD_ENV"] = self._orig_adaad_env

        if self._orig_dev_mode is None:
            os.environ.pop("CRYOVANT_DEV_MODE", None)
        else:
            os.environ["CRYOVANT_DEV_MODE"] = self._orig_dev_mode

    def test_prod_without_keys_rejects_dev_signature(self) -> None:
        os.environ["ADAAD_ENV"] = "prod"
        os.environ.pop("CRYOVANT_DEV_MODE", None)

        with mock.patch("security.cryovant.metrics.log") as metrics_log:
            self.assertFalse(cryovant.signature_valid("cryovant-dev-sample"))

        metrics_log.assert_called_once()
        self.assertEqual(metrics_log.call_args.kwargs["event_type"], "cryovant_signature_verification_without_keys")
        self.assertEqual(metrics_log.call_args.kwargs["level"], "CRITICAL")

    def test_dev_with_dev_mode_accepts_dev_signature(self) -> None:
        os.environ["ADAAD_ENV"] = "dev"
        os.environ["CRYOVANT_DEV_MODE"] = "1"

        with mock.patch("security.cryovant.metrics.log") as metrics_log:
            self.assertTrue(cryovant.signature_valid("cryovant-dev-sample"))

        event_types = [call.kwargs.get("event_type") for call in metrics_log.call_args_list]
        self.assertIn("cryovant_signature_verification_without_keys", event_types)
        self.assertIn("cryovant_dev_signature_accepted", event_types)


    def test_verify_signature_hmac_against_keys_dir(self) -> None:
        key_id = "agent-certificate"
        key_material = b"super-secret"
        (cryovant.KEYS_DIR / f"{key_id}.key").write_bytes(key_material)
        digest = cryovant.hmac.new(key_material, b"cryovant", cryovant.hashlib.sha256).hexdigest()
        self.assertTrue(cryovant.verify_signature(f"{key_id}:{digest}"))


    def test_verify_payload_signature_accepts_payload_bound_static_signature(self) -> None:
        payload = b"governance-envelope"
        digest = "sha256:" + cryovant.hashlib.sha256(payload).hexdigest()
        self.assertTrue(
            cryovant.verify_payload_signature(
                payload,
                f"cryovant-static-{digest}",
                "policy-key",
            )
        )

    def test_verify_payload_signature_accepts_hmac_signature(self) -> None:
        payload = b"replay-proof-digest"
        digest = "sha256:" + cryovant.hashlib.sha256(payload).hexdigest()
        os.environ["ADAAD_SIGNING_KEY"] = "signing-secret"
        self.addCleanup(os.environ.pop, "ADAAD_SIGNING_KEY", None)
        signature = cryovant.sign_hmac_digest(
            key_id="key-1",
            signed_digest=digest,
            specific_env_prefix="ADAAD_SIGNING_KEY_",
            generic_env_var="ADAAD_SIGNING_KEY",
            fallback_namespace="adaad-signing-dev-secret",
        )
        self.assertTrue(cryovant.verify_payload_signature(payload, signature, "key-1"))

    def test_prod_valid_real_signature_accepts(self) -> None:
        os.environ["ADAAD_ENV"] = "prod"
        (cryovant.KEYS_DIR / "signing-key.pem").write_text("key", encoding="utf-8")

        with mock.patch("security.cryovant.verify_signature", return_value=True), mock.patch(
            "security.cryovant.metrics.log"
        ) as metrics_log:
            self.assertTrue(cryovant.signature_valid("real-signature"))

        metrics_log.assert_not_called()

    def test_verify_hmac_digest_signature_accepts_legacy_unprefixed_signature(self) -> None:
        signature = cryovant.sign_hmac_digest(
            key_id="k1",
            signed_digest="sha256:" + ("a" * 64),
            specific_env_prefix="CRYOVANT_TEST_KEY_",
            generic_env_var="CRYOVANT_TEST_SIGNING_KEY",
            fallback_namespace="cryovant-test",
        )
        legacy = signature.removeprefix("sha256:")
        self.assertTrue(
            cryovant.verify_hmac_digest_signature(
                key_id="k1",
                signed_digest="sha256:" + ("a" * 64),
                signature=legacy,
                specific_env_prefix="CRYOVANT_TEST_KEY_",
                generic_env_var="CRYOVANT_TEST_SIGNING_KEY",
                fallback_namespace="cryovant-test",
            )
        )


    def test_valid_signature_accepts_agent_hmac_signature(self) -> None:
        agent_dir = self.tmp_root / "agent-a"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "meta.json").write_text("{}", encoding="utf-8")
        (agent_dir / "dna.json").write_text("{}", encoding="utf-8")
        (agent_dir / "certificate.json").write_text('{"signature": ""}', encoding="utf-8")

        lineage_hash = cryovant.compute_lineage_hash(agent_dir)
        signed_digest = f"sha256:{lineage_hash}"
        os.environ["ADAAD_SIGNING_KEY"] = "agent-cert-secret"
        self.addCleanup(os.environ.pop, "ADAAD_SIGNING_KEY", None)
        signature = cryovant.sign_hmac_digest(
            key_id="agent-certificate",
            signed_digest=signed_digest,
            specific_env_prefix="ADAAD_SIGNING_KEY_",
            generic_env_var="ADAAD_SIGNING_KEY",
            fallback_namespace="adaad-signing-dev-secret",
        )

        self.assertTrue(cryovant._valid_signature(signature, agent_dir=agent_dir))

    def test_valid_signature_legacy_fallback_logs_warning(self) -> None:
        with mock.patch("security.cryovant.metrics.log") as metrics_log:
            self.assertTrue(cryovant._valid_signature("cryovant-static-legacy"))

        metrics_log.assert_called_once()
        self.assertEqual(metrics_log.call_args.kwargs["event_type"], "cryovant_legacy_signature_accepted")
        self.assertEqual(metrics_log.call_args.kwargs["level"], "WARNING")


    def test_certify_agents_reuses_lineage_hash_per_agent(self) -> None:
        agents_root = self.tmp_root / "agents"
        agent_dir = agents_root / "agent-a"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "meta.json").write_text('{"id":"agent-a"}', encoding="utf-8")
        (agent_dir / "dna.json").write_text('{"genes":[]}', encoding="utf-8")
        (agent_dir / "certificate.json").write_text('{"signature":"sig"}', encoding="utf-8")

        call_counter = {"count": 0}
        original_compute_lineage_hash = cryovant.compute_lineage_hash

        def counting_compute_lineage_hash(path: Path) -> str:
            call_counter["count"] += 1
            return original_compute_lineage_hash(path)

        with mock.patch("security.cryovant._maybe_rotate_keys", return_value=False), mock.patch(
            "security.cryovant.verify_payload_signature", return_value=True
        ), mock.patch("security.cryovant.compute_lineage_hash", side_effect=counting_compute_lineage_hash):
            ok, errors = cryovant.certify_agents(agents_root)

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(call_counter["count"], 1)


if __name__ == "__main__":
    unittest.main()
