# SPDX-License-Identifier: Apache-2.0
from runtime.innovations import (
    ADAADInnovationEngine,
    CapabilitySeed,
    MutationPersonality,
    NoNewDependenciesPlugin,
    DocstringRequiredPlugin,
)
from security.identity_rings import build_ring_token
from ui.features.story_mode import build_federated_evolution_map, build_story_arcs


def test_capability_seed_digest_is_deterministic() -> None:
    seed = CapabilitySeed(
        seed_id="seed-001",
        intent="Build oracle capability",
        scaffold="def handler(): pass",
        author="operator",
        lane="governance",
    )
    assert seed.lineage_digest() == seed.lineage_digest()


def test_vision_mode_and_plugins_are_deterministic() -> None:
    engine = ADAADInnovationEngine()
    events = [
        {"epoch_id": "e-1", "capability": "oracle", "fitness_delta": 0.2, "path": "path-0"},
        {"epoch_id": "e-2", "capability": "story_mode", "fitness_delta": 0.1, "dead_end": True, "path": "path-1", "blocking_cause": "policy_gate"},
    ]
    p1 = engine.run_vision_mode(events, horizon_epochs=150, seed_input="fixed-seed")
    p2 = engine.run_vision_mode(events, horizon_epochs=150, seed_input="fixed-seed")
    assert p1 == p2
    projection = p1
    assert projection.horizon_epochs == 150
    assert projection.trajectory_bands is not None
    assert projection.confidence_metadata is not None
    assert projection.dead_end_diagnostics[0]["path_id"] == "path-1"
    results = engine.run_plugins(
        {"new_dependencies": [], "missing_docstrings": 0},
        [NoNewDependenciesPlugin(), DocstringRequiredPlugin()],
    )
    assert all(result.passed for result in results)


def test_personality_selection_stable_for_epoch() -> None:
    engine = ADAADInnovationEngine()
    selected = engine.select_personality(
        [
            MutationPersonality("architect", (0.9, 0.2, 0.3, 0.1), "minimalist"),
            MutationPersonality("dream", (0.6, 0.8, 0.4, 0.2), "aggressive"),
        ],
        epoch_id="epoch-100",
    )
    assert selected.agent_id in {"architect", "dream"}


def test_identity_ring_digest_is_stable() -> None:
    token1 = build_ring_token("agent", "dream", {"role": "mutator"})
    token2 = build_ring_token("agent", "dream", {"role": "mutator"})
    assert token1.digest == token2.digest


def test_story_and_federation_map_builders() -> None:
    events = [
        {"epoch_id": "1", "title": "Epoch 1", "source_repo": "A", "target_repo": "B"},
        {"epoch_id": "2", "title": "Epoch 2", "source_repo": "B", "target_repo": "C", "divergence": True},
    ]
    arcs = build_story_arcs(events)
    galaxy = build_federated_evolution_map(events)
    assert len(arcs) == 2
    assert galaxy["stars"] == ["A", "B", "C"]
