# SPDX-License-Identifier: Apache-2.0
"""Aponi Story Mode helpers."""

from __future__ import annotations

from typing import Any


def build_story_arcs(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    arcs: list[dict[str, Any]] = []
    for event in events:
        arcs.append(
            {
                "epoch": event.get("epoch_id", ""),
                "title": event.get("title", "Governance event"),
                "agent": event.get("agent_id", "system"),
                "decision": event.get("decision", "none"),
                "result": event.get("status", "unknown"),
            }
        )
    return sorted(arcs, key=lambda row: str(row["epoch"]))


def build_federated_evolution_map(events: list[dict[str, Any]]) -> dict[str, Any]:
    stars: set[str] = set()
    paths: list[dict[str, str]] = []
    for event in events:
        source = str(event.get("source_repo", ""))
        target = str(event.get("target_repo", ""))
        if source:
            stars.add(source)
        if target:
            stars.add(target)
        if source and target:
            paths.append(
                {
                    "from": source,
                    "to": target,
                    "state": "flare" if event.get("divergence", False) else "stable",
                }
            )
    return {"stars": sorted(stars), "paths": paths}
