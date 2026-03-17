# SPDX-License-Identifier: Apache-2.0
"""CLI handlers for app.main facade commands."""

from __future__ import annotations

import argparse

from app import APP_ROOT
from adaad.orchestrator.status import build_status_report, render_human_table, report_as_json
from runtime.api.runtime_services import ReplayProofBuilder


def build_main_parser() -> argparse.ArgumentParser:
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
    parser.add_argument(
        "--adaad-status",
        action="store_true",
        help="Print ADAAD/DEVADAAD governance status summary and exit.",
    )
    parser.add_argument(
        "--trigger-mode",
        choices=("ADAAD", "DEVADAAD"),
        default="ADAAD",
        help="Trigger mode context for --adaad-status output.",
    )
    parser.add_argument(
        "--status-format",
        choices=("table", "json", "both"),
        default="both",
        help="Output format for --adaad-status.",
    )
    return parser


def handle_export_replay_proof(*, parser: argparse.ArgumentParser, export_replay_proof: bool, selected_epoch: str) -> bool:
    if not export_replay_proof:
        return False
    if not selected_epoch:
        parser.error("--export-replay-proof requires --epoch <id>")
    proof_path = ReplayProofBuilder().write_bundle(selected_epoch)
    print(proof_path.as_posix())
    return True


def handle_status_report(*, adaad_status: bool, trigger_mode: str, status_format: str) -> bool:
    if not adaad_status:
        return False
    report = build_status_report(repo_root=APP_ROOT.parent, trigger_mode=trigger_mode)
    if status_format in {"table", "both"}:
        print(render_human_table(report))
    if status_format in {"json", "both"}:
        if status_format == "both":
            print()
        print(report_as_json(report))
    return True
