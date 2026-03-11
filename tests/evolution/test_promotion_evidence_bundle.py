# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
from pathlib import Path

from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from runtime.mutation_lifecycle import MutationLifecycleContext, transition


def test_successful_transition_writes_deterministic_evidence_bundle(tmp_path: Path, monkeypatch) -> None:
    import runtime.mutation_lifecycle as _lc
    monkeypatch.setattr(_lc, "_signature_valid", lambda sig, trust_mode, ctx: (True, "verified"))
    monkeypatch.setattr(_lc, "_known_agent_prefix_ok", lambda agent_id: True)
    manifests_dir = tmp_path / "security" / "promotion_manifests"
    context = MutationLifecycleContext(
        mutation_id="mut-evidence",
        agent_id="test-agent-1",
        epoch_id="epoch-7",
        signature="cryovant-static-valid-signature",
        trust_mode="prod",
        fitness_score=0.9,
        fitness_threshold=0.6,
        cert_refs={"certificate_digest": "sha256:cert"},
        metadata={"promotion_manifests_dir": str(manifests_dir), "fitness_history": [0.42, 0.9]},
        state_dir=tmp_path / "state",
    )

    transition("proposed", "staged", context)

    evidence_path = manifests_dir / "mut-evidence_evidence.json"
    assert evidence_path.exists()
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert set(("guard_report", "cert_refs", "fitness_history", "ledger_hash_at_promotion")).issubset(payload)
    assert payload["fitness_history"] == [0.42, 0.9]
    assert payload["guard_report"]["ok"] is True
    assert payload["ledger_hash_at_promotion"]

    expected = dict(payload)
    observed_hash = expected.pop("bundle_hash")
    assert observed_hash == sha256_prefixed_digest(canonical_json(expected))

