#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""ADAAD Phase 121 — Epoch Replay Tool (DAS-REPLAY-0).

Loads a JSONL ledger produced by demo_runner.py and verifies that every
record_hash can be independently re-derived from the stored inputs.
Exits 0 on success, 1 on any divergence.

Usage:
    python scripts/replay_epoch.py --ledger data/das_demo_ledger.jsonl
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from runtime.innovations30.deterministic_audit_sandbox import (
    DASReplayError,
    DASViolation,
    DeterministicAuditSandbox,
    RuntimeDeterminismProvider,
    _CHAIN_PREFIX_LEN,
    _GENESIS_PREV,
    _compute_chain_link,
)

_GREEN = "\033[92m"
_RED   = "\033[91m"
_CYAN  = "\033[96m"
_RESET = "\033[0m"


def replay(ledger_path: Path) -> int:
    """Replay all records in a ledger and verify chain hashes. Returns exit code."""
    if not ledger_path.exists():
        print(f"{_RED}  ✗  Ledger not found: {ledger_path}{_RESET}", file=sys.stderr)
        return 1

    print(f"\n{_CYAN}  ADAAD — Epoch Replay  ·  INNOV-36 · DAS-REPLAY-0{_RESET}\n")
    print(f"  Ledger: {ledger_path}\n")

    import json

    lines = [l.strip() for l in ledger_path.read_text().splitlines() if l.strip()]
    if not lines:
        print(f"{_RED}  ✗  Ledger is empty.{_RESET}", file=sys.stderr)
        return 1

    prev = _GENESIS_PREV
    errors = 0
    for i, line in enumerate(lines, start=1):
        d = json.loads(line)
        stored_hash = d["record_hash"]
        stored_prev = d["prev_digest"]
        record_id = f"{d['epoch_id']}:{d['mutation_id']}"
        expected = _compute_chain_link(record_id=record_id, prev_digest=prev)

        if stored_prev != prev:
            print(f"  [{i:02d}]  {_RED}PREV MISMATCH{_RESET}  "
                  f"stored_prev={stored_prev!r}  tracked={prev!r}")
            errors += 1
        elif stored_hash != expected:
            print(f"  [{i:02d}]  {_RED}HASH MISMATCH{_RESET}  "
                  f"stored={stored_hash!r}  expected={expected!r}")
            errors += 1
        else:
            print(f"  [{i:02d}]  {_GREEN}OK{_RESET}  "
                  f"{d['mutation_id']}  {d['status']:<16}  hash={stored_hash}")
        prev = stored_hash

    print()
    if errors == 0:
        print(f"{_GREEN}  Replay complete — {len(lines)} records, 0 errors. Chain VERIFIED.{_RESET}\n")
        return 0
    else:
        print(f"{_RED}  Replay FAILED — {errors} error(s) in {len(lines)} records.{_RESET}\n",
              file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="ADAAD DAS Epoch Replay")
    parser.add_argument("--ledger", default="data/das_demo_ledger.jsonl", help="Ledger JSONL path")
    args = parser.parse_args()
    sys.exit(replay(Path(args.ledger)))


if __name__ == "__main__":
    main()
