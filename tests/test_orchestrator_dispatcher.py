from __future__ import annotations

import importlib
import time

from adaad.orchestrator import bootstrap as bootstrap_module
import adaad.orchestrator.dispatcher as dispatcher_module
from adaad.orchestrator.bootstrap import bootstrap_tool_registry
from adaad.orchestrator.dispatcher import Dispatcher, dispatch, dispatch_result_or_raise
from adaad.orchestrator.registry import HandlerRegistry, clear_registry, register_tool


def teardown_function() -> None:
    clear_registry()
    bootstrap_module._BOOTSTRAPPED = False


def test_dispatch_meta_contains_monotonic_latency() -> None:
    register_tool("test.echo", lambda payload: payload)

    envelope = dispatch("test.echo", {"ok": True})

    assert envelope["result"] == {"ok": True}
    meta = envelope["_dispatch_meta"]
    assert meta["tool"] == "test.echo"
    assert isinstance(meta["started_mono_ns"], int)
    assert isinstance(meta["finished_mono_ns"], int)
    assert isinstance(meta["latency_ns"], int)
    assert meta["finished_mono_ns"] >= meta["started_mono_ns"]
    assert meta["latency_ns"] == meta["finished_mono_ns"] - meta["started_mono_ns"]


def test_dispatch_hot_path_avoids_imports_after_bootstrap(monkeypatch) -> None:
    bootstrap_module._BOOTSTRAPPED = False
    clear_registry()
    bootstrap_tool_registry(tool_specs=(("test.noop", "builtins:len"),))

    monkeypatch.setattr(importlib, "import_module", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("import called during dispatch")))

    envelope = dispatch("test.noop", [1, 2, 3])
    assert envelope["result"] == 3
    assert envelope["_dispatch_meta"]["latency_ns"] >= 0


def test_dispatch_structured_error_envelope_for_unknown_route() -> None:
    clear_registry()
    envelope = dispatch("missing.route", {})
    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "route_not_found"
    assert envelope["metadata"]["route"] == "missing.route"


def test_dispatcher_class_error_isolation_and_latency_watchdog() -> None:
    def slow_handler(_payload):
        time.sleep(0.055)
        return {"ok": True}

    dispatcher = Dispatcher(HandlerRegistry.preload({"slow": slow_handler}))
    response = dispatcher.dispatch("slow", None)

    assert response["ok"] is True
    assert response["metadata"]["route"] == "slow"
    assert response["metadata"]["within_target"] is False
    assert response["metadata"]["warning"] == "latency_budget_exceeded"


def test_dispatcher_class_latency_metrics_failure_is_non_fatal(monkeypatch, caplog) -> None:
    class _FailingMetrics:
        @staticmethod
        def log(**_kwargs):
            raise RuntimeError("sink unavailable")

    monkeypatch.setattr("adaad.orchestrator.dispatcher.runtime_metrics", _FailingMetrics)

    def slow_handler(_payload):
        time.sleep(0.055)
        return {"ok": True}

    dispatcher = Dispatcher(HandlerRegistry.preload({"slow": slow_handler}))

    with caplog.at_level("WARNING", logger="adaad.dispatcher"):
        response = dispatcher.dispatch("slow", None)

    assert response["ok"] is True
    assert response["metadata"]["warning"] == "latency_budget_exceeded"
    assert any(record.message == "dispatcher runtime metrics write failed" for record in caplog.records)
    failure_record = next(record for record in caplog.records if record.message == "dispatcher runtime metrics write failed")
    assert failure_record.route == "slow"
    assert failure_record.latency_ms >= 50
    assert "sink unavailable" in failure_record.exception


def test_dispatch_result_or_raise_accepts_result_envelope() -> None:
    assert dispatch_result_or_raise({"result": {"ok": True}}) == {"ok": True}


def test_dispatch_composes_with_dispatch_result_or_raise() -> None:
    register_tool("test.ok", lambda _payload: {"status": "ok", "value": 42})

    envelope = dispatch("test.ok", {})
    result = dispatch_result_or_raise(envelope)

    assert result == {"status": "ok", "value": 42}


def test_dispatch_result_or_raise_fails_closed_for_error_envelope() -> None:
    try:
        dispatch_result_or_raise({"status": "error", "error": {"code": "route_not_found"}})
    except RuntimeError as exc:
        assert str(exc) == "dispatch failed:route_not_found"
    else:
        raise AssertionError("expected RuntimeError")


def test_dispatch_result_or_raise_fails_closed_for_missing_result() -> None:
    try:
        dispatch_result_or_raise({"metadata": {"route": "x"}})
    except RuntimeError as exc:
        assert str(exc) == "dispatch failed:missing_result"
    else:
        raise AssertionError("expected RuntimeError")


def test_dispatch_result_or_raise_fails_closed_for_non_success_result_status() -> None:
    try:
        dispatch_result_or_raise({"result": {"status": "rejected", "error_code": "policy_blocked"}})
    except RuntimeError as exc:
        assert str(exc) == "dispatch failed:policy_blocked"
    else:
        raise AssertionError("expected RuntimeError")


def test_dispatch_result_or_raise_fails_closed_for_invalid_envelope_type() -> None:
    try:
        dispatch_result_or_raise([])  # type: ignore[arg-type]
    except RuntimeError as exc:
        assert str(exc) == "dispatch failed:invalid_envelope"
    else:
        raise AssertionError("expected RuntimeError")


def test_dispatch_result_or_raise_fails_closed_for_invalid_top_level_status() -> None:
    try:
        dispatch_result_or_raise({"status": "pending", "result": {"ok": True}})
    except RuntimeError as exc:
        assert str(exc) == "dispatch failed:invalid_envelope_status"
    else:
        raise AssertionError("expected RuntimeError")


def test_dispatch_latency_budget_defaults_to_50ms_when_env_not_set(monkeypatch) -> None:
    monkeypatch.delenv("ADAAD_DISPATCH_LATENCY_BUDGET_MS", raising=False)
    importlib.reload(dispatcher_module)

    dispatcher = dispatcher_module.Dispatcher(HandlerRegistry.preload({"fast": lambda payload: payload}))
    response = dispatcher.dispatch("fast", {"ok": True})

    assert dispatcher_module.MAX_LATENCY_MS == 50.0
    assert response["metadata"]["latency_target_ms"] == 50.0


def test_dispatch_latency_budget_honors_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_DISPATCH_LATENCY_BUDGET_MS", "75")
    importlib.reload(dispatcher_module)

    dispatcher = dispatcher_module.Dispatcher(HandlerRegistry.preload({"fast": lambda payload: payload}))
    response = dispatcher.dispatch("fast", {"ok": True})

    assert dispatcher_module.MAX_LATENCY_MS == 75.0
    assert response["metadata"]["latency_target_ms"] == 75.0


def test_dispatch_latency_budget_adaptive_mode_respects_replay(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_DISPATCH_LATENCY_BUDGET_MS", "100")
    monkeypatch.setenv("ADAAD_DISPATCH_LATENCY_MODE", "adaptive")
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.delenv("ADAAD_DETERMINISTIC_LOCK", raising=False)
    importlib.reload(dispatcher_module)

    assert dispatcher_module.MAX_LATENCY_MS == 80.0


def test_dispatch_latency_budget_adaptive_mode_disabled_by_deterministic_lock(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_DISPATCH_LATENCY_BUDGET_MS", "100")
    monkeypatch.setenv("ADAAD_DISPATCH_LATENCY_MODE", "adaptive")
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.setenv("ADAAD_DETERMINISTIC_LOCK", "1")
    importlib.reload(dispatcher_module)

    assert dispatcher_module.MAX_LATENCY_MS == 100.0
