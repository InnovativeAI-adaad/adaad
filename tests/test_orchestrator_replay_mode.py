import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

import contextlib
import os
import unittest
from unittest import mock

from app.main import (
    Orchestrator,
    _apply_governance_ci_mode_defaults,
    _governance_ci_mode_enabled,
    _read_adaad_version,
    main,
)
from runtime.evolution.checkpoint_verifier import CheckpointVerificationError
from runtime.evolution.replay_mode import ReplayMode, normalize_replay_mode, parse_replay_args


class ADAADVersionReadTest(unittest.TestCase):
    def test_returns_unknown_when_version_read_fails_decode(self) -> None:
        with mock.patch("pathlib.Path.read_text", side_effect=UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid start byte")):
            self.assertEqual(_read_adaad_version(), "unknown")

    def test_returns_unknown_when_read_text_result_cannot_be_stripped(self) -> None:
        with mock.patch("pathlib.Path.read_text", return_value=None):
            self.assertEqual(_read_adaad_version(), "unknown")




class ReplayModeNormalizationTest(unittest.TestCase):
    def test_legacy_aliases_are_supported(self) -> None:
        self.assertEqual(normalize_replay_mode(True), ReplayMode.AUDIT)
        self.assertEqual(normalize_replay_mode(False), ReplayMode.OFF)
        self.assertEqual(normalize_replay_mode("full"), ReplayMode.AUDIT)
        self.assertEqual(normalize_replay_mode("audit"), ReplayMode.AUDIT)
        self.assertEqual(normalize_replay_mode("strict"), ReplayMode.STRICT)
        self.assertEqual(normalize_replay_mode("on"), ReplayMode.AUDIT)
        self.assertEqual(normalize_replay_mode("yes"), ReplayMode.AUDIT)




class ReplayModePropertiesTest(unittest.TestCase):
    def test_should_verify_property(self) -> None:
        self.assertTrue(ReplayMode.AUDIT.should_verify)
        self.assertTrue(ReplayMode.STRICT.should_verify)
        self.assertFalse(ReplayMode.OFF.should_verify)


class ReplayModeArgParsingTest(unittest.TestCase):
    def test_parse_replay_args(self) -> None:
        self.assertEqual(parse_replay_args("audit", "epoch-1"), (ReplayMode.AUDIT, "epoch-1"))
        self.assertEqual(parse_replay_args(False), (ReplayMode.OFF, ""))

class OrchestratorReplayModeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._mutation_executor_patch = mock.patch("app.main.MutationExecutor")
        self._mutation_executor_patch.start()
        self._default_provider_patch = mock.patch("app.main.default_provider", return_value=mock.Mock(deterministic=True))
        self._default_provider_patch.start()

    def tearDown(self) -> None:
        self._default_provider_patch.stop()
        self._mutation_executor_patch.stop()

    @contextlib.contextmanager
    def _boot_context(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(Orchestrator, "_register_elements"))
            stack.enter_context(mock.patch("app.main.DreamMode"))
            stack.enter_context(mock.patch("app.main.BeastModeLoop"))
            stack.enter_context(mock.patch("app.main.evaluate_boot_invariants", return_value=mock.Mock(ok=True, payload={"event_type": "boot_invariant_evaluation.v1"})))
            stack.enter_context(mock.patch.object(Orchestrator, "_verify_checkpoint_chain"))
            stack.enter_context(mock.patch.object(Orchestrator, "_health_check_architect"))
            stack.enter_context(mock.patch.object(Orchestrator, "_health_check_dream"))
            stack.enter_context(mock.patch.object(Orchestrator, "_health_check_beast"))
            stack.enter_context(mock.patch.object(Orchestrator, "_governance_gate", return_value=True))
            dump = stack.enter_context(mock.patch("app.main.dump"))
            stack.enter_context(mock.patch("app.main.journal.write_entry"))
            stack.enter_context(mock.patch.object(Orchestrator, "_register_capabilities"))
            stack.enter_context(mock.patch.object(Orchestrator, "_init_ui"))
            stack.enter_context(mock.patch("app.main.metrics.log"))
            stack.enter_context(
                mock.patch.dict(
                    os.environ,
                    {
                        "ADAAD_FORCE_DETERMINISTIC_PROVIDER": "1",
                        "ADAAD_DETERMINISTIC_SEED": "orchestrator-test-seed",
                        "ADAAD_DISABLE_MUTABLE_FS": "1",
                        "ADAAD_DISABLE_NETWORK": "1",
                    },
                    clear=False,
                )
            )
            yield dump



    def test_boot_orders_checkpoint_stage_after_cryovant_before_replay_preflight(self) -> None:
        call_order: list[str] = []

        def _mark(name: str):
            def _inner(*args, **kwargs):
                call_order.append(name)
                return None

            return _inner

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(Orchestrator, "_register_elements"))
            stack.enter_context(mock.patch("app.main.DreamMode"))
            stack.enter_context(mock.patch("app.main.BeastModeLoop"))
            stack.enter_context(mock.patch("app.main.evaluate_boot_invariants", return_value=mock.Mock(ok=True, payload={"event_type": "boot_invariant_evaluation.v1"})))
            stack.enter_context(mock.patch.object(Orchestrator, "_verify_checkpoint_chain", side_effect=_mark("checkpoint")))
            stack.enter_context(mock.patch.object(Orchestrator, "_health_check_architect"))
            stack.enter_context(mock.patch.object(Orchestrator, "_health_check_dream"))
            stack.enter_context(mock.patch.object(Orchestrator, "_health_check_beast"))
            stack.enter_context(mock.patch.object(Orchestrator, "_run_replay_preflight", side_effect=_mark("replay_preflight")))
            stack.enter_context(mock.patch.object(Orchestrator, "_governance_gate", return_value=True))
            stack.enter_context(mock.patch("app.main.dump"))
            stack.enter_context(mock.patch("app.main.journal.write_entry"))
            stack.enter_context(mock.patch.object(Orchestrator, "_register_capabilities"))
            stack.enter_context(mock.patch.object(Orchestrator, "_init_ui"))
            stack.enter_context(mock.patch("app.main.metrics.log"))
            orch = Orchestrator(replay_mode="off")
            orch.boot()

        self.assertEqual(call_order[:2], ["checkpoint", "replay_preflight"])



    def test_boot_fail_closed_emits_machine_readable_payload(self) -> None:
        failure = mock.Mock(
            ok=False,
            reason="invariants_failed:missing_required_invariant",
            payload={
                "event_type": "boot_invariant_evaluation.v1",
                "status": "error",
                "reason_code": "boot_invariant_governance_invariants_failed",
            },
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, {"ADAAD_FORCE_DETERMINISTIC_PROVIDER": "1"}, clear=False))
            stack.enter_context(mock.patch("app.main.evaluate_boot_invariants", return_value=failure))
            fail = stack.enter_context(mock.patch.object(Orchestrator, "_fail", side_effect=SystemExit(1)))
            stack.enter_context(mock.patch("app.main.metrics.log"))
            orch = Orchestrator(replay_mode="strict")
            with self.assertRaises(SystemExit):
                orch.boot()

        fail.assert_called_once_with(
            "invariants_failed:missing_required_invariant",
            payload={
                "event_type": "boot_invariant_evaluation.v1",
                "status": "error",
                "reason_code": "boot_invariant_governance_invariants_failed",
            },
        )

    def test_replay_off_skips_verification_and_continues_to_ready(self) -> None:
        with self._boot_context():
            orch = Orchestrator(replay_mode="off")
            orch.evolution_runtime.replay_preflight = mock.Mock(return_value={
                "mode": "off",
                "verify_target": "none",
                "has_divergence": False,
                "decision": "skip",
                "results": [],
            })
            orch.boot()
            self.assertEqual(orch.state["status"], "ready")
            orch.evolution_runtime.replay_preflight.assert_called_once()

    @mock.patch.object(Orchestrator, "_fail")
    def test_replay_audit_continues_on_divergence(self, fail: mock.Mock) -> None:
        with self._boot_context():
            orch = Orchestrator(replay_mode="audit")
            orch.evolution_runtime.replay_preflight = mock.Mock(return_value={
                "mode": "audit",
                "verify_target": "all_epochs",
                "has_divergence": True,
                "decision": "continue",
                "results": [{"baseline_epoch": "epoch-1", "expected_digest": "a", "actual_digest": "b", "decision": "diverge", "passed": False}],
            })
            orch.boot()
            fail.assert_not_called()
            self.assertEqual(orch.state["status"], "ready")
            self.assertTrue(orch.state["replay_divergence"])

    @mock.patch.object(Orchestrator, "_fail")
    def test_replay_strict_fails_on_divergence(self, fail: mock.Mock) -> None:
        with self._boot_context():
            orch = Orchestrator(replay_mode="strict")
            orch.evolution_runtime.replay_preflight = mock.Mock(return_value={
                "mode": "strict",
                "verify_target": "all_epochs",
                "has_divergence": True,
                "decision": "fail_closed",
                "results": [{"baseline_epoch": "epoch-1", "expected_digest": "a", "actual_digest": "b", "decision": "diverge", "passed": False}],
            })
            orch.boot()
            fail.assert_called_once_with("replay_divergence")

    def test_verify_replay_only_exits_after_preflight(self) -> None:
        with self._boot_context() as dump:
            orch = Orchestrator(replay_mode="audit")
            orch.evolution_runtime.replay_preflight = mock.Mock(return_value={
                "mode": "audit",
                "verify_target": "all_epochs",
                "has_divergence": False,
                "decision": "continue",
                "results": [],
            })
            orch.verify_replay_only()
            dump.assert_called_once()


class OrchestratorCheckpointStageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._mutation_executor_patch = mock.patch("app.main.MutationExecutor")
        self._mutation_executor_patch.start()
        self._default_provider_patch = mock.patch("app.main.default_provider", return_value=mock.Mock(deterministic=True))
        self._default_provider_patch.start()

    def tearDown(self) -> None:
        self._default_provider_patch.stop()
        self._mutation_executor_patch.stop()

    def test_checkpoint_stage_emits_verified_event_on_success(self) -> None:
        orch = Orchestrator(replay_mode="off")
        with mock.patch("app.main.CheckpointVerifier.verify_all_checkpoints", return_value={"epoch_count": 1, "checkpoint_count": 2}) as verify:
            with mock.patch("app.main.journal.write_entry") as write_entry:
                orch._verify_checkpoint_chain()

        verify.assert_called_once_with(orch.evolution_runtime.ledger.ledger_path)
        write_entry.assert_called_once()
        self.assertEqual(write_entry.call_args.kwargs["action"], "checkpoint_chain_verified")

    def test_checkpoint_stage_emits_violated_event_and_fails_closed(self) -> None:
        orch = Orchestrator(replay_mode="off")
        with mock.patch(
            "app.main.CheckpointVerifier.verify_all_checkpoints",
            side_effect=CheckpointVerificationError(code="checkpoint_prev_missing", detail="epoch=e1;index=1"),
        ):
            with mock.patch("app.main.journal.write_entry") as write_entry:
                with mock.patch.object(orch, "_fail") as fail:
                    orch._verify_checkpoint_chain()

        self.assertEqual(write_entry.call_args.kwargs["action"], "checkpoint_chain_violated")
        fail.assert_called_once_with("checkpoint_chain_violated:checkpoint_prev_missing:epoch=e1;index=1")


class GovernanceCIModeTest(unittest.TestCase):
    def test_governance_ci_mode_env_toggle(self) -> None:
        with mock.patch.dict(os.environ, {"ADAAD_GOVERNANCE_CI_MODE": "1"}, clear=False):
            self.assertTrue(_governance_ci_mode_enabled())

    def test_apply_governance_ci_mode_defaults_sets_provider_env(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            _apply_governance_ci_mode_defaults()
            self.assertEqual(os.getenv("ADAAD_FORCE_DETERMINISTIC_PROVIDER"), "1")
            self.assertEqual(os.getenv("ADAAD_DETERMINISTIC_SEED"), "adaad-governance-ci")



class OrchestratorDreamHealthMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._mutation_executor_patch = mock.patch("app.main.MutationExecutor")
        self._mutation_executor_patch.start()
        self._default_provider_patch = mock.patch("app.main.default_provider", return_value=mock.Mock(deterministic=True))
        self._default_provider_patch.start()

    def tearDown(self) -> None:
        self._default_provider_patch.stop()
        self._mutation_executor_patch.stop()

    def test_health_check_dream_logs_summary_for_ready_transition(self) -> None:
        orch = Orchestrator(replay_mode="off")
        orch.dream = mock.Mock()
        orch.dream.discover_tasks.return_value = ["task-a", "task-b"]
        orch.mutation_orchestrator = mock.Mock()
        orch.mutation_orchestrator.evaluate_dream_tasks.return_value = mock.Mock(
            status="ok",
            reason="tasks_ready",
            payload={"safe_boot": False, "task_count": 2},
        )

        with mock.patch("app.main.metrics.log") as log_metric:
            orch._health_check_dream()

        self.assertTrue(orch.state["mutation_enabled"])
        self.assertFalse(orch.state["safe_boot"])
        log_metric.assert_called_once_with(
            event_type="dream_health_ok",
            payload={"tasks": ["task-a", "task-b"]},
            level="INFO",
        )

    def test_health_check_dream_logs_summary_for_safe_boot_transition(self) -> None:
        orch = Orchestrator(replay_mode="off")
        orch.dream = mock.Mock()
        orch.dream.discover_tasks.return_value = []
        orch.mutation_orchestrator = mock.Mock()
        orch.mutation_orchestrator.evaluate_dream_tasks.return_value = mock.Mock(
            status="warn",
            reason="no_tasks",
            payload={"safe_boot": True},
        )

        with mock.patch("app.main.metrics.log") as log_metric:
            orch._health_check_dream()

        self.assertFalse(orch.state["mutation_enabled"])
        self.assertTrue(orch.state["safe_boot"])
        log_metric.assert_called_once_with(
            event_type="dream_safe_boot",
            payload={"reason": "no tasks"},
            level="WARN",
        )

if __name__ == "__main__":
    unittest.main()


class ReplayProofExportCliTest(unittest.TestCase):
    def test_export_replay_proof_uses_epoch_flag_and_deterministic_path(self) -> None:
        fake_builder = mock.Mock()
        fake_builder.write_bundle.return_value = mock.Mock(as_posix=mock.Mock(return_value="security/ledger/replay_proofs/epoch-42.replay_attestation.v1.json"))
        with mock.patch("app.main.ReplayProofBuilder", return_value=fake_builder):
            with mock.patch("sys.argv", ["app.main", "--export-replay-proof", "--epoch", "epoch-42"]):
                with mock.patch("builtins.print") as printer:
                    main()
        fake_builder.write_bundle.assert_called_once_with("epoch-42")
        printer.assert_called_once_with("security/ledger/replay_proofs/epoch-42.replay_attestation.v1.json")

    def test_export_replay_proof_requires_epoch(self) -> None:
        with mock.patch("sys.argv", ["app.main", "--export-replay-proof"]):
            with self.assertRaises(SystemExit):
                main()
