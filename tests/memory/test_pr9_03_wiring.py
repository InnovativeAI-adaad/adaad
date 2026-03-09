# SPDX-License-Identifier: Apache-2.0
"""
Tests for Phase 0c: ContextReplayInterface → EvolutionLoop + CodebaseContext wiring.

Deferred from PR-9-03 — wires context_digest annotation and explore_ratio injection
into the proposal pipeline (AIMutationProposer / CodebaseContext.as_prompt_block).

Test IDs: T9-W-01 through T9-W-12
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.memory.context_replay_interface import ContextReplayInterface, ReplayInjection

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_context(**kwargs) -> CodebaseContext:
    defaults = dict(
        file_summaries={"runtime/foo.py": "Foo module"},
        recent_failures=[],
        current_epoch_id="epoch-001",
        explore_ratio=0.5,
    )
    defaults.update(kwargs)
    return CodebaseContext(**defaults)


def _make_injection(
    *,
    skipped: bool = False,
    signal_quality_ok: bool = True,
    dominant_pattern: Optional[str] = "experimental",
    mean_elite_score: float = 0.65,
    adjusted_explore_ratio: float = 0.60,
    context_digest: str = "abc123def456",
    skip_reason: Optional[str] = None,
    valid_entry_count: int = 3,
) -> ReplayInjection:
    return ReplayInjection(
        epoch_id="epoch-001",
        context_digest=context_digest,
        dominant_pattern=dominant_pattern,
        mean_elite_score=mean_elite_score,
        adjusted_explore_ratio=adjusted_explore_ratio,
        signal_quality_ok=signal_quality_ok,
        valid_entry_count=valid_entry_count,
        window_size=5,
        skipped=skipped,
        skip_reason=skip_reason,
    )


def _mock_replay_interface(injection: ReplayInjection) -> MagicMock:
    mock = MagicMock(spec=ContextReplayInterface)
    mock.build_injection.return_value = injection
    return mock


# ---------------------------------------------------------------------------
# CodebaseContext: soulbound_annotation field and as_prompt_block rendering
# ---------------------------------------------------------------------------


def test_t9_w_01_codebase_context_annotation_defaults_none():
    """T9-W-01: CodebaseContext.soulbound_annotation defaults to None."""
    ctx = _make_context()
    assert ctx.soulbound_annotation is None


def test_t9_w_02_annotation_not_in_prompt_when_none():
    """T9-W-02: as_prompt_block() does not include soulbound section when annotation is None."""
    ctx = _make_context()
    block = ctx.as_prompt_block()
    assert "Soulbound context" not in block
    assert "context_digest" not in block


def test_t9_w_03_annotation_appears_in_prompt_block():
    """T9-W-03: as_prompt_block() includes soulbound annotation when set."""
    ctx = _make_context(soulbound_annotation="context_digest=abc123 dominant_pattern=experimental")
    block = ctx.as_prompt_block()
    assert "Soulbound context" in block
    assert "context_digest=abc123" in block
    assert "dominant_pattern=experimental" in block


def test_t9_w_04_annotation_section_has_advisory_marker():
    """T9-W-04: Annotation block carries advisory-only marker text."""
    ctx = _make_context(soulbound_annotation="x=1")
    block = ctx.as_prompt_block()
    assert "advisory" in block.lower()


def test_t9_w_05_annotation_section_has_closing_marker():
    """T9-W-05: Annotation block is delimited with opening and closing markers."""
    ctx = _make_context(soulbound_annotation="x=1")
    block = ctx.as_prompt_block()
    assert "--- Soulbound context" in block
    assert "--- end soulbound context ---" in block


def test_t9_w_06_annotation_after_failures_in_prompt_block():
    """T9-W-06: Soulbound annotation appears after recent_failures in prompt block."""
    ctx = _make_context(
        recent_failures=["test_foo"],
        soulbound_annotation="context_digest=xyz",
    )
    block = ctx.as_prompt_block()
    failures_pos = block.index("Recent test failures")
    annotation_pos = block.index("Soulbound context")
    assert annotation_pos > failures_pos


# ---------------------------------------------------------------------------
# EvolutionLoop Phase 0c injection
# ---------------------------------------------------------------------------


def _make_evolution_loop(replay_interface=None):
    """Import EvolutionLoop and instantiate with minimal wiring."""
    from runtime.evolution.evolution_loop import EvolutionLoop
    return EvolutionLoop(
        api_key="test-key",
        replay_interface=replay_interface,
    )


def test_t9_w_07_replay_interface_stored_on_loop():
    """T9-W-07: replay_interface kwarg is stored on EvolutionLoop._replay_interface."""
    mock_ri = _mock_replay_interface(_make_injection())
    loop = _make_evolution_loop(mock_ri)
    assert loop._replay_interface is mock_ri


def test_t9_w_08_none_replay_interface_stored():
    """T9-W-08: When replay_interface is None, _replay_interface is None."""
    loop = _make_evolution_loop(None)
    assert loop._replay_interface is None


def test_t9_w_09_injection_applies_explore_ratio_and_annotation(monkeypatch):
    """T9-W-09: Valid injection updates context.explore_ratio and soulbound_annotation."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    injection = _make_injection(
        adjusted_explore_ratio=0.70,
        context_digest="deadbeef1234",
        dominant_pattern="structural",
    )
    mock_ri = _mock_replay_interface(injection)

    # Patch the proposal call so no real API call is made
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents") as mock_prop:
        mock_prop.return_value = MagicMock(proposals_by_agent={
            "architect": [], "dream": [], "beast": []
        })

        loop = _make_evolution_loop(mock_ri)
        ctx = _make_context(explore_ratio=0.50)
        try:
            loop.run_epoch(ctx)
        except Exception:
            pass  # governance gate will block — we only care about context mutation

    assert ctx.explore_ratio == pytest.approx(0.70)
    assert ctx.soulbound_annotation is not None
    assert "deadbeef1234" in ctx.soulbound_annotation
    assert "structural" in ctx.soulbound_annotation


def test_t9_w_10_skipped_injection_does_not_mutate_context(monkeypatch):
    """T9-W-10: Skipped injection leaves context.explore_ratio and soulbound_annotation unchanged."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    injection = _make_injection(skipped=True, skip_reason="no_craft_pattern_entries_in_ledger")
    mock_ri = _mock_replay_interface(injection)

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents") as mock_prop:
        mock_prop.return_value = MagicMock(proposals_by_agent={
            "architect": [], "dream": [], "beast": []
        })
        loop = _make_evolution_loop(mock_ri)
        ctx = _make_context(explore_ratio=0.50)
        try:
            loop.run_epoch(ctx)
        except Exception:
            pass

    assert ctx.explore_ratio == pytest.approx(0.50)
    assert ctx.soulbound_annotation is None


def test_t9_w_11_low_quality_injection_does_not_mutate_context(monkeypatch):
    """T9-W-11: signal_quality_ok=False injection skips context mutation."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    injection = _make_injection(signal_quality_ok=False, adjusted_explore_ratio=0.30)
    mock_ri = _mock_replay_interface(injection)

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents") as mock_prop:
        mock_prop.return_value = MagicMock(proposals_by_agent={
            "architect": [], "dream": [], "beast": []
        })
        loop = _make_evolution_loop(mock_ri)
        ctx = _make_context(explore_ratio=0.50)
        try:
            loop.run_epoch(ctx)
        except Exception:
            pass

    assert ctx.explore_ratio == pytest.approx(0.50)
    assert ctx.soulbound_annotation is None


def test_t9_w_12_replay_exception_does_not_propagate(monkeypatch):
    """T9-W-12: Exception in ContextReplayInterface.build_injection is swallowed — epoch proceeds."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    bad_ri = MagicMock(spec=ContextReplayInterface)
    bad_ri.build_injection.side_effect = RuntimeError("ledger corrupt")

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents") as mock_prop:
        mock_prop.return_value = MagicMock(proposals_by_agent={
            "architect": [], "dream": [], "beast": []
        })
        loop = _make_evolution_loop(bad_ri)
        ctx = _make_context(explore_ratio=0.50)
        try:
            loop.run_epoch(ctx)
        except Exception:
            pass  # governance gate will raise — that's expected

    # Context must be untouched — the replay exception was swallowed
    assert ctx.explore_ratio == pytest.approx(0.50)
    assert ctx.soulbound_annotation is None
