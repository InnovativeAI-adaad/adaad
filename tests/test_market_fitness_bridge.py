# SPDX-License-Identifier: Apache-2.0
"""Phase 46 — MarketSignalAdapter → EconomicFitnessEvaluator Live Bridge

Tests that the live market signal bridge:
  - Injects live adapter score as highest-priority simulated_market_score source.
  - Falls back to payload when adapter is None.
  - Is fail-closed: adapter exceptions fall through to payload/default path.
  - Exposes correct market_bridge_status() diagnostics.
  - Returns 200 from GET /evolution/market-fitness-bridge with expected schema.

Constitutional invariants enforced:
  - ``live_market_adapter=None`` (default) leaves existing evaluation paths unchanged.
  - Adapter score overrides payload ``simulated_market_score`` when adapter is wired.
  - Adapter failure is logged and swallowed; never propagates as an exception.
  - bridge_fetch_count increments on every successful adapter call.
  - bridge_fallback_count increments on every adapter exception.
"""

from __future__ import annotations

import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from runtime.evolution.economic_fitness import EconomicFitnessEvaluator
from runtime.market.market_signal_adapter import MarketSignal, MarketSignalAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(dau: float = 0.80, retention_d7: float = 0.70) -> MarketSignal:
    score = round(dau * 0.55 + retention_d7 * 0.45, 4)
    return MarketSignal(
        dau=dau,
        retention_d7=retention_d7,
        simulated_market_score=score,
        source="live",
        ingested_at=time.time(),
        lineage_digest="sha256:" + "a" * 64,
    )


def _base_payload(**kwargs: Any) -> Dict[str, Any]:
    base = {
        "epoch_id":                "epoch-ph46-test",
        "passed_syntax":           True,
        "passed_tests":            True,
        "passed_constitution":     True,
        "correctness_score":       0.90,
        "efficiency_score":        0.85,
        "policy_compliance_score": 0.95,
        "goal_alignment_score":    0.88,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# T46-01: Default (no adapter) — evaluate() unchanged
# ---------------------------------------------------------------------------

def test_no_adapter_uses_payload_market_score():
    """T46-01: Without adapter, simulated_market_score comes from payload."""
    evaluator = EconomicFitnessEvaluator()
    payload = _base_payload(simulated_market_score=0.77)
    result = evaluator.evaluate(payload)
    assert result.simulated_market_score == pytest.approx(0.77, abs=1e-4)


def test_no_adapter_defaults_to_zero_when_missing():
    """T46-02: Without adapter and no market keys in payload → defaults to 0.0."""
    evaluator = EconomicFitnessEvaluator()
    payload = _base_payload()  # no simulated_market_score key
    result = evaluator.evaluate(payload)
    assert result.simulated_market_score == pytest.approx(0.0, abs=1e-4)


# ---------------------------------------------------------------------------
# T46-03: Live adapter wired — overrides payload score
# ---------------------------------------------------------------------------

def test_live_adapter_overrides_payload_score():
    """T46-03: When adapter is wired, its score takes priority over payload value."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    adapter.fetch.return_value = _make_signal(dau=0.90, retention_d7=0.85)
    expected_score = round(0.90 * 0.55 + 0.85 * 0.45, 4)

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    # Payload has a different market score — adapter should win
    payload = _base_payload(simulated_market_score=0.10)
    result = evaluator.evaluate(payload)
    assert result.simulated_market_score == pytest.approx(expected_score, abs=1e-4)
    adapter.fetch.assert_called_once()


def test_live_adapter_overrides_when_payload_has_no_score():
    """T46-04: Adapter score used even when payload has no simulated_market_score."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    signal = _make_signal(dau=0.60, retention_d7=0.50)
    adapter.fetch.return_value = signal

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    payload = _base_payload()  # no market score key
    result = evaluator.evaluate(payload)
    assert result.simulated_market_score == pytest.approx(signal.simulated_market_score, abs=1e-4)


# ---------------------------------------------------------------------------
# T46-05: Fail-closed — adapter exception falls back silently
# ---------------------------------------------------------------------------

def test_adapter_exception_falls_back_to_payload():
    """T46-05: When adapter.fetch() raises, evaluation falls back to payload score."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    adapter.fetch.side_effect = RuntimeError("network_timeout")

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    payload = _base_payload(simulated_market_score=0.65)
    result = evaluator.evaluate(payload)
    # Should fall back to payload value, not raise
    assert result.simulated_market_score == pytest.approx(0.65, abs=1e-4)
    assert evaluator._bridge_fallback_count == 1


def test_adapter_exception_does_not_propagate():
    """T46-06: Adapter failure never raises from evaluate()."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    adapter.fetch.side_effect = Exception("catastrophic_failure")

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    # Must not raise
    result = evaluator.evaluate(_base_payload())
    assert isinstance(result.simulated_market_score, float)


# ---------------------------------------------------------------------------
# T46-07: Bridge statistics counters
# ---------------------------------------------------------------------------

def test_bridge_fetch_count_increments():
    """T46-07: bridge_fetch_count increments on each successful adapter call."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    adapter.fetch.return_value = _make_signal()

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    assert evaluator._bridge_fetch_count == 0

    evaluator.evaluate(_base_payload())
    evaluator.evaluate(_base_payload())
    assert evaluator._bridge_fetch_count == 2


def test_bridge_fallback_count_increments():
    """T46-08: bridge_fallback_count increments on each adapter exception."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    adapter.fetch.side_effect = RuntimeError("fail")

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    evaluator.evaluate(_base_payload())
    evaluator.evaluate(_base_payload())
    assert evaluator._bridge_fallback_count == 2
    assert evaluator._bridge_fetch_count == 0


# ---------------------------------------------------------------------------
# T46-09: market_bridge_status()
# ---------------------------------------------------------------------------

def test_bridge_status_unwired():
    """T46-09: market_bridge_status() with no adapter returns wired=False."""
    evaluator = EconomicFitnessEvaluator()
    status = evaluator.market_bridge_status()
    assert status["wired"] is False
    assert status["bridge_fetch_count"] == 0
    assert status["bridge_fallback_count"] == 0
    assert status["last_signal"] is None


def test_bridge_status_wired_includes_signal():
    """T46-10: market_bridge_status() with live adapter returns wired=True + signal."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    signal = _make_signal(dau=0.75, retention_d7=0.65)
    adapter.fetch.return_value = signal

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    status = evaluator.market_bridge_status()
    assert status["wired"] is True
    assert status["last_signal"] is not None
    assert status["last_signal"]["dau"] == pytest.approx(0.75, abs=1e-4)
    assert status["last_signal"]["retention_d7"] == pytest.approx(0.65, abs=1e-4)
    assert "lineage_digest" in status["last_signal"]


def test_bridge_status_wired_adapter_error_returns_none_signal():
    """T46-11: market_bridge_status() with failing adapter returns last_signal=None, no raise."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    adapter.fetch.side_effect = RuntimeError("adapter_down")

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    status = evaluator.market_bridge_status()
    assert status["wired"] is True
    assert status["last_signal"] is None


def test_bridge_status_after_evaluations():
    """T46-12: bridge_fetch_count in status reflects previous evaluate() calls."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    adapter.fetch.return_value = _make_signal()

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    evaluator.evaluate(_base_payload())
    evaluator.evaluate(_base_payload())
    status = evaluator.market_bridge_status()
    # 2 from evaluate() + 1 from market_bridge_status() itself
    assert status["bridge_fetch_count"] == 2


# ---------------------------------------------------------------------------
# T46-13: Score clamping — adapter scores outside [0, 1] are clamped
# ---------------------------------------------------------------------------

def test_adapter_score_clamped_above_one():
    """T46-13: Adapter-provided scores > 1.0 are clamped to 1.0."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    oversaturated = _make_signal(dau=1.0, retention_d7=1.0)
    # Force score > 1 by patching the dataclass value
    object.__setattr__(oversaturated, "simulated_market_score", 1.5)
    adapter.fetch.return_value = oversaturated

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    result = evaluator.evaluate(_base_payload())
    assert result.simulated_market_score <= 1.0


def test_adapter_score_clamped_below_zero():
    """T46-14: Adapter-provided scores < 0.0 are clamped to 0.0."""
    adapter = MagicMock(spec=MarketSignalAdapter)
    neg_signal = _make_signal(dau=0.0, retention_d7=0.0)
    object.__setattr__(neg_signal, "simulated_market_score", -0.5)
    adapter.fetch.return_value = neg_signal

    evaluator = EconomicFitnessEvaluator(live_market_adapter=adapter)
    result = evaluator.evaluate(_base_payload())
    assert result.simulated_market_score >= 0.0


# ---------------------------------------------------------------------------
# T46-15: REST endpoint /evolution/market-fitness-bridge
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# T46-15: REST endpoint /evolution/market-fitness-bridge
# ---------------------------------------------------------------------------

_AUTH_TOKEN = "phase46-test-token"
_AUTH_HDR = {"Authorization": f"Bearer {_AUTH_TOKEN}"}


@pytest.fixture()
def test_client(monkeypatch):
    import json as _json
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", _json.dumps({_AUTH_TOKEN: ["audit:read"]}))
    from server import app
    return TestClient(app, raise_server_exceptions=False)


def test_endpoint_returns_200(test_client):
    """T46-15: GET /evolution/market-fitness-bridge returns 200."""
    resp = test_client.get("/evolution/market-fitness-bridge", headers=_AUTH_HDR)
    assert resp.status_code == 200


def test_endpoint_schema(test_client):
    """T46-16: Endpoint response includes ok, bridge, phase fields."""
    resp = test_client.get("/evolution/market-fitness-bridge", headers=_AUTH_HDR)
    body = resp.json()
    assert body["ok"] is True
    assert "bridge" in body
    assert body["phase"] == "46"
    bridge = body["bridge"]
    assert "wired" in bridge
    assert "bridge_fetch_count" in bridge
    assert "bridge_fallback_count" in bridge
    assert "last_signal" in bridge


def test_endpoint_bridge_wired_with_signal(test_client):
    """T46-17: Endpoint reports wired=True and last_signal when adapter is active."""
    resp = test_client.get("/evolution/market-fitness-bridge", headers=_AUTH_HDR)
    body = resp.json()
    # The endpoint creates a synthetic adapter — wired=True, last_signal present
    assert body["bridge"]["wired"] is True
    assert body["bridge"]["last_signal"] is not None


def test_endpoint_unauthorized_returns_401(test_client):
    """T46-18: Endpoint rejects missing/bad auth with 401 or 403."""
    resp = test_client.get("/evolution/market-fitness-bridge")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# T46-19: Synthetic vs live source field
# ---------------------------------------------------------------------------

def test_synthetic_adapter_source_field():
    """T46-19: MarketSignalAdapter with no source_fn reports source='synthetic'."""
    adapter = MarketSignalAdapter()
    signal = adapter.fetch()
    assert signal.source == "synthetic"


def test_live_adapter_source_field():
    """T46-20: MarketSignalAdapter with source_fn reports source='live'."""
    adapter = MarketSignalAdapter(source_fn=lambda: {"dau": 0.70, "retention_d7": 0.60})
    signal = adapter.fetch()
    assert signal.source == "live"
