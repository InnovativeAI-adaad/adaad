# SPDX-License-Identifier: Apache-2.0
"""CLI argument handling for the ADAAD app composition root."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any

from runtime.api.runtime_services import ReplayMode, ReplayProofBuilder, normalize_replay_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ADAAD orchestrator")
    parser.add_argument("--verbose", action="store_true", help="Print boot stage diagnostics to stdout.")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate mutations without applying them.")
    parser.add_argument(
        "--replay",
        default="off",
        help=(
            "Replay mode: off (skip replay), audit (verify and continue), strict (verify and fail-close). "
            "Deprecated aliases: full->audit, true->audit, false->off."
        ),
    )
    parser.add_argument("--replay-epoch", default="", help="Replay a specific epoch id as the verification target.")
    parser.add_argument("--epoch", default="", help="Epoch identifier used for replay-proof export or replay targeting.")
    parser.add_argument("--verify-replay", action="store_true", help="Run replay verification and exit after reporting result.")
    parser.add_argument(
        "--exit-after-boot",
        action="store_true",
        help="Complete one governed boot (including replay audit) and exit before any mutation cycle.",
    )
    parser.add_argument(
        "--export-replay-proof",
        action="store_true",
        help="Export a signed replay proof bundle for --epoch and exit.",
    )
    return parser


def resolve_runtime_inputs(args: Any, parser: argparse.ArgumentParser) -> tuple[bool, ReplayMode, str]:
    dry_run_env = os.getenv("ADAAD_DRY_RUN", "").lower() in {"1", "true", "yes", "on"}
    try:
        replay_mode = normalize_replay_mode(args.replay)
    except ValueError as exc:
        parser.error(str(exc))

    selected_epoch = (args.epoch or args.replay_epoch).strip()
    if args.epoch and args.replay_epoch and args.epoch.strip() != args.replay_epoch.strip():
        logging.warning("Both --epoch (%s) and --replay-epoch (%s) were provided; using --epoch.", args.epoch, args.replay_epoch)
    return dry_run_env, replay_mode, selected_epoch


def maybe_export_replay_proof(args: Any, parser: argparse.ArgumentParser, selected_epoch: str) -> bool:
    if not args.export_replay_proof:
        return False
    if not selected_epoch:
        parser.error("--export-replay-proof requires --epoch <id>")
    proof_path = ReplayProofBuilder().write_bundle(selected_epoch)
    print(proof_path.as_posix())
    return True
