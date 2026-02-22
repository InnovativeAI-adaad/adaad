from runtime.evolution.replay_proof import generate_proof_bundle


def test_generate_proof_bundle_has_required_fields(tmp_path):
    ledger = tmp_path / "lineage_v2.jsonl"
    ledger.write_text("", encoding="utf-8")
    bundle = generate_proof_bundle("epoch-1", ledger_path=ledger)
    assert bundle["epoch_id"] == "epoch-1"
    for key in ("baseline_digest", "ledger_state_hash", "mutation_graph_fingerprint", "constitution_version", "bundle_hash"):
        assert key in bundle
