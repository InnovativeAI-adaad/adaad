# SPDX-License-Identifier: Apache-2.0
"""CLI job for proposing/applying governance-approved fitness weight updates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime.evolution.fitness_weight_tuner import (
    apply_weight_update_with_governance,
    propose_weights_job,
)
from runtime.evolution.replay_attestation import load_replay_proof
from runtime.governance.foundation import canonical_json


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Propose or apply governance-gated fitness weight updates.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    propose = subparsers.add_parser("propose", help="Generate proposal artifact from historical outcomes and replay proof")
    propose.add_argument("--history", type=Path, required=True, help="Path to historical outcomes JSON with entries[]")
    propose.add_argument("--config", type=Path, required=True, help="Path to runtime/evolution/config/fitness_weights.json")
    propose.add_argument("--replay-proof", type=Path, required=True, help="Path to replay_attestation.v1.json bundle")
    propose.add_argument("--output", type=Path, required=True, help="Output path for proposal artifact")
    propose.add_argument("--proposal-id", type=str, required=True, help="Deterministic proposal identifier")
    propose.add_argument("--signer-key-id", type=str, default="fitness-weight-dev", help="Proposal signer key id")

    apply_cmd = subparsers.add_parser("apply", help="Apply proposal only when signature + replay proof verify")
    apply_cmd.add_argument("--proposal", type=Path, required=True, help="Path to proposal artifact")
    apply_cmd.add_argument("--config", type=Path, required=True, help="Current fitness_weights.json path")
    apply_cmd.add_argument("--replay-proof", type=Path, required=True, help="Path to replay_attestation.v1.json bundle")
    apply_cmd.add_argument("--output", type=Path, required=True, help="Output path for updated fitness_weights.json")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "propose":
        destination = propose_weights_job(
            history_path=args.history,
            config_path=args.config,
            replay_proof_path=args.replay_proof,
            proposal_output_path=args.output,
            signer_key_id=args.signer_key_id,
            proposal_id=args.proposal_id,
        )
        print(destination.as_posix())
        return 0

    proposal_artifact = json.loads(args.proposal.read_text(encoding="utf-8"))
    config_payload = json.loads(args.config.read_text(encoding="utf-8"))
    replay_bundle = load_replay_proof(args.replay_proof)
    updated = apply_weight_update_with_governance(
        proposal_artifact,
        replay_proof=replay_bundle,
        current_config=config_payload,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(updated) + "\n", encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
