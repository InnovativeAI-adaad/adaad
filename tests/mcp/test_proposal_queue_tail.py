# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from runtime.api.agents import MutationRequest
from runtime.mcp.proposal_queue import append_proposal


def _request() -> MutationRequest:
    return MutationRequest(
        agent_id="agent-1",
        generation_ts="2026-01-01T00:00:00Z",
        intent="test",
        ops=[{"op": "replace", "path": "/x", "value": 1}],
        signature="sig:test",
        nonce="n-1",
    )


def test_proposal_queue_recovers_from_missing_tail_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "proposal_queue.jsonl"
    first = append_proposal(proposal_id="p-1", request=_request(), path=path)
    path.with_suffix(".jsonl.tail.json").unlink()

    second = append_proposal(proposal_id="p-2", request=_request(), path=path)

    assert second["prev_hash"] == first["hash"]


def test_proposal_queue_recovers_after_crash_mid_sidecar_write(tmp_path: Path) -> None:
    path = tmp_path / "proposal_queue.jsonl"
    append_proposal(proposal_id="p-1", request=_request(), path=path)
    sidecar = path.with_suffix(".jsonl.tail.json")
    sidecar.write_text('{"hash":', encoding="utf-8")

    append_proposal(proposal_id="p-2", request=_request(), path=path)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines[1]["prev_hash"] == lines[0]["hash"]
