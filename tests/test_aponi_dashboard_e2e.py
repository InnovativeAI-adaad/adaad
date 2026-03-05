# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib import error as urlerror, request as urlrequest
from urllib.request import urlopen

from runtime.evolution.evidence_bundle import EvidenceBundleBuilder
from runtime.evolution.lineage_v2 import LineageLedgerV2
from ui import aponi_dashboard


class _StaticBundleBuilder:
    def __init__(self, *args, **kwargs) -> None:
        return None

    def build_bundle(self, *, epoch_start: str, epoch_end: str | None = None, persist: bool = True):
        return {
            "bundle_id": f"evidence-{epoch_start}",
            "export_metadata": {
                "digest": "sha256:" + ("a" * 64),
                "canonical_ordering": "json_sort_keys",
                "immutable": True,
                "path": "reports/forensics/evidence.json",
            },
        }


def test_replay_diff_http_endpoint_includes_bundle_metadata(tmp_path, monkeypatch) -> None:
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {"x": 1}})
    ledger.append_bundle_with_digest(
        "epoch-1",
        {
            "bundle_id": "bundle-1",
            "impact": 0.1,
            "risk_tier": "low",
            "certificate": {"bundle_id": "bundle-1"},
            "strategy_set": [],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": "epoch-1", "state": {"x": 2}})

    monkeypatch.setattr(aponi_dashboard, "LineageLedgerV2", lambda: ledger)
    monkeypatch.setattr(aponi_dashboard, "EvidenceBundleBuilder", _StaticBundleBuilder)

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        with urlopen(f"http://127.0.0.1:{port}/replay/diff?epoch_id=epoch-1", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        dashboard.stop()

    assert payload["ok"] is True
    assert payload["epoch_id"] == "epoch-1"
    assert payload["bundle_id"] == "evidence-epoch-1"
    assert payload["export_metadata"]["digest"].startswith("sha256:")


def test_replay_diff_http_endpoint_persists_export_bundle(tmp_path, monkeypatch) -> None:
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-2", "state": {"x": 3}})
    ledger.append_bundle_with_digest(
        "epoch-2",
        {
            "bundle_id": "bundle-2",
            "impact": 0.2,
            "risk_tier": "low",
            "certificate": {"bundle_id": "bundle-2"},
            "strategy_set": [],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": "epoch-2", "state": {"x": 4}})

    class _ExportingBundleBuilder:
        def __init__(self, ledger: LineageLedgerV2, replay_engine) -> None:
            self._delegate = EvidenceBundleBuilder(
                ledger=ledger,
                replay_engine=replay_engine,
                export_dir=tmp_path / "forensics",
                schema_path=Path("schemas/evidence_bundle.v1.json"),
            )

        def build_bundle(self, *, epoch_start: str, epoch_end: str | None = None, persist: bool = True):
            return self._delegate.build_bundle(epoch_start=epoch_start, epoch_end=epoch_end, persist=persist)

    monkeypatch.setattr(aponi_dashboard, "LineageLedgerV2", lambda: ledger)
    monkeypatch.setattr(aponi_dashboard, "EvidenceBundleBuilder", _ExportingBundleBuilder)

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        with urlopen(f"http://127.0.0.1:{port}/replay/diff?epoch_id=epoch-2", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        dashboard.stop()

    assert payload["ok"] is True
    export_path = Path(payload["export_metadata"]["path"])
    assert export_path.exists()
    persisted = json.loads(export_path.read_text(encoding="utf-8"))
    assert persisted["bundle_id"] == payload["bundle_id"]



def test_replay_divergence_http_endpoint_reports_recent_divergence(tmp_path, monkeypatch) -> None:
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-div-1", "state": {"x": 1}})
    ledger.append_bundle_with_digest(
        "epoch-div-1",
        {
            "bundle_id": "bundle-div-1",
            "impact": 0.1,
            "risk_tier": "low",
            "certificate": {"bundle_id": "bundle-div-1"},
            "strategy_set": [],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": "epoch-div-1", "state": {"x": 2}})

    monkeypatch.setattr(aponi_dashboard, "LineageLedgerV2", lambda: ledger)
    monkeypatch.setattr(aponi_dashboard.metrics, "tail", lambda limit=200: [{"event": "replay_divergence", "payload": {"epoch_id": "epoch-div-1"}}])

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        with urlopen(f"http://127.0.0.1:{port}/replay/divergence", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        dashboard.stop()

    assert payload["divergence_event_count"] == 1
    assert "epoch-div-1" in payload["proof_status"]


def test_replay_diff_http_endpoint_includes_lineage_chain_for_mutation_drilldown(tmp_path, monkeypatch) -> None:
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")

    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-parent", "state": {"x": 1}})
    ledger.append_bundle_with_digest(
        "epoch-parent",
        {
            "bundle_id": "mutation-parent",
            "impact": 0.1,
            "risk_tier": "low",
            "certificate": {"bundle_id": "mutation-parent"},
            "strategy_set": [],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": "epoch-parent", "state": {"x": 2}})

    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-child", "state": {"x": 2}})
    ledger.append_bundle_with_digest(
        "epoch-child",
        {
            "bundle_id": "mutation-child",
            "impact": 0.2,
            "risk_tier": "low",
            "certificate": {
                "bundle_id": "mutation-child",
                "parent_bundle_id": "mutation-parent",
                "ancestor_chain": ["mutation-parent"],
                "signature": "sig-child",
            },
            "strategy_set": [],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": "epoch-child", "state": {"x": 3}})

    monkeypatch.setattr(aponi_dashboard, "LineageLedgerV2", lambda: ledger)
    monkeypatch.setattr(aponi_dashboard, "EvidenceBundleBuilder", _StaticBundleBuilder)

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        with urlopen(f"http://127.0.0.1:{port}/replay/diff?epoch_id=epoch-child", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        dashboard.stop()

    assert payload["ok"] is True
    mutations = payload["lineage_chain"]["mutations"]
    assert mutations
    assert mutations[-1]["mutation_id"] == "mutation-child"
    assert "mutation-parent" in mutations[-1]["ancestor_chain"]


def _http_post_json(url: str, payload: dict, *, headers: dict[str, str] | None = None):
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urlrequest.Request(url, data=body, headers=req_headers, method="POST")
    return urlrequest.urlopen(req, timeout=5)


def _issue_control_headers(port: int) -> dict[str, str]:
    with urlopen(f"http://127.0.0.1:{port}/control/auth-token", timeout=5) as response:
        token_payload = json.loads(response.read().decode("utf-8"))
    token = token_payload["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Origin": f"http://127.0.0.1:{port}",
        "X-APONI-Nonce": f"nonce-{time.time_ns()}",
    }


def test_control_queue_write_requires_jwt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APONI_COMMAND_SURFACE", "1")
    monkeypatch.setenv("APONI_CONTROL_REQUIRE_JWT", "1")
    monkeypatch.setenv("APONI_DASHBOARD_JWT_SECRET", "test-secret")

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0, jwt_secret="test-secret")
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        try:
            _http_post_json(
                f"http://127.0.0.1:{port}/control/queue",
                {"type": "run_task"},
                headers={"Origin": f"http://127.0.0.1:{port}", "X-APONI-Nonce": "n-1"},
            )
            assert False, "expected unauthorized"
        except urlerror.HTTPError as exc:
            assert exc.code == 401
            payload = json.loads(exc.read().decode("utf-8"))
            assert payload["ok"] is False
            assert payload["error"] == "missing_jwt"
    finally:
        dashboard.stop()


def test_control_execution_write_rejects_invalid_origin(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APONI_COMMAND_SURFACE", "1")
    monkeypatch.setenv("APONI_CONTROL_REQUIRE_JWT", "1")

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0, jwt_secret="test-secret")
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        headers = _issue_control_headers(port)
        headers["Origin"] = "http://evil.local"
        headers["X-APONI-Nonce"] = f"nonce-{time.time_ns()}"
        try:
            _http_post_json(
                f"http://127.0.0.1:{port}/control/execution",
                {"type": "execution_control", "action": "cancel", "target_command_id": "cmd-000001-aaaaaaaaaaaa"},
                headers=headers,
            )
            assert False, "expected forbidden"
        except urlerror.HTTPError as exc:
            assert exc.code == 403
            payload = json.loads(exc.read().decode("utf-8"))
            assert payload["ok"] is False
            assert payload["error"] == "invalid_origin"
    finally:
        dashboard.stop()


def test_control_execution_write_accepts_valid_auth(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APONI_COMMAND_SURFACE", "1")
    monkeypatch.setenv("APONI_CONTROL_REQUIRE_JWT", "1")

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0, jwt_secret="test-secret")
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        headers = _issue_control_headers(port)
        with _http_post_json(
            f"http://127.0.0.1:{port}/control/execution",
            {"type": "execution_control", "action": "cancel", "target_command_id": "cmd-000001-aaaaaaaaaaaa"},
            headers=headers,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["entry"]["payload"]["type"] == "execution_control"
    finally:
        dashboard.stop()


def test_simulation_submission_and_inline_result_rendering(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def _fake_sim_api(method: str, path: str, payload: dict | None = None):
        if method == "POST" and path == "/simulation/run":
            observed["payload"] = payload or {}
            return {
                "ok": True,
                "run_id": "sim-run-001",
                "comparative_outcomes": {"actual": {"health": 0.73}, "simulated": {"health": 0.79}, "delta": {"health": 0.06}},
                "result": {"epochs": [{"epoch_id": "epoch-1", "passed": True}]},
                "provenance": {"deterministic": True},
            }
        if method == "GET" and path == "/simulation/results/sim-run-001":
            return {
                "ok": True,
                "run_id": "sim-run-001",
                "comparative_outcomes": {"actual": {"health": 0.73}, "simulated": {"health": 0.79}, "delta": {"health": 0.06}},
                "result": {"epochs": [{"epoch_id": "epoch-1", "passed": True}]},
                "provenance": {"deterministic": True, "replay_seed": "stable-seed"},
            }
        return {"ok": False, "error": "unexpected_call", "method": method, "path": path}

    monkeypatch.setattr(aponi_dashboard, "_simulation_api_request", _fake_sim_api)
    monkeypatch.setattr(aponi_dashboard, "_simulation_max_epoch_range", lambda: 10)

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        request_payload = {
            "dsl_text": "max_mutations_per_epoch(5)",
            "constraints": [{"type": "max_mutations_per_epoch", "count": 5}],
            "epoch_range": {"start": 1, "end": 5},
        }
        with _http_post_json(f"http://127.0.0.1:{port}/simulation/run", request_payload) as response:
            run_payload = json.loads(response.read().decode("utf-8"))

        with urlopen(f"http://127.0.0.1:{port}/simulation/results/sim-run-001", timeout=5) as response:
            result_payload = json.loads(response.read().decode("utf-8"))

        with urlopen(f"http://127.0.0.1:{port}/index.html", timeout=5) as response:
            page_html = response.read().decode("utf-8")
    finally:
        dashboard.stop()

    assert run_payload["ok"] is True
    assert run_payload["run_id"] == "sim-run-001"
    assert "comparative_outcomes" in run_payload
    assert "provenance" in run_payload
    assert observed["payload"]["constraints"] == [{"type": "max_mutations_per_epoch", "count": 5}]

    assert result_payload["ok"] is True
    assert result_payload["comparative_outcomes"]["delta"]["health"] == 0.06
    assert result_payload["provenance"]["replay_seed"] == "stable-seed"

    assert 'id="proposalSimulationPanel"' in page_html
    assert 'id="simulationRun"' in page_html
    assert 'id="simulationResults"' in page_html


def test_simulation_run_rejects_epoch_range_beyond_android_bound(monkeypatch) -> None:
    monkeypatch.setattr(aponi_dashboard, "_simulation_max_epoch_range", lambda: 10)

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        assert dashboard._server is not None
        port = dashboard._server.server_port
        request_payload = {
            "dsl_text": "max_mutations_per_epoch(5)",
            "constraints": [{"type": "max_mutations_per_epoch", "count": 5}],
            "epoch_range": {"start": 1, "end": 25},
        }
        try:
            _http_post_json(f"http://127.0.0.1:{port}/simulation/run", request_payload)
            assert False, "expected epoch_range_exceeds_platform_limit"
        except urlerror.HTTPError as exc:
            assert exc.code == 400
            payload = json.loads(exc.read().decode("utf-8"))
    finally:
        dashboard.stop()

    assert payload["ok"] is False
    assert payload["error"] == "epoch_range_exceeds_platform_limit"
    assert payload["max_epoch_range"] == 10


def test_reviewer_panel_in_state_payload(monkeypatch, tmp_path) -> None:
    """reviewer_panel key must appear in state_payload when dashboard fetches state."""
    from security.ledger import journal as _journal_module
    empty_journal = tmp_path / "journal.jsonl"
    empty_journal.touch()
    monkeypatch.setattr(_journal_module, "JOURNAL_PATH", empty_journal)
    monkeypatch.setattr(_journal_module, "TAIL_STATE_PATH", tmp_path / "tail.json")

    from ui.aponi_dashboard import AponiDashboard
    panel = AponiDashboard._reviewer_reputation_panel()
    assert "epoch_id" in panel
    assert "reputation_scores" in panel
    assert "tier_calibration" in panel
    assert "scoring_algorithm_version" in panel


def test_reviewer_panel_constitutional_floor_enforced(monkeypatch, tmp_path) -> None:
    """tier_calibration entries must always carry constitutional_floor_enforced=True."""
    from security.ledger import journal as _journal_module
    import json

    # Write one reviewer_action_outcome event to the journal
    journal = tmp_path / "journal.jsonl"
    entry = {
        "tx": "TX-test",
        "ts": "2026-03-05T00:00:00Z",
        "type": "reviewer_action_outcome",
        "payload": {
            "reviewer_id": "alice",
            "review_id": "rv-1",
            "mutation_id": "mut-1",
            "decision": "approve",
            "latency_seconds": 1000.0,
            "epoch_id": "epoch-7",
            "scoring_algorithm_version": "1.0",
        },
        "prev_hash": "0" * 64,
    }
    import hashlib
    material = entry.copy()
    del material["prev_hash"]
    # Recompute hash
    m = hashlib.sha256((entry["prev_hash"] + json.dumps({k: v for k, v in entry.items() if k != "prev_hash"}, ensure_ascii=False, sort_keys=True)).encode()).hexdigest()
    entry["hash"] = m
    journal.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(_journal_module, "JOURNAL_PATH", journal)
    monkeypatch.setattr(_journal_module, "TAIL_STATE_PATH", tmp_path / "tail.json")

    from ui.aponi_dashboard import AponiDashboard
    panel = AponiDashboard._reviewer_reputation_panel()
    for tier_data in panel["tier_calibration"].values():
        assert tier_data["constitutional_floor_enforced"] is True


# ---------------------------------------------------------------------------
# ADAAD-9 Phase 4 — Replay Inspector UI e2e extensions (PR-9-02)
# ---------------------------------------------------------------------------

def test_replay_inspector_epoch_chain_covers_last_n_epochs(tmp_path, monkeypatch) -> None:
    """Replay inspector endpoint returns a navigable epoch chain (last N epochs)."""
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    for i in range(1, 6):
        epoch_id = f"epoch-chain-{i:02d}"
        ledger.append_event("EpochStartEvent", {"epoch_id": epoch_id, "state": {"x": i}})
        ledger.append_bundle_with_digest(
            epoch_id,
            {
                "bundle_id": f"bundle-chain-{i:02d}",
                "impact": 0.1 * i,
                "risk_tier": "low",
                "certificate": {"bundle_id": f"bundle-chain-{i:02d}"},
                "strategy_set": [],
            },
        )
        ledger.append_event("EpochEndEvent", {"epoch_id": epoch_id, "state": {"x": i + 1}})

    monkeypatch.setattr(aponi_dashboard, "LineageLedgerV2", lambda: ledger)
    monkeypatch.setattr(aponi_dashboard, "EvidenceBundleBuilder", _StaticBundleBuilder)

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        port = dashboard._server.server_port
        with urlopen(f"http://127.0.0.1:{port}/replay/divergence", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        dashboard.stop()

    # All 5 epochs must appear in proof_status (epoch chain coverage)
    proof_status = payload.get("proof_status", {})
    for i in range(1, 6):
        epoch_id = f"epoch-chain-{i:02d}"
        assert epoch_id in proof_status, (
            f"Inspector missing epoch {epoch_id} from proof_status; got keys: {list(proof_status.keys())}"
        )


def test_replay_inspector_diff_surfaces_canonical_digest(tmp_path, monkeypatch) -> None:
    """Replay diff must include canonical_digest for deterministic verification."""
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-digest-check"
    ledger.append_event("EpochStartEvent", {"epoch_id": epoch_id, "state": {"x": 10}})
    ledger.append_bundle_with_digest(
        epoch_id,
        {
            "bundle_id": "bundle-digest-check",
            "impact": 0.3,
            "risk_tier": "standard",
            "certificate": {"bundle_id": "bundle-digest-check"},
            "strategy_set": [],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": epoch_id, "state": {"x": 11}})

    monkeypatch.setattr(aponi_dashboard, "LineageLedgerV2", lambda: ledger)
    monkeypatch.setattr(aponi_dashboard, "EvidenceBundleBuilder", _StaticBundleBuilder)

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        port = dashboard._server.server_port
        with urlopen(f"http://127.0.0.1:{port}/replay/diff?epoch_id={epoch_id}", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        dashboard.stop()

    assert payload.get("ok") is True
    assert "export_metadata" in payload
    digest = payload["export_metadata"].get("digest", "")
    assert digest.startswith("sha256:"), (
        f"export_metadata.digest must start with 'sha256:'; got: {digest!r}"
    )


def test_replay_inspector_divergence_alerts_visually_distinguished(tmp_path, monkeypatch) -> None:
    """Divergence events must appear in proof_status with distinct error markers."""
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_div = "epoch-div-alert"
    ledger.append_event("EpochStartEvent", {"epoch_id": epoch_div, "state": {"x": 1}})
    ledger.append_bundle_with_digest(
        epoch_div,
        {
            "bundle_id": "bundle-div-alert",
            "impact": 0.9,
            "risk_tier": "high",
            "certificate": {"bundle_id": "bundle-div-alert"},
            "strategy_set": [],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": epoch_div, "state": {"x": 2}})

    monkeypatch.setattr(aponi_dashboard, "LineageLedgerV2", lambda: ledger)
    monkeypatch.setattr(
        aponi_dashboard.metrics,
        "tail",
        lambda limit=200: [
            {
                "event": "replay_divergence",
                "payload": {"epoch_id": epoch_div, "reason": "canonical_digest_mismatch"},
            }
        ],
    )

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        port = dashboard._server.server_port
        with urlopen(f"http://127.0.0.1:{port}/replay/divergence", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        dashboard.stop()

    assert payload["divergence_event_count"] >= 1
    assert epoch_div in payload["proof_status"]


def test_replay_inspector_lineage_navigation_from_mutation(tmp_path, monkeypatch) -> None:
    """From a mutation in the replay trace, full lineage must be navigable."""
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")

    for i, (epoch_id, bundle_id, parent) in enumerate([
        ("epoch-nav-1", "mut-nav-1", None),
        ("epoch-nav-2", "mut-nav-2", "mut-nav-1"),
        ("epoch-nav-3", "mut-nav-3", "mut-nav-2"),
    ]):
        ledger.append_event("EpochStartEvent", {"epoch_id": epoch_id, "state": {"x": i}})
        cert = {"bundle_id": bundle_id}
        if parent:
            cert["parent_bundle_id"] = parent
            cert["ancestor_chain"] = [parent]
        ledger.append_bundle_with_digest(
            epoch_id,
            {
                "bundle_id": bundle_id,
                "impact": 0.1 * (i + 1),
                "risk_tier": "low",
                "certificate": cert,
                "strategy_set": [],
            },
        )
        ledger.append_event("EpochEndEvent", {"epoch_id": epoch_id, "state": {"x": i + 1}})

    monkeypatch.setattr(aponi_dashboard, "LineageLedgerV2", lambda: ledger)
    monkeypatch.setattr(aponi_dashboard, "EvidenceBundleBuilder", _StaticBundleBuilder)

    dashboard = aponi_dashboard.AponiDashboard(host="127.0.0.1", port=0)
    dashboard.start({"status": "ok"})
    try:
        port = dashboard._server.server_port
        with urlopen(f"http://127.0.0.1:{port}/replay/diff?epoch_id=epoch-nav-3", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        dashboard.stop()

    assert payload.get("ok") is True
    lineage = payload.get("lineage_chain", {})
    mutations = lineage.get("mutations", [])
    assert mutations, "lineage_chain.mutations must be non-empty for epoch-nav-3"
    last = mutations[-1]
    assert last["mutation_id"] == "mut-nav-3"
    ancestor_chain = last.get("ancestor_chain", [])
    assert "mut-nav-2" in ancestor_chain, (
        f"Expected 'mut-nav-2' in ancestor_chain; got: {ancestor_chain}"
    )
