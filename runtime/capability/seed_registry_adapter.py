# SPDX-License-Identifier: Apache-2.0
"""Phase 68 — Capability Seed Lineage Adapter.

Registers `CapabilitySeed` instances as Tier-2 `CapabilityNode` entries inside
`CapabilityRegistry`, making seeds first-class participants in the capability
lineage ledger.

Constitutional invariants
=========================
SEED-REG-0    Every seed registered here is Tier-2 (extension / experimental).
              Seeds may never be registered as Tier-0 or Tier-1 via this adapter.
SEED-HASH-0   The CapabilityNode.node_hash is derived from the seed's own
              lineage_digest, preserving deterministic traceability.
SEED-DEP-0    Seeds carry no dependency_set by default; the caller may supply
              explicit deps but they are subject to CapabilityRegistry.CAP-DEP-0.
SEED-IDEM-0   Re-registering an existing seed_id is idempotent: the registry
              returns (False, "already_registered") without altering state.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from runtime.capability.capability_node import CapabilityContract, CapabilityNode
from runtime.capability.capability_registry import CapabilityRegistry
from runtime.innovations import CapabilitySeed


# Governance tag applied to all seed-derived capability nodes.
_SEED_TAG = "SEED-REG-0"

# Fixed version for seed-derived nodes.  Bumped by amendment only.
_SEED_NODE_VERSION = "0.1.0"


def seed_to_capability_node(
    seed: CapabilitySeed,
    *,
    additional_tags: Optional[FrozenSet[str]] = None,
    dependency_set: Optional[FrozenSet[str]] = None,
) -> CapabilityNode:
    """Convert a CapabilitySeed into a Tier-2 CapabilityNode.

    SEED-REG-0: tier is always 2.
    SEED-HASH-0: node_hash is seeded from the seed's lineage_digest.
    """
    capability_id = f"seed.{seed.lane}.{seed.seed_id}"
    tags: FrozenSet[str] = frozenset({_SEED_TAG, f"LANE-{seed.lane.upper()}"})
    if additional_tags:
        tags = tags | additional_tags

    contract = CapabilityContract(
        description=f"[Seed] {seed.intent}",
        preconditions=[f"seed_id={seed.seed_id}", f"author={seed.author}"],
        postconditions=["seed_registered_in_lineage_ledger"],
        tier=2,  # SEED-REG-0: always Tier-2
        sla_max_ms=0,
    )

    node = CapabilityNode(
        capability_id=capability_id,
        version=_SEED_NODE_VERSION,
        contract=contract,
        governance_tags=tags,
        bound_modules=[],
        dependency_set=dependency_set or frozenset(),
        telemetry={
            "lineage_digest": seed.lineage_digest(),
            "seed_id": seed.seed_id,
            "lane": seed.lane,
            "author": seed.author,
        },
    )
    return node


def register_seed(
    registry: CapabilityRegistry,
    seed: CapabilitySeed,
    *,
    additional_tags: Optional[FrozenSet[str]] = None,
    dependency_set: Optional[FrozenSet[str]] = None,
) -> Tuple[bool, str]:
    """Register a CapabilitySeed in the given CapabilityRegistry.

    SEED-IDEM-0: re-registering an existing seed is idempotent.

    Returns
    -------
    (True, capability_id)   on successful first registration.
    (False, reason)         when idempotent or on registry error.
    """
    capability_id = f"seed.{seed.lane}.{seed.seed_id}"

    # SEED-IDEM-0 — check for prior registration
    existing = registry.get(capability_id)
    if existing is not None:
        return False, "already_registered"

    node = seed_to_capability_node(
        seed,
        additional_tags=additional_tags,
        dependency_set=dependency_set,
    )
    ok, reason = registry.register(node)
    if ok:
        return True, capability_id
    return False, reason


def register_seeds_bulk(
    registry: CapabilityRegistry,
    seeds: List[CapabilitySeed],
) -> List[Dict[str, Any]]:
    """Register multiple seeds; returns a result list for each.

    Idempotent per seed (SEED-IDEM-0). Never raises.
    """
    results = []
    for seed in seeds:
        try:
            ok, detail = register_seed(registry, seed)
            results.append({"seed_id": seed.seed_id, "registered": ok, "detail": detail})
        except Exception as exc:  # noqa: BLE001
            results.append({"seed_id": seed.seed_id, "registered": False, "detail": str(exc)})
    return results


__all__ = [
    "register_seed",
    "register_seeds_bulk",
    "seed_to_capability_node",
]
