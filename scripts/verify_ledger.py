#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""ADAAD Phase 121 — Ledger Verifier (DAS-VERIFY-0).

Verifies the cryptographic chain integrity of any ADAAD JSONL audit ledger.
Exits 0 if all links are intact; exits 1 on first broken link.

Usage:
    python scripts/verify_ledger.py --ledger data/das_demo_ledger.jsonl [--verbose]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from runtime.innovations30.deterministic_audit_sandbox import (
    DASVerifyError,
    DASViolation,
    DeterministicAuditSandbox,
    _CHAIN_PREFIX_LEN,
    _GENESIS_PREV,
    _compute_chain_link,
)

_GREEN = "\033[92m"
_RED   = "\033[91m"
_CYAN  = "\033[96m"
_GOLD  = "\033[93m"
_RESET = "\033[0m"


def verify(ledger_path: Path, verbose: bool = False) -> int:
    """Verify ledger chain integrity. Returns 0 (ok) or 1 (failure)."""
    if not ledger_path.exists():
        print(f"{_RED}  ✗  Ledger not found: {ledger_path}{_RESET}", file=sys.stderr)
        return 1

    print(f"\n{_CYAN}  ADAAD — Ledger Verifier  ·  INNOV-36 · DAS-VERIFY-0{_RESET}\n")
    print(f"  Ledger   : {ledger_path}")
    print(f"  Hash len : {_CHAIN_PREFIX_LEN} chars (HMAC-SHA256 prefix)\n")

    try:
        result = DeterministicAuditSandbox.verify_ledger(ledger_path)
    except DASVerifyError as exc:
        print(f"{_RED}  ✗  Verification FAILED: {exc}{_RESET}\n", file=sys.stderr)
        return 1
    except DASViolation as exc:
        print(f"{_RED}  ✗  Constitution violation: {exc}{_RESET}\n", file=sys.stderr)
        return 1

    # ── optional verbose record dump ──────────────────────────────────────────
    if verbose:
        lines = [l.strip() for l in ledger_path.read_text().splitlines() if l.strip()]
        prev = _GENESIS_PREV
        for i, line in enumerate(lines, start=1):
            d = json.loads(line)
            record_id = f"{d['epoch_id']}:{d['mutation_id']}"
            computed = _compute_chain_link(record_id=record_id, prev_digest=prev)
            # Canonical comparison: computed[:_CHAIN_PREFIX_LEN] vs stored
            match = "✓" if d["record_hash"] == computed[:_CHAIN_PREFIX_LEN] else "✗"
            print(f"  [{i:02d}]  {_GREEN if match == '✓' else _RED}{match}{_RESET}  "
                  f"{d['mutation_id']}  prev={d['prev_digest'][:12]}…  "
                  f"hash={d['record_hash']}")
            prev = d["record_hash"]
        print()

    n = result["records_checked"]
    print(f"{_GREEN}  ✓  Verification PASSED{_RESET}")
    print(f"     Records checked : {n}")
    print(f"     Chain links     : {n} / {n} intact")
    print(f"     Result          : {_GREEN}OK{_RESET}\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ADAAD DAS Ledger Verifier")
    parser.add_argument("--ledger", default="data/das_demo_ledger.jsonl", help="Ledger JSONL path")
    parser.add_argument("--verbose", action="store_true", help="Print per-record verification")
    args = parser.parse_args()
    sys.exit(verify(Path(args.ledger), verbose=args.verbose))


if __name__ == "__main__":
    main()
