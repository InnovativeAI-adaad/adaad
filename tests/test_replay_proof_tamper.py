import json
import subprocess
import sys

from runtime.evolution.replay_proof import generate_proof_bundle


def test_verify_replay_bundle_detects_tamper(tmp_path):
    bundle = generate_proof_bundle("epoch-2", ledger_path=tmp_path / "missing.jsonl")
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle, sort_keys=True), encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ledger_state_hash"] = "00"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    proc = subprocess.run([sys.executable, "tools/verify_replay_bundle.py", str(path)], capture_output=True, text=True)
    assert proc.returncode == 1
