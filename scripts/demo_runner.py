#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""ADAAD Phase 121 — Demo Runner (DAS).

Executes a full CEL epoch in the Deterministic Audit Sandbox, writes an
8-record JSONL ledger, verifies the chain, and exits 0.  Any constitution
violation causes exit 1 (DAS-GATE-0).

Usage:
    python scripts/demo_runner.py [--ledger PATH] [--seed SEED] [--epoch EPOCH_ID]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Resolve project root (scripts/ lives one level below repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from runtime.innovations30.deterministic_audit_sandbox import (
    DASViolation,
    DeterministicAuditSandbox,
    RuntimeDeterminismProvider,
)

_BANNER = """
╔══════════════════════════════════════════════════════╗
║        ADAAD — Deterministic Audit Sandbox           ║
║        INNOV-36 · Phase 121 · v9.54.0                ║
╚══════════════════════════════════════════════════════╝
"""

_GREEN  = "\033[92m"
_RED    = "\033[91m"
_CYAN   = "\033[96m"
_GOLD   = "\033[93m"
_RESET  = "\033[0m"


def _ok(msg: str) -> None:
    print(f"{_GREEN}  ✓  {msg}{_RESET}")


def _err(msg: str) -> None:
    print(f"{_RED}  ✗  {msg}{_RESET}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"{_CYAN}  ·  {msg}{_RESET}")


def run_demo(
    ledger_path: Path,
    seed: str,
    epoch_id: str,
    n_mutations: int = 8,
) -> int:
    """Execute the full demo pipeline. Returns exit code (0 = success, 1 = failure)."""
    print(_BANNER)

    # ── Step 1: initialise sandbox ────────────────────────────────────────────
    _info("Initialising DeterministicAuditSandbox …")
    timer = RuntimeDeterminismProvider(base_ts="2026-04-04T00:00:00Z", step_seconds=1)
    sandbox = DeterministicAuditSandbox(ledger_path=ledger_path, timer=timer)
    _ok("Sandbox initialised")

    # ── Step 2: execute epoch ─────────────────────────────────────────────────
    _info(f"Running epoch {epoch_id!r} with seed {seed!r} ({n_mutations} mutations) …")
    try:
        records = sandbox.run_epoch(epoch_id=epoch_id, seed=seed, n_mutations=n_mutations)
    except DASViolation as exc:
        _err(f"DAS constitution violation during epoch run: {exc}")
        return 1
    _ok(f"Epoch complete — {len(records)} mutation records produced")

    # ── Step 3: print record summary ──────────────────────────────────────────
    print(f"\n{_GOLD}  Ledger Records:{_RESET}")
    for i, rec in enumerate(records, start=1):
        status_color = _GREEN if rec.status == "approved" else _RED
        print(
            f"    [{i:02d}] {rec.mutation_id}  "
            f"{status_color}{rec.status:<16}{_RESET}  "
            f"hash={rec.record_hash}"
        )

    # ── Step 4: flush to JSONL ────────────────────────────────────────────────
    print()
    _info(f"Flushing ledger to {ledger_path} …")
    try:
        sandbox.flush()
    except DASViolation as exc:
        _err(f"DAS constitution violation during flush: {exc}")
        return 1
    _ok(f"Ledger written — {n_mutations} records")

    # ── Step 5: verify chain (DAS-VERIFY-0) ──────────────────────────────────
    _info("Verifying ledger chain integrity (DAS-VERIFY-0) …")
    try:
        result = DeterministicAuditSandbox.verify_ledger(ledger_path)
    except DASViolation as exc:
        _err(f"Chain verification FAILED: {exc}")
        return 1
    _ok(f"Chain verified — {result['records_checked']} records, all chain links intact")

    # ── Step 6: replay epoch (DAS-REPLAY-0) ──────────────────────────────────
    _info("Replaying epoch from ledger (DAS-REPLAY-0) …")
    timer2 = RuntimeDeterminismProvider(base_ts="2026-04-04T00:00:00Z", step_seconds=1)
    sb2 = DeterministicAuditSandbox(ledger_path=ledger_path.parent / "replay_check.jsonl", timer=timer2)
    try:
        replayed = sb2.replay_epoch(ledger_path)
    except DASViolation as exc:
        _err(f"Replay FAILED: {exc}")
        return 1
    _ok(f"Replay verified — {len(replayed)} records, all digests match")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{_GREEN}{'═' * 56}{_RESET}")
    print(f"{_GREEN}  DEMO PASSED — all DAS constitutional gates cleared{_RESET}")
    print(f"{_GREEN}{'═' * 56}{_RESET}\n")
    print(f"  Ledger   : {ledger_path}")
    print(f"  Records  : {n_mutations}")
    print(f"  Chain    : VERIFIED")
    print(f"  Replay   : VERIFIED")
    print(f"  Exit     : 0\n")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ADAAD DAS Demo Runner")
    parser.add_argument("--ledger", default="data/das_demo_ledger.jsonl", help="Output ledger path")
    parser.add_argument("--seed", default="adaad-innov36-demo-seed-v1", help="Epoch seed")
    parser.add_argument("--epoch", default="EPOCH-DAS-DEMO-001", help="Epoch ID")
    parser.add_argument("--mutations", type=int, default=8, help="Number of mutations (default 8)")
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    exit_code = run_demo(
        ledger_path=ledger_path,
        seed=args.seed,
        epoch_id=args.epoch,
        n_mutations=args.mutations,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
