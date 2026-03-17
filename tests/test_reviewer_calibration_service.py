# SPDX-License-Identifier: Apache-2.0
"""Equivalence tests for reviewer calibration service ledger filtering.

Performance contract: the service must compute calibration from epoch-filtered
ledger rows without changing deterministic output semantics versus the previous
broad-scan implementation.
"""

from __future__ import annotations

from typing import Any, Iterable

from runtime.api.runtime_services import reviewer_calibration_service
from runtime.governance.review_pressure import HIGH_REPUTATION_THRESHOLD, compute_tier_reviewer_count
from runtime.governance.reviewer_reputation import SCORING_ALGORITHM_VERSION, compute_epoch_reputation_batch
from security.ledger import journal


def _legacy_reviewer_calibration_service(*, epoch_id: str, reviewer_ids: Iterable[str] | None = None) -> dict[str, Any]:
    events = journal.read_entries(limit=5_000)
    normalized_reviewer_ids = [rid.strip() for rid in (reviewer_ids or []) if rid and rid.strip()]

    if not normalized_reviewer_ids:
        inferred: set[str] = set()
        for entry in events:
            payload = entry.get("payload") if isinstance(entry, dict) else {}
            if isinstance(payload, dict) and str(payload.get("epoch_id") or "") == epoch_id:
                reviewer_id = str(payload.get("reviewer_id") or "").strip()
                if reviewer_id:
                    inferred.add(reviewer_id)
        normalized_reviewer_ids = sorted(inferred)

    reputation_scores = compute_epoch_reputation_batch(
        normalized_reviewer_ids,
        events,
        epoch_id=epoch_id,
        scoring_algorithm_version=SCORING_ALGORITHM_VERSION,
    )
    composite_scores = [record["composite_score"] for record in reputation_scores.values()]
    avg_reputation = round(sum(composite_scores) / len(composite_scores), 6) if composite_scores else 0.0
    cohort_summary = {
        "high": sum(1 for score in composite_scores if score >= HIGH_REPUTATION_THRESHOLD),
        "standard": sum(1 for score in composite_scores if 0.60 <= score < HIGH_REPUTATION_THRESHOLD),
        "low": sum(1 for score in composite_scores if score < 0.60),
    }
    calibration = compute_tier_reviewer_count("standard", avg_reputation)
    tier_pressure = "extended" if calibration["adjustment"] < 0 else "elevated" if calibration["adjustment"] > 0 else "nominal"
    return {
        "cohort_summary": cohort_summary,
        "avg_reputation": avg_reputation,
        "tier_pressure": tier_pressure,
    }


def _events_fixture() -> list[dict[str, Any]]:
    return [
        {"action": "heartbeat", "payload": {"epoch_id": "epoch-9", "reviewer_id": "noop"}},
        {
            "event_type": "reviewer_action_outcome",
            "payload": {
                "epoch_id": "epoch-7",
                "reviewer_id": "alice",
                "latency_seconds": 500,
                "sla_seconds": 1000,
                "overridden_by_authority": False,
                "long_term_mutation_impact_score": 0.9,
                "governance_alignment_score": 0.85,
            },
        },
        {
            "event_type": "reviewer_action_outcome",
            "payload": {
                "epoch_id": "epoch-7",
                "reviewer_id": "bob",
                "latency_seconds": 1200,
                "sla_seconds": 1000,
                "overridden_by_authority": True,
                "long_term_mutation_impact_score": 0.4,
                "governance_alignment_score": 0.5,
            },
        },
        {
            "event_type": "reviewer_action_outcome",
            "payload": {
                "epoch_id": "epoch-8",
                "reviewer_id": "alice",
                "latency_seconds": 50,
                "sla_seconds": 1000,
                "overridden_by_authority": False,
                "long_term_mutation_impact_score": 0.95,
                "governance_alignment_score": 0.92,
            },
        },
        {
            "event_type": "reviewer_action_outcome",
            "payload": {
                "epoch_id": "epoch-7",
                "reviewer_id": "alice",
                "latency_seconds": 800,
                "sla_seconds": 1000,
                "overridden_by_authority": False,
                "long_term_mutation_impact_score": 0.88,
                "governance_alignment_score": 0.9,
            },
        },
    ]


def test_reviewer_calibration_equivalent_without_selector(monkeypatch) -> None:
    events = _events_fixture()
    monkeypatch.setattr(journal, "read_entries", lambda limit=5_000: events)
    monkeypatch.setattr(journal, "read_entries_for_epoch", lambda **kwargs: [
        e for e in events if str((e.get("payload") or {}).get("epoch_id") or "") == kwargs["epoch_id"]
    ])

    legacy = _legacy_reviewer_calibration_service(epoch_id="epoch-7")
    current = reviewer_calibration_service(epoch_id="epoch-7")

    assert current["cohort_summary"] == legacy["cohort_summary"]
    assert current["avg_reputation"] == legacy["avg_reputation"]
    assert current["tier_pressure"] == legacy["tier_pressure"]


def test_reviewer_calibration_equivalent_with_reviewer_selector(monkeypatch) -> None:
    events = _events_fixture()
    monkeypatch.setattr(journal, "read_entries", lambda limit=5_000: events)

    def _read_entries_for_epoch(*, epoch_id: str, reviewer_ids: Iterable[str] | None = None, **_: Any) -> list[dict[str, Any]]:
        selected = []
        selector = {rid.strip() for rid in (reviewer_ids or []) if rid and rid.strip()}
        for entry in events:
            payload = entry.get("payload") if isinstance(entry, dict) else {}
            if str((payload or {}).get("epoch_id") or "") != epoch_id:
                continue
            if selector and str((payload or {}).get("reviewer_id") or "").strip() not in selector:
                continue
            selected.append(entry)
        return selected

    monkeypatch.setattr(journal, "read_entries_for_epoch", _read_entries_for_epoch)

    legacy = _legacy_reviewer_calibration_service(epoch_id="epoch-7", reviewer_ids=["alice"])
    current = reviewer_calibration_service(epoch_id="epoch-7", reviewer_ids=["alice"])

    assert current["cohort_summary"] == legacy["cohort_summary"]
    assert current["avg_reputation"] == legacy["avg_reputation"]
    assert current["tier_pressure"] == legacy["tier_pressure"]
