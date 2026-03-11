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
        key_material = b"super-secret"
        (cryovant.KEYS_DIR / "agent-certificate.key").write_bytes(key_material)
        digest = cryovant.hmac.new(key_material, b"cryovant", cryovant.hashlib.sha256).hexdigest()
        self.assertTrue(cryovant.verify_signature(f"sha256:{digest}"))

    def test_verify_signature_rejects_bad_signature(self) -> None:
        key_material = b"super-secret"
        (cryovant.KEYS_DIR / "agent-certificate.key").write_bytes(key_material)
        self.assertFalse(cryovant.verify_signature(f"sha256:{'0' * 64}"))

    def test_verify_signature_rejects_malformed_prefix(self) -> None:
        key_material = b"super-secret"
        (cryovant.KEYS_DIR / "agent-certificate.key").write_bytes(key_material)
        digest = cryovant.hmac.new(key_material, b"cryovant", cryovant.hashlib.sha256).hexdigest()
        self.assertFalse(cryovant.verify_signature(f"md5:{digest}"))

    def test_verify_signature_rejects_when_key_missing(self) -> None:
        self.assertFalse(cryovant.verify_signature(f"sha256:{'0' * 64}"))

    def test_verify_signature_accepts_rotated_key_deterministically(self) -> None:
        old_key_material = b"old-secret"
        new_key_material = b"new-secret"
        (cryovant.KEYS_DIR / "001-old.key").write_bytes(old_key_material)
        (cryovant.KEYS_DIR / "002-current.key").write_bytes(new_key_material)

        new_digest = cryovant.hmac.new(new_key_material, b"cryovant", cryovant.hashlib.sha256).hexdigest()
        old_digest = cryovant.hmac.new(old_key_material, b"cryovant", cryovant.hashlib.sha256).hexdigest()

        self.assertTrue(cryovant.verify_signature(f"sha256:{new_digest}"))
        self.assertTrue(cryovant.verify_signature(f"sha256:{old_digest}"))


    def test_verify_payload_signature_accepts_payload_bound_static_signature_in_dev_mode(self) -> None:
        payload = b"governance-envelope"
        digest = "sha256:" + cryovant.hashlib.sha256(payload).hexdigest()
        os.environ["ADAAD_ENV"] = "dev"
        os.environ["CRYOVANT_DEV_MODE"] = "1"
        self.assertTrue(
            cryovant.verify_payload_signature(
                payload,
                f"cryovant-static-{digest}",
                "policy-key",
            )
        )

    def test_verify_payload_signature_rejects_payload_bound_static_signature_in_prod(self) -> None:
        payload = b"governance-envelope"
        digest = "sha256:" + cryovant.hashlib.sha256(payload).hexdigest()
        os.environ["ADAAD_ENV"] = "prod"
        os.environ.pop("CRYOVANT_DEV_MODE", None)
        self.assertFalse(
            cryovant.verify_payload_signature(
                payload,
                f"cryovant-static-{digest}",
                "policy-key",
            )
        )

    def test_verify_payload_signature_static_fallback_disabled_in_strict_context(self) -> None:
        payload = b"governance-envelope"
        digest = "sha256:" + cryovant.hashlib.sha256(payload).hexdigest()
        os.environ["ADAAD_ENV"] = "dev"
        os.environ["ADAAD_REPLAY_MODE"] = "strict"
        os.environ["CRYOVANT_DEV_MODE"] = "1"
        os.environ.pop("ADAAD_ENABLE_LEGACY_STATIC_SIGNATURES", None)
        self.addCleanup(os.environ.pop, "ADAAD_REPLAY_MODE", None)
        self.assertFalse(
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
        os.environ["ADAAD_ENV"] = "dev"
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
        os.environ["ADAAD_ENV"] = "dev"
        with mock.patch("security.cryovant.metrics.log") as metrics_log:
            self.assertTrue(cryovant._valid_signature("cryovant-static-legacy"))

        metrics_log.assert_called_once()
        self.assertEqual(metrics_log.call_args.kwargs["event_type"], "cryovant_legacy_signature_accepted")
        self.assertEqual(metrics_log.call_args.kwargs["level"], "WARNING")

    def test_valid_signature_legacy_fallback_disabled_by_default_in_strict_context(self) -> None:
        os.environ["ADAAD_ENV"] = "dev"
        os.environ["ADAAD_REPLAY_MODE"] = "strict"
        os.environ.pop("ADAAD_ENABLE_LEGACY_STATIC_SIGNATURES", None)
        self.addCleanup(os.environ.pop, "ADAAD_REPLAY_MODE", None)

        self.assertFalse(cryovant._valid_signature("cryovant-static-legacy"))


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
            ok, errors = cryovant.certify_agents(agents_root, repair=True)

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(call_counter["count"], 1)

    def test_certify_agents_validation_mode_reports_missing_lineage_hash_without_writing(self) -> None:
        agents_root = self.tmp_root / "agents"
        agent_dir = agents_root / "agent-a"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "meta.json").write_text('{"id":"agent-a"}', encoding="utf-8")
        (agent_dir / "dna.json").write_text('{"genes":[]}', encoding="utf-8")
        cert_path = agent_dir / "certificate.json"
        original_certificate = '{"signature":"sig"}'
        cert_path.write_text(original_certificate, encoding="utf-8")

        with mock.patch("security.cryovant._maybe_rotate_keys", return_value=False), mock.patch(
            "security.cryovant.verify_payload_signature", return_value=True
        ):
            ok, errors = cryovant.certify_agents(agents_root)

        self.assertFalse(ok)
        self.assertIn("agent-a:missing_lineage_hash", errors)
        self.assertEqual(cert_path.read_text(encoding="utf-8"), original_certificate)

    def test_certify_agents_repair_mode_writes_lineage_hash_and_logs_repair_event(self) -> None:
        agents_root = self.tmp_root / "agents"
        agent_dir = agents_root / "agent-a"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "meta.json").write_text('{"id":"agent-a"}', encoding="utf-8")
        (agent_dir / "dna.json").write_text('{"genes":[]}', encoding="utf-8")
        cert_path = agent_dir / "certificate.json"
        cert_path.write_text('{"signature":"sig"}', encoding="utf-8")
        expected_lineage_hash = cryovant.compute_lineage_hash(agent_dir)

        with mock.patch("security.cryovant._maybe_rotate_keys", return_value=False), mock.patch(
            "security.cryovant.verify_payload_signature", return_value=True
        ), mock.patch("security.cryovant.metrics.log") as metrics_log:
            ok, errors = cryovant.certify_agents(agents_root, repair=True)

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        repaired_cert = cryovant._read_json(cert_path)
        self.assertEqual(repaired_cert.get("lineage_hash"), expected_lineage_hash)
        event_types = [call.kwargs.get("event_type") for call in metrics_log.call_args_list]
        self.assertIn("cryovant_certificate_repaired", event_types)


    def test_compute_lineage_hash_fail_closes_on_malformed_critical_json(self) -> None:
        agent_dir = self.tmp_root / "agent-b"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "meta.json").write_text('{"id":"agent-b"}', encoding="utf-8")
        (agent_dir / "dna.json").write_text('{"genes":[]}', encoding="utf-8")
        (agent_dir / "certificate.json").write_text('{"signature":', encoding="utf-8")

        with mock.patch("security.cryovant.metrics.log") as metrics_log, mock.patch(
            "security.cryovant.journal.write_entry"
        ) as write_entry:
            with self.assertRaises(cryovant.CriticalArtifactReadError) as exc:
                cryovant.compute_lineage_hash(agent_dir)

        self.assertIn("critical_json_parse_error", str(exc.exception))
        self.assertEqual(metrics_log.call_args.kwargs["event_type"], "cryovant_critical_json_read_failed")
        self.assertEqual(metrics_log.call_args.kwargs["payload"]["reason_code"], "critical_json_parse_error")
        self.assertEqual(write_entry.call_args.kwargs["action"], "critical_json_read_failed")

    def test_rotation_metadata_fail_closes_on_malformed_critical_json(self) -> None:
        rotation_path = self.tmp_root / "rotation" / "rotation.json"
        rotation_path.parent.mkdir(parents=True, exist_ok=True)
        rotation_path.write_text('{"interval_seconds":', encoding="utf-8")

        with mock.patch("security.cryovant.ROTATION_METADATA_PATH", rotation_path), mock.patch(
            "security.cryovant.metrics.log"
        ) as metrics_log, mock.patch("security.cryovant.journal.write_entry") as write_entry:
            with self.assertRaises(cryovant.CriticalArtifactReadError) as exc:
                cryovant._load_rotation_metadata()

        self.assertIn("critical_json_parse_error", str(exc.exception))
        self.assertEqual(metrics_log.call_args.kwargs["event_type"], "cryovant_critical_json_read_failed")
        self.assertEqual(metrics_log.call_args.kwargs["payload"]["path"], str(rotation_path))
        self.assertEqual(write_entry.call_args.kwargs["payload"]["reason_code"], "critical_json_parse_error")

    def test_verify_governance_token_accepts_signed_token(self) -> None:
        os.environ["ADAAD_GOVERNANCE_SESSION_SIGNING_KEY"] = "gov-secret"
        self.addCleanup(os.environ.pop, "ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", None)
        token = cryovant.sign_governance_token(key_id="orchestrator", expires_at=4102444800, nonce="abc123")
        self.assertTrue(cryovant.verify_governance_token(token))

    def test_verify_governance_token_rejects_expired_token(self) -> None:
        os.environ["ADAAD_GOVERNANCE_SESSION_SIGNING_KEY"] = "gov-secret"
        self.addCleanup(os.environ.pop, "ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", None)
        token = cryovant.sign_governance_token(key_id="orchestrator", expires_at=1, nonce="expired")
        with self.assertRaises(cryovant.TokenExpiredError):
            cryovant.verify_governance_token(token)

    def test_verify_governance_token_allows_dev_override_only_in_explicit_dev_mode(self) -> None:
        os.environ["CRYOVANT_DEV_TOKEN"] = "dev-token"
        self.addCleanup(os.environ.pop, "CRYOVANT_DEV_TOKEN", None)

        os.environ["ADAAD_ENV"] = "prod"
        os.environ.pop("CRYOVANT_DEV_MODE", None)
        self.assertFalse(cryovant.verify_governance_token("dev-token"))

        os.environ["ADAAD_ENV"] = "dev"
        os.environ["CRYOVANT_DEV_MODE"] = "1"
        self.assertTrue(cryovant.verify_governance_token("dev-token"))

    def test_verify_governance_token_rejects_dev_override_when_legacy_flag_disabled(self) -> None:
        os.environ["CRYOVANT_DEV_TOKEN"] = "dev-token"
        os.environ["ADAAD_ENV"] = "dev"
        os.environ["CRYOVANT_DEV_MODE"] = "1"
        os.environ["ADAAD_ENABLE_LEGACY_DEV_TOKEN_OVERRIDE"] = "0"
        self.addCleanup(os.environ.pop, "CRYOVANT_DEV_TOKEN", None)
        self.addCleanup(os.environ.pop, "ADAAD_ENV", None)
        self.addCleanup(os.environ.pop, "CRYOVANT_DEV_MODE", None)
        self.addCleanup(os.environ.pop, "ADAAD_ENABLE_LEGACY_DEV_TOKEN_OVERRIDE", None)

        self.assertFalse(cryovant.verify_governance_token("dev-token"))


    def test_sign_governance_token_rejects_delimiter_in_fields(self) -> None:
        with self.assertRaises(ValueError):
            cryovant.sign_governance_token(key_id="bad:key", expires_at=4102444800, nonce="ok")
        with self.assertRaises(ValueError):
            cryovant.sign_governance_token(key_id="ok", expires_at=4102444800, nonce="bad:nonce")

    def test_verify_governance_token_rejects_field_delimiter_in_payload(self) -> None:
        os.environ["ADAAD_GOVERNANCE_SESSION_SIGNING_KEY"] = "gov-secret"
        self.addCleanup(os.environ.pop, "ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", None)
        token = cryovant.sign_governance_token(key_id="orchestrator", expires_at=4102444800, nonce="abc123")
        tampered = token.replace(":abc123:", ":abc:123:")
        self.assertFalse(cryovant.verify_governance_token(tampered))


if __name__ == "__main__":
    unittest.main()
