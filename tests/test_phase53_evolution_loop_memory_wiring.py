# SPDX-License-Identifier: Apache-2.0
"""
Phase 53 tests — EpochMemoryStore wiring into EvolutionLoop

Tests verify:
- Memory store receives emit() after each run_epoch()
- Learning signal is injected into CodebaseContext.learning_context
- Emit failure never blocks epoch completion (fail-closed)
- Emit correctness: epoch_id, accepted_count, proposal_count, winning_agent
- Cross-epoch accumulation: store grows monotonically over multiple epochs

Test IDs: T53-W01..W12
"""

from __future__ import annotations

import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.autonomy.epoch_memory_store import EpochMemoryStore
from runtime.autonomy.learning_signal_extractor import LearningSignalExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loop_with_tmp_memory():
    """Return (EvolutionLoop, tmp_path) with an isolated EpochMemoryStore."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    tmp_path = Path(path)

    loop = EvolutionLoop(api_key="k", simulate_outcomes=True, market_integrator=None)
    # Replace the auto-provisioned store with our isolated one
    loop._epoch_memory = EpochMemoryStore(path=tmp_path, window_size=50)
    return loop, tmp_path


def _make_ctx(epoch_id: str = "ep-test") -> CodebaseContext:
    return CodebaseContext(
        file_summaries={},
        recent_failures=[],
        current_epoch_id=epoch_id,
    )


def _run_silent(loop, ctx):
    """Run epoch with proposal stage patched to empty list."""
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=[],
    ):
        return loop.run_epoch(ctx)


# ===========================================================================
# T53-W: EvolutionLoop × EpochMemoryStore wiring
# ===========================================================================


class TestEvolutionLoopMemoryWiringT53W:

    def test_T53_W01_store_has_one_entry_after_one_epoch(self):
        """T53-W01: one run_epoch → one entry in EpochMemoryStore."""
        loop, _ = _make_loop_with_tmp_memory()
        ctx = _make_ctx("ep-w01")
        _run_silent(loop, ctx)
        assert len(loop._epoch_memory.window()) == 1

    def test_T53_W02_entry_epoch_id_matches(self):
        """T53-W02: emitted entry epoch_id matches context.current_epoch_id."""
        loop, _ = _make_loop_with_tmp_memory()
        ctx = _make_ctx("ep-w02-specific")
        _run_silent(loop, ctx)
        entry = loop._epoch_memory.head()
        assert entry is not None
        assert entry.epoch_id == "ep-w02-specific"

    def test_T53_W03_entry_proposal_count_zero_when_no_proposals(self):
        """T53-W03: when no proposals, proposal_count == 0 in entry."""
        loop, _ = _make_loop_with_tmp_memory()
        _run_silent(loop, _make_ctx("ep-w03"))
        entry = loop._epoch_memory.head()
        assert entry is not None
        assert entry.proposal_count == 0
        assert entry.accepted_count == 0

    def test_T53_W04_store_grows_over_multiple_epochs(self):
        """T53-W04: 5 epochs → 5 entries in memory store."""
        loop, _ = _make_loop_with_tmp_memory()
        for i in range(5):
            _run_silent(loop, _make_ctx(f"ep-w04-{i:03d}"))
        assert len(loop._epoch_memory.window()) == 5

    def test_T53_W05_chain_valid_after_multiple_epochs(self):
        """T53-W05: hash chain remains valid after 5 epochs."""
        loop, _ = _make_loop_with_tmp_memory()
        for i in range(5):
            _run_silent(loop, _make_ctx(f"ep-w05-{i:03d}"))
        assert loop._epoch_memory.chain_valid()

    def test_T53_W06_emit_failure_does_not_abort_epoch(self):
        """T53-W06: if EpochMemoryStore.emit() raises, run_epoch still returns EpochResult."""
        from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult

        loop, _ = _make_loop_with_tmp_memory()
        # Force emit to raise
        loop._epoch_memory.emit = MagicMock(side_effect=RuntimeError("inject"))

        result = _run_silent(loop, _make_ctx("ep-w06"))
        assert isinstance(result, EpochResult)  # epoch completed normally

    def test_T53_W07_learning_signal_injected_into_context(self):
        """T53-W07: after 3 epochs, 4th epoch has learning_context set on CodebaseContext."""
        loop, _ = _make_loop_with_tmp_memory()

        # Run 3 epochs to build memory
        for i in range(3):
            _run_silent(loop, _make_ctx(f"ep-w07-seed-{i}"))

        # 4th epoch: capture context after learning injection
        captured_ctx = {}

        original_propose = __import__(
            "runtime.evolution.evolution_loop", fromlist=["propose_from_all_agents"]
        ).propose_from_all_agents

        def _capture_and_return(ctx, api_key, **kwargs):
            captured_ctx["learning_context"] = ctx.learning_context
            return []

        with patch(
            "runtime.evolution.evolution_loop.propose_from_all_agents",
            side_effect=_capture_and_return,
        ):
            loop.run_epoch(_make_ctx("ep-w07-final"))

        # After 3 seeded epochs, signal should be non-empty → learning_context set
        assert captured_ctx.get("learning_context") is not None
        assert "ADVISORY" in captured_ctx["learning_context"]

    def test_T53_W08_no_learning_context_on_first_epoch(self):
        """T53-W08: first epoch has no prior memory → learning_context not injected."""
        loop, _ = _make_loop_with_tmp_memory()
        captured_ctx: dict = {}

        def _capture(ctx, api_key, **kwargs):
            captured_ctx["learning_context"] = ctx.learning_context
            return []

        with patch(
            "runtime.evolution.evolution_loop.propose_from_all_agents",
            side_effect=_capture,
        ):
            loop.run_epoch(_make_ctx("ep-w08-first"))

        # No prior epochs → empty signal → learning_context not set
        assert captured_ctx.get("learning_context") is None

    def test_T53_W09_winning_agent_null_when_no_accepted(self):
        """T53-W09: winning_agent is None when no mutations accepted."""
        loop, _ = _make_loop_with_tmp_memory()
        _run_silent(loop, _make_ctx("ep-w09"))
        entry = loop._epoch_memory.head()
        assert entry is not None
        assert entry.winning_agent is None

    def test_T53_W10_extractor_initialized(self):
        """T53-W10: EvolutionLoop has _learning_extractor attribute (LearningSignalExtractor)."""
        from runtime.evolution.evolution_loop import EvolutionLoop
        from runtime.autonomy.learning_signal_extractor import LearningSignalExtractor

        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, market_integrator=None)
        assert hasattr(loop, "_learning_extractor")
        assert isinstance(loop._learning_extractor, LearningSignalExtractor)

    def test_T53_W11_memory_store_initialized(self):
        """T53-W11: EvolutionLoop has _epoch_memory attribute (EpochMemoryStore)."""
        from runtime.evolution.evolution_loop import EvolutionLoop
        from runtime.autonomy.epoch_memory_store import EpochMemoryStore

        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, market_integrator=None)
        assert hasattr(loop, "_epoch_memory")
        assert isinstance(loop._epoch_memory, EpochMemoryStore)

    def test_T53_W12_governance_gate_not_imported_in_memory_modules(self):
        """T53-W12: GovernanceGate is not imported in EpochMemoryStore or LearningSignalExtractor (MEMORY-0 invariant)."""
        import ast, inspect
        from runtime.autonomy import epoch_memory_store, learning_signal_extractor

        for mod in (epoch_memory_store, learning_signal_extractor):
            src = inspect.getsource(mod)
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom):
                        assert "GovernanceGate" not in (node.module or ""), \
                            f"GovernanceGate referenced in {mod.__name__} imports"
                    for alias in node.names:
                        assert "GovernanceGate" not in alias.name, \
                            f"GovernanceGate referenced in {mod.__name__} imports"
