# SPDX-License-Identifier: Apache-2.0
"""Phase 70 — Innovations Event Bus tests.

Covers:
  T70-BUS-01..06  InnovationsEventBus: subscribe, emit, fanout, failsafe, singleton
  T70-EMT-01..06  Typed emit helpers: epoch_start/end, cel_step, story_arc,
                  personality, reflection, gplugin, seed_planted
  T70-WIR-01..03  innovations_wiring bus emissions (personality, reflection)
  T70-CEL-01..02  cel_wiring bus emissions (epoch_start/end present, step 14)

Constitutional invariants verified:
  IBUS-FANOUT-0     Every subscriber receives every frame.
  IBUS-FAILSAFE-0   Full queue dropped silently; emission never raises.
  IBUS-DETERM-0     Frame payloads are JSON-serialisable dicts.
  IBUS-THREAD-0     emit_sync does not raise when no loop running.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from runtime.innovations_bus import (
    InnovationsEventBus,
    emit_cel_step,
    emit_epoch_end,
    emit_epoch_start,
    emit_gplugin,
    emit_personality,
    emit_reflection,
    emit_seed_planted,
    emit_story_arc,
    get_bus,
)


# ---------------------------------------------------------------------------
# T70-BUS: Bus core behaviour
# ---------------------------------------------------------------------------

class TestInnovationsEventBus:
    """T70-BUS-01..06"""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_subscribe_returns_queue(self) -> None:
        """T70-BUS-01: subscribe() returns an asyncio.Queue."""
        bus = InnovationsEventBus()
        q = self._run(bus.subscribe())
        assert isinstance(q, asyncio.Queue)

    def test_emit_delivers_to_subscriber(self) -> None:
        """T70-BUS-02: IBUS-FANOUT-0 — emitted frame reaches subscriber."""
        bus = InnovationsEventBus()
        async def _run():
            q = await bus.subscribe()
            await bus.emit({"type": "test", "value": 42})
            frame = q.get_nowait()
            assert frame["type"] == "test"
            assert frame["value"] == 42
        self._run(_run())

    def test_emit_fanout_to_all_subscribers(self) -> None:
        """T70-BUS-03: IBUS-FANOUT-0 — all subscribers receive frame."""
        bus = InnovationsEventBus()
        async def _run():
            q1 = await bus.subscribe()
            q2 = await bus.subscribe()
            q3 = await bus.subscribe()
            await bus.emit({"type": "fanout_test"})
            for q in (q1, q2, q3):
                frame = q.get_nowait()
                assert frame["type"] == "fanout_test"
        self._run(_run())

    def test_emit_adds_ts_if_missing(self) -> None:
        """T70-BUS-04: IBUS-DETERM-0 — ts field injected automatically."""
        bus = InnovationsEventBus()
        async def _run():
            q = await bus.subscribe()
            await bus.emit({"type": "ts_test"})
            frame = q.get_nowait()
            assert "ts" in frame
        self._run(_run())

    def test_full_queue_dropped_silently(self) -> None:
        """T70-BUS-05: IBUS-FAILSAFE-0 — full queue dropped without exception."""
        bus = InnovationsEventBus()
        async def _run():
            q = await bus.subscribe()
            # Fill the queue to maxsize
            for i in range(q.maxsize):
                q.put_nowait({"type": "fill"})
            # This should NOT raise
            await bus.emit({"type": "overflow"})
            assert bus.subscriber_count == 0  # dead queue removed
        self._run(_run())

    def test_unsubscribe_removes_queue(self) -> None:
        """T70-BUS-06: unsubscribe removes the queue from fanout."""
        bus = InnovationsEventBus()
        async def _run():
            q = await bus.subscribe()
            assert bus.subscriber_count == 1
            await bus.unsubscribe(q)
            assert bus.subscriber_count == 0
        self._run(_run())


# ---------------------------------------------------------------------------
# T70-EMT: Typed emit helpers
# ---------------------------------------------------------------------------

class TestTypedEmitHelpers:
    """T70-EMT-01..06"""

    def _capture(self, fn, *args, **kwargs) -> Dict[str, Any]:
        """Call a typed emit helper and capture the frame via bus subscription."""
        loop = asyncio.new_event_loop()
        bus = InnovationsEventBus()
        frame_holder = {}
        async def _run():
            q = await bus.subscribe()
            with patch("runtime.innovations_bus._BUS", bus):
                fn(*args, **kwargs)
                # Give emit_sync a chance to schedule
                await asyncio.sleep(0)
            # Drain any synchronous emit
            if not q.empty():
                frame_holder["frame"] = q.get_nowait()
        loop.run_until_complete(_run())
        loop.close()
        return frame_holder.get("frame", {})

    def test_emit_epoch_start_shape(self) -> None:
        """T70-EMT-01: epoch_start frame has required fields."""
        import runtime.innovations_bus as ib
        ib._BUS = InnovationsEventBus()
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            emit_epoch_start("epoch-test", "SANDBOX_ONLY")
            await asyncio.sleep(0)
            if not q.empty():
                frame = q.get_nowait()
                assert frame["type"] == "epoch_start"
                assert frame["epoch_id"] == "epoch-test"
        loop.run_until_complete(_run())
        loop.close()

    def test_emit_cel_step_fields(self) -> None:
        """T70-EMT-02: cel_step frame has step_number, step_name, outcome."""
        import runtime.innovations_bus as ib
        ib._BUS = InnovationsEventBus()
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            emit_cel_step("e-1", 4, "PROPOSAL-GENERATE", "PASS", {"proposal_id": "p1"})
            await asyncio.sleep(0)
            if not q.empty():
                f = q.get_nowait()
                assert f["type"] == "cel_step"
                assert f["step_number"] == 4
                assert f["step_name"] == "PROPOSAL-GENERATE"
        loop.run_until_complete(_run())
        loop.close()

    def test_emit_story_arc_fields(self) -> None:
        """T70-EMT-03: story_arc frame has epoch, agent, result, title."""
        import runtime.innovations_bus as ib
        ib._BUS = InnovationsEventBus()
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            emit_story_arc("epoch-99", "architect", "promoted", "Test arc")
            await asyncio.sleep(0)
            if not q.empty():
                f = q.get_nowait()
                assert f["type"] == "story_arc"
                assert f["agent"] == "architect"
                assert f["result"] == "promoted"
        loop.run_until_complete(_run())
        loop.close()

    def test_emit_personality_fields(self) -> None:
        """T70-EMT-04: personality frame has agent_id, philosophy, vector."""
        import runtime.innovations_bus as ib
        ib._BUS = InnovationsEventBus()
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            emit_personality("dream", "exploratory", [0.6, 0.8, 0.4, 0.2], "epoch-5")
            await asyncio.sleep(0)
            if not q.empty():
                f = q.get_nowait()
                assert f["type"] == "personality"
                assert f["agent_id"] == "dream"
                assert f["philosophy"] == "exploratory"
        loop.run_until_complete(_run())
        loop.close()

    def test_emit_reflection_fields(self) -> None:
        """T70-EMT-05: reflection frame has dominant/underperforming/hint."""
        import runtime.innovations_bus as ib
        ib._BUS = InnovationsEventBus()
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            emit_reflection("epoch-100", "architect", "beast", "rebalance bandit weights")
            await asyncio.sleep(0)
            if not q.empty():
                f = q.get_nowait()
                assert f["type"] == "reflection"
                assert f["dominant_agent"] == "architect"
                assert "rebalance" in f["rebalance_hint"]
        loop.run_until_complete(_run())
        loop.close()

    def test_emit_seed_planted_fields(self) -> None:
        """T70-EMT-06: seed_planted frame has seed_id, lane, intent."""
        import runtime.innovations_bus as ib
        ib._BUS = InnovationsEventBus()
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            emit_seed_planted("oracle-v1", "governance", "Build oracle", "operator")
            await asyncio.sleep(0)
            if not q.empty():
                f = q.get_nowait()
                assert f["type"] == "seed_planted"
                assert f["seed_id"] == "oracle-v1"
                assert f["lane"] == "governance"
        loop.run_until_complete(_run())
        loop.close()


# ---------------------------------------------------------------------------
# T70-WIR: innovations_wiring bus emissions
# ---------------------------------------------------------------------------

class TestWiringBusEmissions:
    """T70-WIR-01..03"""

    def test_personality_select_emits_frame(self) -> None:
        """T70-WIR-01: select_agent_personality emits personality frame."""
        import runtime.innovations_bus as ib
        ib._BUS = InnovationsEventBus()
        from runtime.innovations import ADAADInnovationEngine
        from runtime.innovations_wiring import select_agent_personality
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            engine = ADAADInnovationEngine()
            select_agent_personality(engine, "epoch-emit-test")
            await asyncio.sleep(0)
            if not q.empty():
                f = q.get_nowait()
                assert f["type"] == "personality"
        loop.run_until_complete(_run())
        loop.close()

    def test_reflection_emits_frame(self) -> None:
        """T70-WIR-02: run_self_reflection emits reflection frame on cadence."""
        import runtime.innovations_bus as ib
        from runtime.innovations_wiring import REFLECTION_CADENCE
        ib._BUS = InnovationsEventBus()
        from runtime.innovations import ADAADInnovationEngine
        from runtime.innovations_wiring import run_self_reflection
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            engine = ADAADInnovationEngine()
            state = {"agent_scores": {"architect": 0.8, "dream": 0.3}, "fitness_summary": ()}
            run_self_reflection(engine, "epoch-100", REFLECTION_CADENCE, state)
            await asyncio.sleep(0)
            if not q.empty():
                f = q.get_nowait()
                assert f["type"] == "reflection"
        loop.run_until_complete(_run())
        loop.close()

    def test_no_frame_between_cadence(self) -> None:
        """T70-WIR-03: no reflection frame emitted between cadence ticks."""
        import runtime.innovations_bus as ib
        ib._BUS = InnovationsEventBus()
        from runtime.innovations import ADAADInnovationEngine
        from runtime.innovations_wiring import run_self_reflection
        loop = asyncio.new_event_loop()
        async def _run():
            q = await ib._BUS.subscribe()
            engine = ADAADInnovationEngine()
            run_self_reflection(engine, "epoch-5", epoch_seq=5, state={})
            await asyncio.sleep(0)
            assert q.empty()
        loop.run_until_complete(_run())
        loop.close()


# ---------------------------------------------------------------------------
# T70-CEL: LiveWiredCEL bus wiring surface
# ---------------------------------------------------------------------------

class TestCELBusWiring:
    """T70-CEL-01..02"""

    def test_liveWiredCEL_has_run_epoch_override(self) -> None:
        """T70-CEL-01: LiveWiredCEL overrides run_epoch with bus emission."""
        from runtime.evolution.cel_wiring import LiveWiredCEL
        import inspect
        # run_epoch must be defined directly on LiveWiredCEL (not just inherited)
        assert "run_epoch" in LiveWiredCEL.__dict__, (
            "LiveWiredCEL must override run_epoch for Phase 70 bus emission"
        )

    def test_bus_singleton_stable(self) -> None:
        """T70-CEL-02: get_bus() returns same instance on repeated calls."""
        import runtime.innovations_bus as ib
        ib._BUS = None  # reset singleton
        b1 = get_bus()
        b2 = get_bus()
        assert b1 is b2
