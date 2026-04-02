# SPDX-License-Identifier: Apache-2.0
"""Phase 102 — INNOV-17: Agent Post-Mortem Interviews (APM)
Tests T102-APM-01 through T102-APM-30.
All tests are Hard-class invariant assertions — zero xfail permitted at merge.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from runtime.innovations30.agent_postmortem import (
    AgentPostMortemSystem,
    AgentReasoningEntry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_system(tmp_path: Path) -> AgentPostMortemSystem:
    return AgentPostMortemSystem(ledger_path=tmp_path / "apm.jsonl")


def _conduct(system: AgentPostMortemSystem, **overrides) -> AgentReasoningEntry:
    defaults = dict(
        agent_id="agent-alpha",
        mutation_id="mut-001",
        epoch_id="epoch-42",
        rejection_reasons=["lineage gap detected"],
        mutation_intent="refactor error handler",
        mutation_strategy="structural_refactor",
    )
    defaults.update(overrides)
    return system.conduct_interview(**defaults)


# ---------------------------------------------------------------------------
# T102-APM-01 — Happy path: conduct_interview returns AgentReasoningEntry
# ---------------------------------------------------------------------------
def test_apm_01_conduct_interview_returns_entry(tmp_path):
    """T102-APM-01: conduct_interview() returns an AgentReasoningEntry."""
    entry = _conduct(_make_system(tmp_path))
    assert isinstance(entry, AgentReasoningEntry)


# ---------------------------------------------------------------------------
# T102-APM-02 — APM-CHAIN-0: entry carries agent_id
# ---------------------------------------------------------------------------
def test_apm_02_entry_carries_agent_id(tmp_path):
    """T102-APM-02: APM-CHAIN-0 — entry.agent_id equals supplied agent_id."""
    entry = _conduct(_make_system(tmp_path), agent_id="agent-beta")
    assert entry.agent_id == "agent-beta"


# ---------------------------------------------------------------------------
# T102-APM-03 — APM-CHAIN-0: entry carries mutation_id
# ---------------------------------------------------------------------------
def test_apm_03_entry_carries_mutation_id(tmp_path):
    """T102-APM-03: APM-CHAIN-0 — entry.mutation_id equals supplied mutation_id."""
    entry = _conduct(_make_system(tmp_path), mutation_id="mut-XYZ")
    assert entry.mutation_id == "mut-XYZ"


# ---------------------------------------------------------------------------
# T102-APM-04 — APM-CHAIN-0: entry carries epoch_id
# ---------------------------------------------------------------------------
def test_apm_04_entry_carries_epoch_id(tmp_path):
    """T102-APM-04: APM-CHAIN-0 — entry.epoch_id equals supplied epoch_id."""
    entry = _conduct(_make_system(tmp_path), epoch_id="epoch-007")
    assert entry.epoch_id == "epoch-007"


# ---------------------------------------------------------------------------
# T102-APM-05 — APM-CHAIN-0: entry carries non-empty rejection_reasons list
# ---------------------------------------------------------------------------
def test_apm_05_entry_carries_rejection_reasons(tmp_path):
    """T102-APM-05: APM-CHAIN-0 — entry.rejection_reasons is a non-empty list."""
    reasons = ["scope too broad", "replay invariant violated"]
    entry = _conduct(_make_system(tmp_path), rejection_reasons=reasons)
    assert isinstance(entry.rejection_reasons, list)
    assert len(entry.rejection_reasons) == 2
    assert "scope too broad" in entry.rejection_reasons


# ---------------------------------------------------------------------------
# T102-APM-06 — APM-CHAIN-0: entry carries entry_digest
# ---------------------------------------------------------------------------
def test_apm_06_entry_carries_digest(tmp_path):
    """T102-APM-06: APM-CHAIN-0 — entry.entry_digest is present and non-empty."""
    entry = _conduct(_make_system(tmp_path))
    assert entry.entry_digest
    assert len(entry.entry_digest) > 0


# ---------------------------------------------------------------------------
# T102-APM-07 — APM-DETERM-0: digest prefix is "sha256:"
# ---------------------------------------------------------------------------
def test_apm_07_digest_has_sha256_prefix(tmp_path):
    """T102-APM-07: APM-DETERM-0 — entry_digest starts with 'sha256:'."""
    entry = _conduct(_make_system(tmp_path))
    assert entry.entry_digest.startswith("sha256:")


# ---------------------------------------------------------------------------
# T102-APM-08 — APM-DETERM-0: digest is 16 hex chars after prefix
# ---------------------------------------------------------------------------
def test_apm_08_digest_length_after_prefix(tmp_path):
    """T102-APM-08: APM-DETERM-0 — digest has exactly 16 hex chars after 'sha256:'."""
    entry = _conduct(_make_system(tmp_path))
    hex_part = entry.entry_digest[len("sha256:"):]
    assert len(hex_part) == 16
    assert all(c in "0123456789abcdef" for c in hex_part)


# ---------------------------------------------------------------------------
# T102-APM-09 — APM-DETERM-0: digest deterministic across 3 independent calls
# ---------------------------------------------------------------------------
def test_apm_09_digest_deterministic_three_calls(tmp_path):
    """T102-APM-09: APM-DETERM-0 — identical inputs produce identical digest (3 calls)."""
    kwargs = dict(agent_id="agent-det", mutation_id="mut-det", epoch_id="ep-1",
                  rejection_reasons=["lineage gap"], mutation_intent="fix",
                  mutation_strategy="safety_hardening")
    s = _make_system(tmp_path)
    d1 = s.conduct_interview(**kwargs).entry_digest
    d2 = s.conduct_interview(**kwargs).entry_digest
    d3 = s.conduct_interview(**kwargs).entry_digest
    assert d1 == d2 == d3


# ---------------------------------------------------------------------------
# T102-APM-10 — APM-DETERM-0: digest matches manual sha256 computation
# ---------------------------------------------------------------------------
def test_apm_10_digest_matches_manual_sha256(tmp_path):
    """T102-APM-10: APM-DETERM-0 — digest equals sha256(agent_id:mutation_id:identified_gap)[:16]."""
    entry = _conduct(_make_system(tmp_path), agent_id="agt", mutation_id="m1",
                     rejection_reasons=["lineage gap detected"])
    # identified_gap maps from "lineage" → "Insufficient lineage chain verification"
    expected_gap = "Insufficient lineage chain verification"
    payload = f"agt:m1:{expected_gap}"
    expected = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]
    assert entry.entry_digest == expected


# ---------------------------------------------------------------------------
# T102-APM-11 — APM-DETERM-0: different inputs produce different digests
# ---------------------------------------------------------------------------
def test_apm_11_different_inputs_different_digest(tmp_path):
    """T102-APM-11: APM-DETERM-0 — distinct inputs yield distinct digests."""
    s = _make_system(tmp_path)
    e1 = s.conduct_interview("a1", "m1", "e1", ["lineage gap"], "intent", "strat")
    e2 = s.conduct_interview("a2", "m2", "e2", ["entropy budget"], "intent", "strat")
    assert e1.entry_digest != e2.entry_digest


# ---------------------------------------------------------------------------
# T102-APM-12 — APM-GAP-0: identified_gap is non-empty string
# ---------------------------------------------------------------------------
def test_apm_12_identified_gap_non_empty(tmp_path):
    """T102-APM-12: APM-GAP-0 — identified_gap is always a non-empty string."""
    entry = _conduct(_make_system(tmp_path))
    assert isinstance(entry.identified_gap, str)
    assert entry.identified_gap.strip()


# ---------------------------------------------------------------------------
# T102-APM-13 — APM-GAP-0: lineage rejection maps to correct gap
# ---------------------------------------------------------------------------
def test_apm_13_lineage_reason_maps_to_gap(tmp_path):
    """T102-APM-13: APM-GAP-0 — 'lineage' in reason maps to lineage gap string."""
    entry = _conduct(_make_system(tmp_path), rejection_reasons=["lineage chain missing"])
    assert "lineage" in entry.identified_gap.lower()


# ---------------------------------------------------------------------------
# T102-APM-14 — APM-GAP-0: entropy rejection maps to correct gap
# ---------------------------------------------------------------------------
def test_apm_14_entropy_reason_maps_to_gap(tmp_path):
    """T102-APM-14: APM-GAP-0 — 'entropy' in reason maps to entropy gap string."""
    entry = _conduct(_make_system(tmp_path), rejection_reasons=["entropy budget exceeded"])
    assert "entropy" in entry.identified_gap.lower()


# ---------------------------------------------------------------------------
# T102-APM-15 — APM-GAP-0: scope rejection maps to correct gap
# ---------------------------------------------------------------------------
def test_apm_15_scope_reason_maps_to_gap(tmp_path):
    """T102-APM-15: APM-GAP-0 — 'scope' in reason maps to scope gap string."""
    entry = _conduct(_make_system(tmp_path), rejection_reasons=["scope exceeded"])
    assert "scope" in entry.identified_gap.lower()


# ---------------------------------------------------------------------------
# T102-APM-16 — APM-GAP-0: ast rejection maps to correct gap
# ---------------------------------------------------------------------------
def test_apm_16_ast_reason_maps_to_gap(tmp_path):
    """T102-APM-16: APM-GAP-0 — 'ast' in reason maps to AST gap string."""
    entry = _conduct(_make_system(tmp_path), rejection_reasons=["ast parse failed"])
    assert "ast" in entry.identified_gap.lower()


# ---------------------------------------------------------------------------
# T102-APM-17 — APM-GAP-0: replay rejection maps to correct gap
# ---------------------------------------------------------------------------
def test_apm_17_replay_reason_maps_to_gap(tmp_path):
    """T102-APM-17: APM-GAP-0 — 'replay' in reason maps to replay gap string."""
    entry = _conduct(_make_system(tmp_path), rejection_reasons=["replay divergence"])
    assert "replay" in entry.identified_gap.lower()


# ---------------------------------------------------------------------------
# T102-APM-18 — APM-GAP-0: unknown reason maps to constitutional rule string
# ---------------------------------------------------------------------------
def test_apm_18_unknown_reason_maps_to_constitutional_gap(tmp_path):
    """T102-APM-18: APM-GAP-0 — unrecognised reason produces 'Constitutional rule violated' gap."""
    entry = _conduct(_make_system(tmp_path), rejection_reasons=["unrecognised-rule-xyz"])
    assert "constitutional rule violated" in entry.identified_gap.lower()


# ---------------------------------------------------------------------------
# T102-APM-19 — APM-GAP-0: multiple reasons combine into gap string
# ---------------------------------------------------------------------------
def test_apm_19_multiple_reasons_combined_in_gap(tmp_path):
    """T102-APM-19: APM-GAP-0 — multiple reasons produce combined gap with '; ' separator."""
    entry = _conduct(_make_system(tmp_path),
                     rejection_reasons=["lineage chain missing", "scope exceeded"])
    assert ";" in entry.identified_gap


# ---------------------------------------------------------------------------
# T102-APM-20 — APM-PERSIST-0: _persist uses Path.open not builtins.open
# ---------------------------------------------------------------------------
@pytest.mark.autonomous_critical
def test_apm_20_persist_uses_path_open(tmp_path):
    """T102-APM-20: APM-PERSIST-0 — _persist() calls Path.open, never builtins.open."""
    from unittest.mock import mock_open as _mock_open
    system = _make_system(tmp_path)
    entry = AgentReasoningEntry(
        agent_id="agt", mutation_id="m1", epoch_id="ep-1",
        rejection_reasons=["lineage gap"],
        agent_self_assessment="test",
        identified_gap="Insufficient lineage chain verification",
        proposed_correction="fix it",
    )
    with patch("runtime.innovations30.agent_postmortem.Path.open",
               _mock_open()) as mocked:
        system._persist(entry)
        mocked.assert_called()


# ---------------------------------------------------------------------------
# T102-APM-21 — APM-PERSIST-0: ledger file created on first write
# ---------------------------------------------------------------------------
def test_apm_21_ledger_file_created_on_first_write(tmp_path):
    """T102-APM-21: APM-PERSIST-0 — ledger file is created after first conduct_interview."""
    system = _make_system(tmp_path)
    assert not system.ledger_path.exists()
    _conduct(system)
    assert system.ledger_path.exists()


# ---------------------------------------------------------------------------
# T102-APM-22 — APM-PERSIST-0: ledger is append-only JSONL
# ---------------------------------------------------------------------------
def test_apm_22_ledger_is_append_only_jsonl(tmp_path):
    """T102-APM-22: APM-PERSIST-0 — each interview appends a valid JSON line."""
    system = _make_system(tmp_path)
    _conduct(system, agent_id="a1", mutation_id="m1")
    _conduct(system, agent_id="a2", mutation_id="m2")
    lines = system.ledger_path.read_text().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert "agent_id" in record
        assert "entry_digest" in record


# ---------------------------------------------------------------------------
# T102-APM-23 — APM-LOAD-0: agent_recurring_gaps returns empty on missing ledger
# ---------------------------------------------------------------------------
@pytest.mark.autonomous_critical
def test_apm_23_recurring_gaps_empty_on_missing_ledger(tmp_path):
    """T102-APM-23: APM-LOAD-0 — agent_recurring_gaps() returns {} when ledger absent."""
    system = AgentPostMortemSystem(ledger_path=tmp_path / "nonexistent.jsonl")
    result = system.agent_recurring_gaps("agent-x")
    assert result == {}


# ---------------------------------------------------------------------------
# T102-APM-24 — APM-LOAD-0: agent_recurring_gaps does not raise on corrupt ledger
# ---------------------------------------------------------------------------
@pytest.mark.autonomous_critical
def test_apm_24_recurring_gaps_fail_open_on_corrupt_ledger(tmp_path):
    """T102-APM-24: APM-LOAD-0 — agent_recurring_gaps() silently skips corrupt lines."""
    ledger = tmp_path / "apm.jsonl"
    ledger.write_text("not-json\n{\"agent_id\": \"a\", \"identified_gap\": \"gap-x\"}\n")
    system = AgentPostMortemSystem(ledger_path=ledger)
    result = system.agent_recurring_gaps("a")
    assert isinstance(result, dict)
    assert "gap-x" in result


# ---------------------------------------------------------------------------
# T102-APM-25 — APM-LOAD-0: agent_recurring_gaps counts gaps correctly
# ---------------------------------------------------------------------------
def test_apm_25_recurring_gaps_counts_correctly(tmp_path):
    """T102-APM-25: APM-LOAD-0 — agent_recurring_gaps frequency counts are accurate."""
    system = _make_system(tmp_path)
    for _ in range(3):
        _conduct(system, agent_id="agt-a", rejection_reasons=["lineage gap detected"])
    _conduct(system, agent_id="agt-a", rejection_reasons=["entropy budget exceeded"])
    gaps = system.agent_recurring_gaps("agt-a")
    assert isinstance(gaps, dict)
    assert len(gaps) >= 1
    top_gap = next(iter(gaps))
    assert gaps[top_gap] >= 3


# ---------------------------------------------------------------------------
# T102-APM-26 — APM-LOAD-0: agent_recurring_gaps filters by agent_id
# ---------------------------------------------------------------------------
def test_apm_26_recurring_gaps_filters_by_agent(tmp_path):
    """T102-APM-26: APM-LOAD-0 — agent_recurring_gaps only counts entries for target agent."""
    system = _make_system(tmp_path)
    _conduct(system, agent_id="target", rejection_reasons=["lineage gap detected"])
    _conduct(system, agent_id="other", rejection_reasons=["entropy budget exceeded"])
    gaps = system.agent_recurring_gaps("target")
    # other agent's gaps must not appear
    for gap in gaps:
        assert "entropy" not in gap.lower()


# ---------------------------------------------------------------------------
# T102-APM-27 — APM-LOAD-0: agent_recurring_gaps returns {} for unknown agent
# ---------------------------------------------------------------------------
def test_apm_27_recurring_gaps_empty_for_unknown_agent(tmp_path):
    """T102-APM-27: APM-LOAD-0 — agent_recurring_gaps returns {} for an agent with no records."""
    system = _make_system(tmp_path)
    _conduct(system, agent_id="known-agent")
    gaps = system.agent_recurring_gaps("unknown-agent")
    assert gaps == {}


# ---------------------------------------------------------------------------
# T102-APM-28 — APM-0: self_assessment field populated from intent + strategy
# ---------------------------------------------------------------------------
def test_apm_28_self_assessment_references_intent(tmp_path):
    """T102-APM-28: APM-0 — self_assessment contains mutation intent string."""
    entry = _conduct(_make_system(tmp_path), mutation_intent="unique-intent-XYZ")
    assert "unique-intent-XYZ" in entry.agent_self_assessment


# ---------------------------------------------------------------------------
# T102-APM-29 — APM-0: proposed_correction is non-empty string
# ---------------------------------------------------------------------------
def test_apm_29_proposed_correction_non_empty(tmp_path):
    """T102-APM-29: APM-0 — proposed_correction is a non-empty string."""
    entry = _conduct(_make_system(tmp_path))
    assert isinstance(entry.proposed_correction, str)
    assert entry.proposed_correction.strip()


# ---------------------------------------------------------------------------
# T102-APM-30 — Full round-trip: ledger persists and gaps recoverable
# ---------------------------------------------------------------------------
@pytest.mark.autonomous_critical
def test_apm_30_full_roundtrip_ledger_and_gaps(tmp_path):
    """T102-APM-30: Full round-trip — entries persisted, agent_recurring_gaps recoverable."""
    system = _make_system(tmp_path)
    for _ in range(5):
        _conduct(system, agent_id="rnd-agent",
                 rejection_reasons=["replay divergence"])

    # Re-instantiate to verify persistence is durable
    system2 = AgentPostMortemSystem(ledger_path=system.ledger_path)
    gaps = system2.agent_recurring_gaps("rnd-agent")
    assert isinstance(gaps, dict)
    assert len(gaps) >= 1
    top_count = next(iter(gaps.values()))
    assert top_count == 5
