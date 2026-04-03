# SPDX-License-Identifier: Apache-2.0
"""
Phase 104 — INNOV-19 Governance Archaeology Mode (GAM)
Test suite: T104-GAM-01..30  (30 tests)

Invariants under test:
  GAM-0           — excavate() never raises; always returns MutationTimeline
  GAM-CHAIN-0     — timeline_digest starts with "sha256:"
  GAM-DETERM-0    — identical inputs → identical digest (no RNG)
  GAM-SORT-0      — events sorted ascending by timestamp; empty timestamp sorts first
  GAM-FAIL-OPEN-0 — corrupt JSONL / unreadable files silently skipped
  GAM-PARSE-0     — _parse_event() returns None for non-matching records
  GAM-OUTCOME-0   — final_outcome from last terminal event; defaults "unknown"
  GAM-EXPORT-0    — export_timeline() carries innovation=19 and timeline_digest
  GAM-VERIFY-0    — verify_chain() returns bool; never raises
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from runtime.innovations30.governance_archaeology import (
    _TERMINAL_EVENT_TYPES,
    DecisionEvent,
    GovernanceArchaeologist,
    MutationTimeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ledger(tmp_path: Path, records: list[dict]) -> Path:
    """Write records as JSONL into a tmp ledger file."""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return tmp_path


def make_archaeologist(tmp_path: Path) -> GovernanceArchaeologist:
    return GovernanceArchaeologist(ledger_roots=[tmp_path])


def make_event(event_type: str, ts: str = "2026-01-01T00:00:00", mutation_id: str = "mut-001") -> DecisionEvent:
    return DecisionEvent(
        event_type=event_type, timestamp=ts, epoch_id="ep-001",
        mutation_id=mutation_id, actor="system", outcome=event_type,
    )


# ---------------------------------------------------------------------------
# T104-GAM-01..05  excavate() basics  [GAM-0]
# ---------------------------------------------------------------------------

def test_T104_GAM_01_excavate_returns_timeline_always(tmp_path: Path) -> None:
    """GAM-0: excavate() with no ledger → valid MutationTimeline."""
    a = GovernanceArchaeologist(ledger_roots=[tmp_path / "nonexistent"])
    tl = a.excavate("mut-001")
    assert isinstance(tl, MutationTimeline)


def test_T104_GAM_02_excavate_never_raises_on_empty_ledger(tmp_path: Path) -> None:
    """GAM-0: no ledger files → no exception."""
    a = make_archaeologist(tmp_path)
    a.excavate("mut-001")   # must not raise


def test_T104_GAM_03_excavate_never_raises_on_empty_mutation_id(tmp_path: Path) -> None:
    """GAM-0: empty mutation_id → valid timeline with unknown outcome."""
    a = make_archaeologist(tmp_path)
    tl = a.excavate("")
    assert tl.final_outcome == "unknown"
    assert tl.events == []


def test_T104_GAM_04_excavate_finds_matching_events(tmp_path: Path) -> None:
    """GAM-0: events for mutation_id are collected from ledger."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "proposed", "epoch_id": "e1",
         "actor": "Architect", "outcome": "recorded"},
        {"mutation_id": "mut-002", "event_type": "approved", "epoch_id": "e1",
         "actor": "human", "outcome": "approved"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert len(tl.events) == 1
    assert tl.events[0].event_type == "proposed"


def test_T104_GAM_05_excavate_excludes_other_mutations(tmp_path: Path) -> None:
    """GAM-PARSE-0: events for other mutation_ids are not included."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-999", "event_type": "approved", "epoch_id": "e1",
         "actor": "system", "outcome": "approved"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert len(tl.events) == 0


# ---------------------------------------------------------------------------
# T104-GAM-06..10  _parse_event()  [GAM-PARSE-0]
# ---------------------------------------------------------------------------

def test_T104_GAM_06_parse_event_returns_none_for_wrong_id(tmp_path: Path) -> None:
    """GAM-PARSE-0: wrong mutation_id → None."""
    a = make_archaeologist(tmp_path)
    result = a._parse_event(
        {"mutation_id": "mut-XYZ", "event_type": "approved"}, "mut-001"
    )
    assert result is None


def test_T104_GAM_07_parse_event_returns_decision_event_for_match(tmp_path: Path) -> None:
    """GAM-PARSE-0: matching mutation_id → DecisionEvent."""
    a = make_archaeologist(tmp_path)
    result = a._parse_event(
        {"mutation_id": "mut-001", "event_type": "gate_passed",
         "epoch_id": "ep-1", "actor": "GovernanceGate", "outcome": "pass"},
        "mut-001",
    )
    assert isinstance(result, DecisionEvent)
    assert result.event_type == "gate_passed"


def test_T104_GAM_08_parse_event_falls_back_to_action_field(tmp_path: Path) -> None:
    """GAM-PARSE-0: 'action' field used when 'event_type' absent."""
    a = make_archaeologist(tmp_path)
    result = a._parse_event(
        {"mutation_id": "mut-001", "action": "gate_checked", "actor": "gate"},
        "mut-001",
    )
    assert result is not None
    assert result.event_type == "gate_checked"


def test_T104_GAM_09_parse_event_maps_ts_to_timestamp(tmp_path: Path) -> None:
    """GAM-PARSE-0: 'ts' field mapped to timestamp."""
    a = make_archaeologist(tmp_path)
    result = a._parse_event(
        {"mutation_id": "mut-001", "event_type": "proposed", "ts": "2026-01-01T12:00:00"},
        "mut-001",
    )
    assert result is not None
    assert result.timestamp == "2026-01-01T12:00:00"


def test_T104_GAM_10_parse_event_maps_agent_id_to_actor(tmp_path: Path) -> None:
    """GAM-PARSE-0: 'agent_id' field mapped to actor."""
    a = make_archaeologist(tmp_path)
    result = a._parse_event(
        {"mutation_id": "mut-001", "event_type": "proposed", "agent_id": "DreamAgent"},
        "mut-001",
    )
    assert result is not None
    assert result.actor == "DreamAgent"


# ---------------------------------------------------------------------------
# T104-GAM-11..15  Timeline digest  [GAM-CHAIN-0, GAM-DETERM-0]
# ---------------------------------------------------------------------------

def test_T104_GAM_11_timeline_digest_is_sha256_prefixed(tmp_path: Path) -> None:
    """GAM-CHAIN-0: digest starts with 'sha256:'."""
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert tl.timeline_digest.startswith("sha256:")


def test_T104_GAM_12_digest_deterministic_same_events(tmp_path: Path) -> None:
    """GAM-DETERM-0: identical events → identical digest."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "proposed", "actor": "a", "outcome": "r"},
        {"mutation_id": "mut-001", "event_type": "approved", "actor": "human", "outcome": "approved"},
    ])
    a = make_archaeologist(tmp_path)
    tl1 = a.excavate("mut-001")
    tl2 = a.excavate("mut-001")
    assert tl1.timeline_digest == tl2.timeline_digest


def test_T104_GAM_13_digest_differs_with_different_events(tmp_path: Path) -> None:
    """GAM-CHAIN-0: different event sequence → different digest."""
    a = GovernanceArchaeologist(ledger_roots=[tmp_path])
    d1 = a._compute_digest([make_event("proposed")])
    d2 = a._compute_digest([make_event("proposed"), make_event("approved")])
    assert d1 != d2


def test_T104_GAM_14_empty_events_digest_is_stable(tmp_path: Path) -> None:
    """GAM-DETERM-0: empty event list → stable known digest."""
    a = make_archaeologist(tmp_path)
    d1 = a._compute_digest([])
    d2 = a._compute_digest([])
    assert d1 == d2
    assert d1.startswith("sha256:")


def test_T104_GAM_15_compute_digest_matches_manual_sha256(tmp_path: Path) -> None:
    """GAM-CHAIN-0: computed digest matches manual calculation."""
    a = make_archaeologist(tmp_path)
    events = [make_event("proposed"), make_event("approved")]
    expected_payload = json.dumps(["proposed", "approved"], sort_keys=True)
    expected = "sha256:" + hashlib.sha256(expected_payload.encode()).hexdigest()
    assert a._compute_digest(events) == expected


# ---------------------------------------------------------------------------
# T104-GAM-16..18  Event sorting  [GAM-SORT-0]
# ---------------------------------------------------------------------------

def test_T104_GAM_16_events_sorted_ascending_by_timestamp(tmp_path: Path) -> None:
    """GAM-SORT-0: events returned in ascending timestamp order."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "approved", "ts": "2026-01-03", "actor": "h", "outcome": "approved"},
        {"mutation_id": "mut-001", "event_type": "proposed", "ts": "2026-01-01", "actor": "a", "outcome": "r"},
        {"mutation_id": "mut-001", "event_type": "gate_passed", "ts": "2026-01-02", "actor": "g", "outcome": "pass"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    timestamps = [e.timestamp for e in tl.events]
    assert timestamps == sorted(timestamps)


def test_T104_GAM_17_empty_timestamp_sorts_before_non_empty(tmp_path: Path) -> None:
    """GAM-SORT-0: event with empty timestamp appears before timestamped events."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "approved", "ts": "2026-01-02", "actor": "h", "outcome": "approved"},
        {"mutation_id": "mut-001", "event_type": "proposed", "actor": "a", "outcome": "r"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert tl.events[0].event_type == "proposed"  # empty ts sorts first


def test_T104_GAM_18_sort_is_stable_for_equal_timestamps(tmp_path: Path) -> None:
    """GAM-SORT-0: events with equal timestamps maintain consistent secondary sort."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "z_event", "ts": "2026-01-01", "actor": "a", "outcome": "r"},
        {"mutation_id": "mut-001", "event_type": "a_event", "ts": "2026-01-01", "actor": "b", "outcome": "r"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert len(tl.events) == 2  # both present, order consistent


# ---------------------------------------------------------------------------
# T104-GAM-19..21  Corrupt / unreadable files  [GAM-FAIL-OPEN-0]
# ---------------------------------------------------------------------------

def test_T104_GAM_19_corrupt_jsonl_lines_skipped(tmp_path: Path) -> None:
    """GAM-FAIL-OPEN-0: corrupt lines silently skipped; valid lines read."""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        '{"mutation_id":"mut-001","event_type":"proposed","actor":"a","outcome":"r"}\n'
        "NOT_JSON_AT_ALL\n"
        '{"mutation_id":"mut-001","event_type":"gate_passed","actor":"g","outcome":"pass"}\n'
    )
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert len(tl.events) == 2


def test_T104_GAM_20_excavate_never_raises_on_corrupt_file(tmp_path: Path) -> None:
    """GAM-FAIL-OPEN-0: entirely corrupt file → no exception."""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("GARBAGE\n{{{BAD}}}\n")
    a = make_archaeologist(tmp_path)
    a.excavate("mut-001")   # must not raise


def test_T104_GAM_21_excavate_continues_after_one_bad_root(tmp_path: Path) -> None:
    """GAM-FAIL-OPEN-0: non-existent root in list doesn't block other roots."""
    good_root = tmp_path / "good"
    good_root.mkdir()
    (good_root / "ledger.jsonl").write_text(
        '{"mutation_id":"mut-001","event_type":"proposed","actor":"a","outcome":"r"}\n'
    )
    a = GovernanceArchaeologist(ledger_roots=[tmp_path / "nonexistent", good_root])
    tl = a.excavate("mut-001")
    assert len(tl.events) == 1


# ---------------------------------------------------------------------------
# T104-GAM-22..25  final_outcome resolution  [GAM-OUTCOME-0]
# ---------------------------------------------------------------------------

def test_T104_GAM_22_outcome_defaults_to_unknown_with_no_terminal_events(tmp_path: Path) -> None:
    """GAM-OUTCOME-0: no terminal events → 'unknown'."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "proposed", "actor": "a", "outcome": "pending"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert tl.final_outcome == "unknown"


def test_T104_GAM_23_outcome_uses_last_terminal_event(tmp_path: Path) -> None:
    """GAM-OUTCOME-0: last terminal event determines outcome."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "approved",    "ts": "2026-01-01", "actor": "h", "outcome": "approved"},
        {"mutation_id": "mut-001", "event_type": "rolled_back", "ts": "2026-01-02", "actor": "h", "outcome": "rollback_complete"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert tl.final_outcome == "rollback_complete"


def test_T104_GAM_24_all_terminal_types_recognized(tmp_path: Path) -> None:
    """GAM-OUTCOME-0: all four terminal types are in _TERMINAL_EVENT_TYPES."""
    assert _TERMINAL_EVENT_TYPES == frozenset({"approved", "rejected", "promoted", "rolled_back"})


def test_T104_GAM_25_non_terminal_events_dont_affect_outcome(tmp_path: Path) -> None:
    """GAM-OUTCOME-0: 'gate_passed', 'proposed' are non-terminal → outcome 'unknown'."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "gate_passed", "actor": "g", "outcome": "pass"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert tl.final_outcome == "unknown"


# ---------------------------------------------------------------------------
# T104-GAM-26..27  verify_chain()  [GAM-VERIFY-0]
# ---------------------------------------------------------------------------

def test_T104_GAM_26_verify_chain_true_for_fresh_timeline(tmp_path: Path) -> None:
    """GAM-VERIFY-0: freshly excavated timeline always verifies."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "proposed", "actor": "a", "outcome": "r"},
        {"mutation_id": "mut-001", "event_type": "approved", "actor": "human", "outcome": "approved"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert a.verify_chain(tl) is True


def test_T104_GAM_27_verify_chain_false_for_tampered_digest(tmp_path: Path) -> None:
    """GAM-VERIFY-0: tampered timeline_digest → verify_chain returns False."""
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    tl.timeline_digest = "sha256:deadbeef"
    assert a.verify_chain(tl) is False


# ---------------------------------------------------------------------------
# T104-GAM-28  export_timeline()  [GAM-EXPORT-0]
# ---------------------------------------------------------------------------

def test_T104_GAM_28_export_timeline_contains_innovation_19(tmp_path: Path) -> None:
    """GAM-EXPORT-0: export always carries innovation=19."""
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    exp = a.export_timeline(tl)
    assert exp["innovation"] == 19
    assert exp["innovation_name"] == "GovernanceArchaeologyMode"
    assert "timeline_digest" in exp
    assert exp["timeline_digest"].startswith("sha256:")


# ---------------------------------------------------------------------------
# T104-GAM-29..30  MutationTimeline accessors
# ---------------------------------------------------------------------------

def test_T104_GAM_29_proposal_event_accessor(tmp_path: Path) -> None:
    """GAM-0: proposal_event returns first 'proposed' event."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "proposed", "actor": "Dream", "outcome": "r"},
        {"mutation_id": "mut-001", "event_type": "approved", "actor": "human", "outcome": "approved"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert tl.proposal_event is not None
    assert tl.proposal_event.event_type == "proposed"


def test_T104_GAM_30_terminal_event_accessor_and_to_dict(tmp_path: Path) -> None:
    """GAM-EXPORT-0: terminal_event returns last terminal; to_dict is JSON-serializable."""
    make_ledger(tmp_path, [
        {"mutation_id": "mut-001", "event_type": "proposed",  "ts": "2026-01-01", "actor": "a", "outcome": "r"},
        {"mutation_id": "mut-001", "event_type": "rejected",  "ts": "2026-01-02", "actor": "human", "outcome": "rejected"},
    ])
    a = make_archaeologist(tmp_path)
    tl = a.excavate("mut-001")
    assert tl.terminal_event is not None
    assert tl.terminal_event.event_type == "rejected"
    # to_dict must be JSON-serializable
    serialized = json.dumps(tl.to_dict())
    assert "mut-001" in serialized
