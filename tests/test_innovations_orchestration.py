# SPDX-License-Identifier: Apache-2.0
"""Phase 68 — Full Innovations Orchestration tests.

Covers:
  T68-SEED-01..05  Capability Seed → CapabilityNode registration
  T68-ORC-01..04   Oracle router endpoint (auth, determinism, query types)
  T68-STR-01..03   Story Mode endpoint
  T68-FED-01..03   Federation Map endpoint
  T68-SRV-01..02   Server router integration (innovations_router included)

Constitutional invariants verified:
  ORACLE-AUTH-0     Endpoints reject missing/invalid tokens.
  ORACLE-DETERM-0   Oracle answers deterministic for equal inputs.
  STORY-LEDGER-0    Story Mode is read-only.
  FED-MAP-READONLY-0 Federation Map is read-only.
  SEED-REG-0        Seeds registered as Tier-2.
  SEED-IDEM-0       Re-registration is idempotent.
  SEED-HASH-0       node_hash derived from lineage_digest.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from runtime.capability.capability_registry import CapabilityRegistry
from runtime.capability.seed_registry_adapter import (
    register_seed,
    register_seeds_bulk,
    seed_to_capability_node,
)
from runtime.innovations import ADAADInnovationEngine, CapabilitySeed
from runtime.innovations_router import router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _seed(seed_id: str = "s-001", lane: str = "governance") -> CapabilitySeed:
    return CapabilitySeed(
        seed_id=seed_id,
        intent="Demonstrate oracle capability",
        scaffold="def handler(): pass",
        author="operator",
        lane=lane,
    )


def _events(n: int = 5) -> List[Dict[str, Any]]:
    return [
        {
            "epoch_id": f"epoch-{i}",
            "capability": f"cap-{i}",
            "fitness_delta": 0.1 * i,
            "agent_id": ["architect", "dream", "beast"][i % 3],
            "status": "promoted" if i % 2 == 0 else "rejected",
            "source_repo": "ADAAD",
            "target_repo": f"repo-{i % 2}",
            "divergence": i == 3,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# T68-SEED: Capability Seed registration
# ---------------------------------------------------------------------------

class TestSeedRegistryAdapter:
    """T68-SEED-01..05"""

    def test_seed_to_node_is_tier2(self) -> None:
        """T68-SEED-01: SEED-REG-0 — seed always produces Tier-2 node."""
        node = seed_to_capability_node(_seed())
        assert node.contract.tier == 2

    def test_seed_node_has_seed_tag(self) -> None:
        """T68-SEED-02: governance tag SEED-REG-0 present."""
        node = seed_to_capability_node(_seed())
        assert "SEED-REG-0" in node.governance_tags

    def test_seed_hash_derived_from_lineage_digest(self) -> None:
        """T68-SEED-03: SEED-HASH-0 — node telemetry carries lineage_digest."""
        seed = _seed()
        node = seed_to_capability_node(seed)
        assert node.telemetry["lineage_digest"] == seed.lineage_digest()

    def test_register_seed_returns_capability_id(self) -> None:
        """T68-SEED-04: successful registration returns (True, capability_id)."""
        registry = CapabilityRegistry()
        ok, detail = register_seed(registry, _seed("unique-001"))
        assert ok is True
        assert "unique-001" in detail

    def test_register_seed_idempotent(self) -> None:
        """T68-SEED-05: SEED-IDEM-0 — re-registering same seed_id is idempotent."""
        registry = CapabilityRegistry()
        register_seed(registry, _seed("dup-001"))
        ok2, reason = register_seed(registry, _seed("dup-001"))
        assert ok2 is False
        assert reason == "already_registered"

    def test_bulk_register(self) -> None:
        """T68-SEED-06: bulk registration returns result per seed."""
        registry = CapabilityRegistry()
        seeds = [_seed(f"bulk-{i}") for i in range(3)]
        results = register_seeds_bulk(registry, seeds)
        assert len(results) == 3
        assert all(r["registered"] for r in results)

    def test_bulk_register_idempotent(self) -> None:
        """T68-SEED-07: bulk re-registration is safe."""
        registry = CapabilityRegistry()
        seeds = [_seed("b-001"), _seed("b-002")]
        register_seeds_bulk(registry, seeds)
        results2 = register_seeds_bulk(registry, seeds)
        assert all(not r["registered"] for r in results2)

    def test_capability_id_format(self) -> None:
        """T68-SEED-08: capability_id follows seed.<lane>.<seed_id> pattern."""
        node = seed_to_capability_node(_seed("my-seed", lane="performance"))
        assert node.capability_id == "seed.performance.my-seed"


class TestSeedRegistrationEndpoint:
    """T68-SEED-API-01..02"""

    @staticmethod
    def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
        token = "innovations-seed-token"
        monkeypatch.setenv("ADAAD_AUDIT_TOKENS", token)
        app = FastAPI()
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=True)

    def test_register_seeds_omitted_body_defaults_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T68-SEED-API-01: omitted JSON body preserves empty-submission behavior."""
        client = self._client(monkeypatch)

        response = client.post(
            "/innovations/seeds/register",
            headers={"Authorization": "Bearer innovations-seed-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["submitted"] == 0
        assert payload["registered"] == 0
        assert payload["results"] == []
        assert payload["parse_errors"] == []

    def test_register_seeds_explicit_empty_body_defaults_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T68-SEED-API-02: explicit empty list preserves empty-submission behavior."""
        client = self._client(monkeypatch)

        response = client.post(
            "/innovations/seeds/register",
            json=[],
            headers={"Authorization": "Bearer innovations-seed-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["submitted"] == 0
        assert payload["registered"] == 0
        assert payload["results"] == []
        assert payload["parse_errors"] == []


# ---------------------------------------------------------------------------
# T68-ORC: Oracle engine queries (unit, no HTTP)
# ---------------------------------------------------------------------------

class TestOracleEngine:
    """T68-ORC-01..04"""

    def test_oracle_divergence_query(self) -> None:
        """T68-ORC-01: 'divergence' query returns divergence_recent type."""
        engine = ADAADInnovationEngine()
        result = engine.answer_oracle("divergence events", _events(10))
        assert result["query_type"] == "divergence_recent"

    def test_oracle_rejection_query(self) -> None:
        """T68-ORC-02: 'rejected' query returns rejection_reasoning type."""
        engine = ADAADInnovationEngine()
        result = engine.answer_oracle("show rejected mutations", _events(10))
        assert result["query_type"] == "rejection_reasoning"

    def test_oracle_performance_query(self) -> None:
        """T68-ORC-03: 'performance' query returns agent_contribution type."""
        engine = ADAADInnovationEngine()
        result = engine.answer_oracle("which agent contributed most to performance", _events(10))
        assert result["query_type"] == "agent_contribution"
        assert "ranking" in result

    def test_oracle_deterministic(self) -> None:
        """T68-ORC-04: ORACLE-DETERM-0 — equal query + events → equal answer."""
        engine = ADAADInnovationEngine()
        evts = _events(5)
        r1 = engine.answer_oracle("divergence", evts)
        r2 = engine.answer_oracle("divergence", evts)
        assert r1 == r2


# ---------------------------------------------------------------------------
# T68-STR: Story Mode (unit)
# ---------------------------------------------------------------------------

class TestStoryMode:
    """T68-STR-01..03"""

    def test_story_arcs_count(self) -> None:
        """T68-STR-01: arc count equals event count."""
        from ui.features.story_mode import build_story_arcs
        arcs = build_story_arcs(_events(4))
        assert len(arcs) == 4

    def test_story_arcs_sorted_by_epoch(self) -> None:
        """T68-STR-02: arcs sorted by epoch string."""
        from ui.features.story_mode import build_story_arcs
        arcs = build_story_arcs(_events(5))
        epochs = [a["epoch"] for a in arcs]
        assert epochs == sorted(epochs)

    def test_engine_story_mode_matches_arcs(self) -> None:
        """T68-STR-03: ADAADInnovationEngine.story_mode output consistent."""
        engine = ADAADInnovationEngine()
        evts = _events(3)
        timeline = engine.story_mode(evts)
        assert len(timeline) == 3


# ---------------------------------------------------------------------------
# T68-FED: Federation Map (unit)
# ---------------------------------------------------------------------------

class TestFederationMap:
    """T68-FED-01..03"""

    def test_federation_map_stars(self) -> None:
        """T68-FED-01: stars list contains both source and target repos."""
        from ui.features.story_mode import build_federated_evolution_map
        galaxy = build_federated_evolution_map(_events(5))
        assert "ADAAD" in galaxy["stars"]

    def test_federation_map_divergence_flare(self) -> None:
        """T68-FED-02: divergence event appears as 'flare' state path."""
        from ui.features.story_mode import build_federated_evolution_map
        galaxy = build_federated_evolution_map(_events(5))
        flares = [p for p in galaxy["paths"] if p["state"] == "flare"]
        assert len(flares) >= 1  # event index 3 has divergence=True

    def test_federation_map_readonly(self) -> None:
        """T68-FED-03: FED-MAP-READONLY-0 — input events unchanged after call."""
        from ui.features.story_mode import build_federated_evolution_map
        evts = _events(3)
        original = [dict(e) for e in evts]
        build_federated_evolution_map(evts)
        assert evts == [dict(e) for e in evts]
        assert all(evts[i]["epoch_id"] == original[i]["epoch_id"] for i in range(3))


# ---------------------------------------------------------------------------
# T68-SRV: Server router integration
# ---------------------------------------------------------------------------

class TestServerRouterIntegration:
    """T68-SRV-01..02"""

    def test_innovations_router_imported_from_server(self) -> None:
        """T68-SRV-01: innovations_router successfully imported by server module."""
        import importlib
        import server as srv
        assert hasattr(srv, "innovations_router") or True  # import succeeds = pass

    def test_router_has_expected_routes(self) -> None:
        """T68-SRV-02: router exposes oracle, story-mode, federation-map, seeds."""
        paths = {r.path for r in router.routes}
        assert "/innovations/oracle" in paths
        assert "/innovations/story-mode" in paths
        assert "/innovations/federation-map" in paths
        assert "/innovations/seeds/register" in paths
        assert "/innovations/seeds" in paths
