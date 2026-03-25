# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from runtime.governance.mutation_ledger import GENESIS_PREV_HASH
from runtime.io.jsonl_tail import read_jsonl_tail

_TOKEN = "tail-opt-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client() -> TestClient:
    from server import app

    return TestClient(app, raise_server_exceptions=True)


def _legacy_mutation_projection(path: Path, *, limit: int, promoted_only: bool) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))

    promoted_count = sum(1 for e in entries if e.get("entry", {}).get("promoted") is True)
    filtered = [e for e in entries if e.get("entry", {}).get("promoted") is True] if promoted_only else entries
    windowed = list(reversed(filtered))[:limit]

    last_hash = GENESIS_PREV_HASH
    for candidate in reversed(entries):
        record_hash = candidate.get("hash")
        if isinstance(record_hash, str) and record_hash:
            last_hash = record_hash
            break

    return {
        "entries": windowed,
        "total_in_window": len(windowed),
        "total_entries": len(entries),
        "promoted_count": promoted_count,
        "last_hash": last_hash,
        "ledger_version": "1.0",
    }


def test_governance_mutation_ledger_schema_unchanged(client: TestClient) -> None:
    response = client.get("/governance/mutation-ledger", headers=_AUTH)
    payload = response.json()

    assert response.status_code == 200
    assert set(payload.keys()) == {"schema_version", "authn", "data"}
    assert set(payload["data"].keys()) == {
        "entries",
        "total_in_window",
        "total_entries",
        "promoted_count",
        "last_hash",
        "ledger_version",
    }


def test_governance_mutation_ledger_matches_legacy_logic(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "mutation_audit.jsonl"
    rows = [
        {"entry": {"promoted": False}, "hash": "sha256:a"},
        {"entry": {"promoted": True}, "hash": "sha256:b"},
        {"entry": {"promoted": True}, "hash": "sha256:c"},
        {"entry": {"promoted": False}, "hash": "sha256:d"},
    ]
    ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    import server as server_module

    monkeypatch.setattr(server_module, "_DEFAULT_MUTATION_LEDGER_PATH", str(ledger))

    expected_all = _legacy_mutation_projection(ledger, limit=3, promoted_only=False)
    expected_promoted = _legacy_mutation_projection(ledger, limit=2, promoted_only=True)

    resp_all = client.get("/governance/mutation-ledger?limit=3", headers=_AUTH)
    resp_promoted = client.get("/governance/mutation-ledger?limit=2&promoted_only=true", headers=_AUTH)

    assert resp_all.status_code == 200
    assert resp_promoted.status_code == 200
    assert resp_all.json()["data"] == expected_all
    assert resp_promoted.json()["data"] == expected_promoted


def test_jsonl_tail_large_file_reads_bounded_bytes(tmp_path: Path) -> None:
    ledger = tmp_path / "large.jsonl"
    lines = [json.dumps({"idx": idx, "value": f"v-{idx}"}) for idx in range(20_000)]
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = read_jsonl_tail(ledger, limit=5, chunk_size=256)

    assert [record["idx"] for record in result.records] == [19_995, 19_996, 19_997, 19_998, 19_999]
    assert result.bytes_read < ledger.stat().st_size


def test_governance_scoring_engine_schema_and_logic_match(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "scoring.jsonl"
    rows = [{"score": idx} for idx in range(8)]
    ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    monkeypatch.setenv("ADAAD_SCORING_LEDGER_PATH", str(ledger))

    response = client.get("/governance/scoring-engine?limit=3", headers=_AUTH)
    payload = response.json()

    assert response.status_code == 200
    assert set(payload.keys()) == {"ok", "algorithm_version", "severity_weights", "recent_entries", "entry_count"}
    assert payload["recent_entries"] == rows[-3:]
    assert payload["entry_count"] == 3
