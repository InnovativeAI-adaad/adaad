# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os

import pytest

from adaad.agents.base_agent import stage_offspring
from app.beast_mode_loop import BeastModeLoop
from runtime.evolution import lineage_v2, promotion_manifest
from runtime.evolution.promotion_events import create_promotion_event, derive_event_id
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.evolution.promotion_state_machine import PromotionState
from runtime.governance.foundation import SeededDeterminismProvider
from runtime.governance.foundation.hashing import ZERO_HASH

pytestmark = pytest.mark.regression_standard

_PROMOTION_ENV_KEYS = (
    "ADAAD_FITNESS_THRESHOLD",
    "ADAAD_AUTONOMY_THRESHOLD",
)


@pytest.fixture(autouse=True)
def _restore_promotion_process_state() -> None:
    env_snapshot = {key: os.environ.get(key) for key in _PROMOTION_ENV_KEYS}
    ledger_v2_path = lineage_v2.LEDGER_V2_PATH
    lineage_path = lineage_v2.LINEAGE_V2_PATH
    promotion_ledger = promotion_manifest.LEDGER_V2_PATH
    try:
        yield
    finally:
        for key, value in env_snapshot.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        lineage_v2.LEDGER_V2_PATH = ledger_v2_path
        lineage_v2.LINEAGE_V2_PATH = lineage_path
        promotion_manifest.LEDGER_V2_PATH = promotion_ledger


def test_event_id_determinism() -> None:
    first = derive_event_id("mut-1", PromotionState.CERTIFIED, PromotionState.ACTIVATED, None)
    second = derive_event_id("mut-1", PromotionState.CERTIFIED, PromotionState.ACTIVATED, None)
    assert first == second


def test_promotion_event_hash_chain() -> None:
    provider = SeededDeterminismProvider(seed="promo")
    event_one = create_promotion_event(
        mutation_id="mut-1",
        epoch_id="epoch-1",
        from_state=PromotionState.PROPOSED,
        to_state=PromotionState.CERTIFIED,
        actor_type="SYSTEM",
        actor_id="engine",
        policy_version="v1.0.0",
        payload={"score": 0.7},
        prev_event_hash=None,
        provider=provider,
        replay_mode="strict",
    )
    event_two = create_promotion_event(
        mutation_id="mut-1",
        epoch_id="epoch-1",
        from_state=PromotionState.CERTIFIED,
        to_state=PromotionState.ACTIVATED,
        actor_type="SYSTEM",
        actor_id="engine",
        policy_version="v1.0.0",
        payload={"score": 0.9},
        prev_event_hash=event_one["event_hash"],
        provider=provider,
        replay_mode="strict",
    )

    assert event_one["prev_event_hash"] == ZERO_HASH
    assert event_two["prev_event_hash"] == event_one["event_hash"]
    assert event_one["event_hash"].startswith("sha256:")
    assert event_two["event_hash"].startswith("sha256:")


def test_a_contaminates_process_state_without_local_cleanup(tmp_path) -> None:
    contaminated = tmp_path / "contaminated_lineage_v2.jsonl"
    os.environ["ADAAD_FITNESS_THRESHOLD"] = "999"
    lineage_v2.LEDGER_V2_PATH = contaminated
    lineage_v2.LINEAGE_V2_PATH = contaminated
    promotion_manifest.LEDGER_V2_PATH = contaminated

    assert os.environ["ADAAD_FITNESS_THRESHOLD"] == "999"
    assert lineage_v2.LEDGER_V2_PATH == contaminated
    assert promotion_manifest.LEDGER_V2_PATH == contaminated


def test_run_after_contaminated_state_remains_deterministic() -> None:
    assert os.environ.get("ADAAD_FITNESS_THRESHOLD") != "999"

    first = derive_event_id("mut-regression", PromotionState.CERTIFIED, PromotionState.ACTIVATED, None)
    second = derive_event_id("mut-regression", PromotionState.CERTIFIED, PromotionState.ACTIVATED, None)

    assert first == second


def test_promotion_cycle_appends_promotion_policy_evaluated_event(tmp_path, monkeypatch) -> None:
    agents_root = tmp_path / "agents"
    lineage_dir = agents_root / "lineage"
    agent_dir = agents_root / "agentA"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "meta.json").write_text(json.dumps({"name": "agentA"}), encoding="utf-8")
    (agent_dir / "dna.json").write_text(json.dumps({"seq": "abc"}), encoding="utf-8")
    (agent_dir / "certificate.json").write_text(json.dumps({"signature": "seed"}), encoding="utf-8")

    staged = stage_offspring("agentA", "mutation-source", lineage_dir)
    payload = json.loads((staged / "mutation.json").read_text(encoding="utf-8"))
    payload.update({"mutation_id": "decision-allow", "expected_gain": 0.9, "risk_score": 0.1, "complexity": 0.1, "coverage_delta": 0.4})
    (staged / "mutation.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr("app.beast_mode_loop.fitness.score_mutation", lambda *_: 0.95)
    monkeypatch.setattr("security.cryovant.evolve_certificate", lambda *args, **kwargs: None)

    lineage_ledger_path = tmp_path / "lineage_v2.jsonl"
    monkeypatch.setattr("runtime.evolution.promotion_manifest.LEDGER_V2_PATH", lineage_ledger_path)

    beast = BeastModeLoop(agents_root, lineage_dir)
    result = beast._legacy.run_cycle("agentA")
    assert result["status"] == "promoted"

    events = LineageLedgerV2(lineage_ledger_path).read_all()
    lifecycle_events = [event.get("payload") for event in events if event.get("type") == "PRLifecycleEvent"]
    assert any(event.get("event_type") == "promotion_policy_evaluated" for event in lifecycle_events if isinstance(event, dict))
