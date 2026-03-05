# SPDX-License-Identifier: Apache-2.0
"""Tests for MarketDrivenContainerProfiler — ADAAD-14 PR-14-03.

Coverage
--------
- TestProfileSelection         (5 tests) — profile_dict, journal_event, tiers
- TestProfilerTierSelection    (7 tests) — constrained/standard/burst thresholds, confidence guard
- TestProfilerFallback         (4 tests) — provider error, zero confidence, custom thresholds
- TestProfilerFactory          (2 tests) — make_profiler_from_feed_registry, federated_broker
- TestProfileSummary           (2 tests) — no selection, post-selection summary
"""
from __future__ import annotations

import time
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, call

from runtime.sandbox.market_driven_profiler import (
    ContainerProfileTier,
    MarketDrivenContainerProfiler,
    ProfileSelection,
    PROFILE_DEFINITIONS,
    _CONSTRAINED_THRESHOLD,
    _BURST_THRESHOLD,
    _MIN_CONFIDENCE_FOR_OVERRIDE,
    make_profiler_from_feed_registry,
    make_profiler_from_federated_broker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provider(score: float, confidence: float):
    return lambda: (score, confidence)


def _profiler(score: float, confidence: float = 0.9, journal_fn=None, **kwargs):
    return MarketDrivenContainerProfiler(
        score_provider=_provider(score, confidence),
        journal_fn=journal_fn,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# TestProfileSelection
# ---------------------------------------------------------------------------

class TestProfileSelection(unittest.TestCase):

    def _selection(self, tier=ContainerProfileTier.STANDARD) -> ProfileSelection:
        return ProfileSelection(
            tier=tier, market_score=0.5, market_confidence=0.9,
            rationale="test", selected_at=time.time(),
            lineage_digest="sha256:abc", overridden=False,
        )

    def test_profile_dict_contains_cpu_quota(self):
        sel = self._selection(ContainerProfileTier.STANDARD)
        d = sel.profile_dict()
        self.assertIn("cpu_quota_percent", d)
        self.assertEqual(d["cpu_quota_percent"], 50)

    def test_constrained_profile_has_lower_cpu_than_standard(self):
        c = PROFILE_DEFINITIONS[ContainerProfileTier.CONSTRAINED]
        s = PROFILE_DEFINITIONS[ContainerProfileTier.STANDARD]
        self.assertLess(c["cpu_quota_percent"], s["cpu_quota_percent"])

    def test_burst_profile_has_higher_mem_than_standard(self):
        b = PROFILE_DEFINITIONS[ContainerProfileTier.BURST]
        s = PROFILE_DEFINITIONS[ContainerProfileTier.STANDARD]
        self.assertGreater(b["memory_limit_mb"], s["memory_limit_mb"])

    def test_journal_event_contains_tier(self):
        sel = self._selection(ContainerProfileTier.BURST)
        event = sel.to_journal_event()
        self.assertEqual(event["tier"], "burst")
        self.assertEqual(event["event_type"], "container_profile_selected.v1")

    def test_journal_event_contains_lineage_digest(self):
        sel = self._selection()
        event = sel.to_journal_event()
        self.assertTrue(event["lineage_digest"].startswith("sha256:"))


# ---------------------------------------------------------------------------
# TestProfilerTierSelection
# ---------------------------------------------------------------------------

class TestProfilerTierSelection(unittest.TestCase):

    def test_high_score_selects_burst(self):
        p = _profiler(score=0.8)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.BURST)

    def test_low_score_selects_constrained(self):
        p = _profiler(score=0.2)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.CONSTRAINED)

    def test_mid_score_selects_standard(self):
        p = _profiler(score=0.5)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.STANDARD)

    def test_exactly_at_constrained_threshold_uses_standard(self):
        p = _profiler(score=_CONSTRAINED_THRESHOLD)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.STANDARD)

    def test_exactly_at_burst_threshold_selects_burst(self):
        p = _profiler(score=_BURST_THRESHOLD)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.BURST)

    def test_low_confidence_forces_standard(self):
        p = _profiler(score=0.1, confidence=0.1)  # score says constrained but conf too low
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.STANDARD)
        self.assertTrue(sel.overridden)

    def test_high_score_low_confidence_forces_standard(self):
        p = _profiler(score=0.9, confidence=0.05)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.STANDARD)
        self.assertTrue(sel.overridden)


# ---------------------------------------------------------------------------
# TestProfilerFallback
# ---------------------------------------------------------------------------

class TestProfilerFallback(unittest.TestCase):

    def test_provider_exception_returns_standard(self):
        def bad_provider():
            raise RuntimeError("feed down")
        p = MarketDrivenContainerProfiler(score_provider=bad_provider)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.STANDARD)

    def test_zero_confidence_returns_standard(self):
        p = _profiler(score=0.9, confidence=0.0)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.STANDARD)

    def test_custom_thresholds_respected(self):
        p = MarketDrivenContainerProfiler(
            score_provider=_provider(0.7, 0.9),
            constrained_threshold=0.5,
            burst_threshold=0.8,
        )
        # 0.7 is in [0.5, 0.8) → STANDARD with custom thresholds
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.STANDARD)

    def test_profile_for_slot_returns_dict_with_cpu_quota(self):
        p = _profiler(score=0.5)
        profile = p.profile_for_slot(epoch_id="ep-test")
        self.assertIn("cpu_quota_percent", profile)


# ---------------------------------------------------------------------------
# TestProfilerJournal
# ---------------------------------------------------------------------------

class TestProfilerJournal(unittest.TestCase):

    def test_journal_fn_called_on_selection(self):
        journal = MagicMock()
        p = _profiler(score=0.5, journal_fn=journal)
        p.select_profile(epoch_id="ep-1")
        journal.assert_called_once()
        event = journal.call_args[0][0]
        self.assertEqual(event["event_type"], "container_profile_selected.v1")

    def test_journal_fn_error_does_not_raise(self):
        def bad_journal(e):
            raise RuntimeError("journal down")
        p = _profiler(score=0.5, journal_fn=bad_journal)
        sel = p.select_profile()  # Should not raise
        self.assertIsNotNone(sel)


# ---------------------------------------------------------------------------
# TestProfileSummary
# ---------------------------------------------------------------------------

class TestProfileSummary(unittest.TestCase):

    def test_no_selection_returns_status(self):
        p = _profiler(score=0.5)
        summary = p.profile_summary()
        self.assertEqual(summary["status"], "no_selection_yet")

    def test_post_selection_summary_contains_tier(self):
        p = _profiler(score=0.8)
        p.select_profile()
        summary = p.profile_summary()
        self.assertIn("tier", summary)
        self.assertEqual(summary["tier"], "burst")


# ---------------------------------------------------------------------------
# TestProfilerFactory
# ---------------------------------------------------------------------------

class TestProfilerFactory(unittest.TestCase):

    def test_make_profiler_from_feed_registry(self):
        from runtime.market.feed_registry import MarketSignalReading
        import hashlib, json
        reading = MarketSignalReading(
            adapter_id="test", signal_type="composite",
            value=0.72, confidence=0.88, sampled_at=time.time(),
            lineage_digest="sha256:" + hashlib.sha256(b"t").hexdigest(),
            source_uri="test://",
        )
        feed = MagicMock()
        feed.composite_reading.return_value = reading
        p = make_profiler_from_feed_registry(feed)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.BURST)
        self.assertAlmostEqual(sel.market_score, 0.72, places=4)

    def test_make_profiler_from_federated_broker(self):
        broker = MagicMock()
        broker.cluster_composite.return_value = 0.25  # → CONSTRAINED
        broker.alive_peer_count.return_value = 3
        # confidence = min(1.0, 0.5 + 3*0.1) = 0.8 → above min threshold
        p = make_profiler_from_federated_broker(broker)
        sel = p.select_profile()
        self.assertEqual(sel.tier, ContainerProfileTier.CONSTRAINED)


if __name__ == "__main__":
    unittest.main()
