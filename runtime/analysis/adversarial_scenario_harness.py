# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from runtime import metrics
from runtime.governance.foundation.determinism import SystemDeterminismProvider, require_replay_safe_provider
from runtime.governance.gate_certifier import GateCertifier
from runtime.recovery.tier_manager import RecoveryTierLevel, TierManager
from security import cryovant


@dataclass(frozen=True)
class AdversarialScenario:
    scenario_id: str
    narrative: str
    seed: str
    expected_verdict: str
    expected_evidence: tuple[str, ...]


ScenarioEvaluator = Callable[[AdversarialScenario], dict[str, Any]]


@contextmanager
def _temp_env(overrides: dict[str, str]) -> Any:
    previous: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def _evidence_pointer(path: str, detail: str) -> str:
    return f"{path}::{detail}"


def _legacy_signature_misuse(scenario: AdversarialScenario) -> dict[str, Any]:
    payload = f"payload:{scenario.seed}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    signature = f"cryovant-static-{digest}"
    baseline_events = len(metrics.tail(limit=200))

    with _temp_env(
        {
            "ADAAD_ENV": "prod",
            "CRYOVANT_DEV_MODE": "0",
            "ADAAD_ENABLE_LEGACY_STATIC_SIGNATURES": "1",
        }
    ):
        accepted = cryovant.verify_payload_signature(payload, signature, key_id="redteam")

    observed = metrics.tail(limit=200)
    new_events = observed[baseline_events:]
    has_critical_audit = any(
        entry.get("event") == "cryovant_legacy_static_payload_signature_rejected" and entry.get("level") == "CRITICAL"
        for entry in new_events
    )
    blocked = (not accepted) and has_critical_audit
    return {
        "actual_verdict": "block" if blocked else "allow",
        "evidence": {
            "legacy_signature_rejected": not accepted,
            "critical_audit_event": has_critical_audit,
            "pointers": [
                _evidence_pointer("security/cryovant.py", "verify_payload_signature"),
                _evidence_pointer("reports/metrics.jsonl", "cryovant_legacy_static_payload_signature_rejected"),
            ],
        },
    }


def _dev_token_leakage(scenario: AdversarialScenario) -> dict[str, Any]:
    token = f"dev-token-{scenario.seed}"
    with _temp_env(
        {
            "ADAAD_ENV": "prod",
            "CRYOVANT_DEV_MODE": "1",
            "CRYOVANT_DEV_TOKEN": token,
            "ADAAD_ENABLE_LEGACY_DEV_TOKEN_OVERRIDE": "1",
        }
    ):
        accepted = cryovant.verify_governance_token(token)
    blocked = not accepted
    return {
        "actual_verdict": "block" if blocked else "allow",
        "evidence": {
            "dev_token_rejected_in_prod": blocked,
            "pointers": [_evidence_pointer("security/cryovant.py", "verify_governance_token")],
        },
    }


def _determinism_bypass(_: AdversarialScenario) -> dict[str, Any]:
    error: str | None = None
    try:
        require_replay_safe_provider(SystemDeterminismProvider(), replay_mode="strict", recovery_tier="critical")
    except RuntimeError as exc:
        error = str(exc)
    blocked = error == "strict_replay_requires_deterministic_provider"
    return {
        "actual_verdict": "block" if blocked else "allow",
        "evidence": {
            "runtime_error": error,
            "pointers": [_evidence_pointer("runtime/governance/foundation/determinism.py", "require_replay_safe_provider")],
        },
    }


def _certification_partial_bypass(scenario: AdversarialScenario) -> dict[str, Any]:
    with TemporaryDirectory() as tmpdir:
        candidate = Path(tmpdir) / "candidate.py"
        candidate.write_text(
            "def safe_bridge():\n"
            "    # token-level primitive should still be blocked\n"
            "    marker = 'exec('\n"
            "    return marker\n",
            encoding="utf-8",
        )

        with _temp_env(
            {
                "ADAAD_ENV": "dev",
                "CRYOVANT_DEV_MODE": "1",
                "ADAAD_GOVERNANCE_SESSION_SIGNING_KEY": f"governance-secret-{scenario.seed}",
            }
        ):
            token = cryovant.sign_governance_token(key_id="rt", expires_at=4_102_444_800, nonce=scenario.seed)
            cert = GateCertifier(clock_now_iso=lambda: "2026-01-01T00:00:00Z").certify(
                candidate,
                metadata={"cryovant_token": token, "scenario_id": scenario.scenario_id},
            )

    blocked = cert["status"] == "REJECTED" and cert["checks"]["token_ok"] is False
    ledger_hashes = [entry.get("ledger_hash", "") for entry in cert.get("event", []) if isinstance(entry, dict)]
    return {
        "actual_verdict": "block" if blocked else "allow",
        "evidence": {
            "status": cert["status"],
            "token_ok": cert["checks"]["token_ok"],
            "ledger_hashes": ledger_hashes,
            "pointers": [_evidence_pointer("runtime/governance/gate_certifier.py", "token_ok=false")],
        },
    }


def _recovery_churn(_: AdversarialScenario) -> dict[str, Any]:
    manager = TierManager(violation_window_seconds=30, recovery_window_seconds=120)
    clock = {"now": 1000.0}

    import runtime.recovery.tier_manager as tier_manager_module

    original_time = tier_manager_module.time.time
    tier_manager_module.time.time = lambda: clock["now"]
    try:
        for _ in range(3):
            manager.record_governance_violation()
        manager.auto_evaluate_and_apply(reason="initial_violation_burst")
        clock["now"] += 31.0
        tier_after_short_gap = manager.auto_evaluate_and_apply(reason="short_gap_attempt")
        no_premature_deescalation = tier_after_short_gap == RecoveryTierLevel.GOVERNANCE
        clock["now"] += 120.0
        tier_after_window = manager.auto_evaluate_and_apply(reason="recovery_window_elapsed")
    finally:
        tier_manager_module.time.time = original_time

    blocked = no_premature_deescalation and tier_after_window == RecoveryTierLevel.NONE
    return {
        "actual_verdict": "block" if blocked else "allow",
        "evidence": {
            "tier_after_short_gap": tier_after_short_gap.value,
            "tier_after_window": tier_after_window.value,
            "transition_count": len(manager.tier_history),
            "pointers": [_evidence_pointer("runtime/recovery/tier_manager.py", "_can_deescalate")],
        },
    }


EVALUATORS: dict[str, ScenarioEvaluator] = {
    "legacy_signature_misuse": _legacy_signature_misuse,
    "dev_token_leakage": _dev_token_leakage,
    "determinism_bypass": _determinism_bypass,
    "certification_partial_check_bypass": _certification_partial_bypass,
    "recovery_churn": _recovery_churn,
}


def load_manifest(path: Path) -> list[AdversarialScenario]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios: list[AdversarialScenario] = []
    for item in payload["scenarios"]:
        scenarios.append(
            AdversarialScenario(
                scenario_id=item["scenario_id"],
                narrative=item["narrative"],
                seed=item["seed"],
                expected_verdict=item["expected_verdict"],
                expected_evidence=tuple(item.get("expected_evidence", [])),
            )
        )
    scenarios.sort(key=lambda entry: entry.scenario_id)
    return scenarios


def run_manifest(path: Path) -> dict[str, Any]:
    scenarios = load_manifest(path)
    results: list[dict[str, Any]] = []
    failed = 0

    for scenario in scenarios:
        evaluator = EVALUATORS.get(scenario.narrative)
        if evaluator is None:
            raise ValueError(f"unknown_narrative:{scenario.narrative}")
        evaluation = evaluator(scenario)
        actual_verdict = str(evaluation["actual_verdict"])
        evidence = dict(evaluation["evidence"])
        missing_evidence = sorted(key for key in scenario.expected_evidence if key not in evidence)
        passed = actual_verdict == scenario.expected_verdict and not missing_evidence
        if not passed:
            failed += 1
        results.append(
            {
                "scenario_id": scenario.scenario_id,
                "seed": scenario.seed,
                "narrative": scenario.narrative,
                "expected_verdict": scenario.expected_verdict,
                "actual_verdict": actual_verdict,
                "passed": passed,
                "missing_evidence_keys": missing_evidence,
                "evidence": evidence,
                "evidence_pointers": evidence.get("pointers", []),
            }
        )

    report = {
        "schema_version": "1.0",
        "scenario_count": len(results),
        "failed_count": failed,
        "complete": failed == 0,
        "results": results,
    }
    report["report_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return report


def write_summary(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = ["AdversarialScenario", "load_manifest", "run_manifest", "write_summary"]
