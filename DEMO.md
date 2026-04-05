# ADAAD — Deterministic Audit Sandbox (DAS)
**INNOV-36 · Phase 121 · v9.54.0 · InnovativeAI LLC**

---

## What is DAS?

The **Deterministic Audit Sandbox** is a hermetic, reproducible execution
environment for ADAAD's Constitutional Evolution Loop (CEL). Any external
observer can clone this repository, run `docker-compose up das-demo`, and
receive a cryptographically verifiable audit ledger in under 60 seconds —
no ADAAD account, no credentials, no cloud infrastructure required.

Every ledger record is HMAC-SHA256 chain-linked to its predecessor.
Tampering with any record breaks the chain at that position and is
immediately detected by `verify_ledger.py`.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD

# 2. Run the full demo (generates ledger, verifies chain, replays epoch)
docker-compose up das-demo

# 3. Verify the ledger independently
docker-compose up das-verify

# 4. Replay and check all digest derivations
docker-compose up das-replay

# 5. Run the Phase 121 test suite
docker-compose run das-test
```

All commands exit 0 on success and 1 on any constitutional violation.

---

## Without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install pytest

# Run demo
python scripts/demo_runner.py --ledger data/das_demo_ledger.jsonl

# Verify
python scripts/verify_ledger.py --ledger data/das_demo_ledger.jsonl --verbose

# Replay
python scripts/replay_epoch.py --ledger data/das_demo_ledger.jsonl

# Tests (30/30)
pytest tests/test_phase121_das.py -v
```

---

## Constitutional Invariants (DAS)

| Invariant     | Class | Description |
|---------------|-------|-------------|
| `DAS-0`       | Hard  | Identical `(seed, epoch_id)` → byte-identical ledger records |
| `DAS-DETERM-0`| Hard  | All timestamps use `RuntimeDeterminismProvider`; no `datetime.now()` |
| `DAS-CHAIN-0` | Hard  | Every record is HMAC-SHA256 chain-linked to its predecessor |
| `DAS-REPLAY-0`| Hard  | `replay_epoch()` must reproduce identical `record_hash` values |
| `DAS-GATE-0`  | Hard  | `demo_runner` exits non-zero on any constitution violation |
| `DAS-VERIFY-0`| Hard  | `verify_ledger()` detects every broken chain link; no silent pass |
| `DAS-DOCKER-0`| Hard  | `Dockerfile.demo` pins exact Python image digest; `:latest` prohibited |

---

## Ledger Format

Each line in the JSONL ledger is a `json.dumps(..., sort_keys=True)` encoded
`EpochRecord`:

```json
{
  "epoch_id":    "EPOCH-DAS-DEMO-001",
  "mutation_id": "586ddbbda4675ed3",
  "metadata":    {},
  "prev_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "record_hash": "3aa591d3e75e466ca6cf2cde",
  "seed":        "adaad-innov36-demo-seed-v1",
  "status":      "approved",
  "timestamp":   "2026-04-04T00:00:00Z"
}
```

`record_hash` is the first 24 hex characters of:
```
HMAC-SHA256(
  key     = b"das-chain-key-innov36-v1",
  message = json.dumps({"prev": prev_digest, "sub": epoch_id+":"+mutation_id}, sort_keys=True)
)
```

The genesis record uses `prev_digest = "0" * 64`.

---

## Chain Verification Algorithm

```python
prev = "0" * 64
for record in ledger:
    assert record["prev_digest"] == prev          # stored prev must match tracked chain
    computed = hmac_sha256(key, payload)[:24]
    assert record["record_hash"] == computed      # hash must be re-derivable
    prev = record["record_hash"]
```

This is exactly what `verify_ledger.py` and `DeterministicAuditSandbox.verify_ledger()` do.

---

## Architecture

```
scripts/demo_runner.py           — orchestrates full pipeline, DAS-GATE-0
scripts/verify_ledger.py         — standalone chain verifier, DAS-VERIFY-0
scripts/replay_epoch.py          — epoch replay tool, DAS-REPLAY-0
runtime/innovations30/
  deterministic_audit_sandbox.py — DAS module, all 7 invariants
tests/test_phase121_das.py       — T121-DAS-01..30 (30/30)
Dockerfile.demo                  — pinned Python 3.12.3 image, DAS-DOCKER-0
docker-compose.yml               — 4 services: demo, verify, replay, test
```

---

## IP Claims

1. **Deterministic, hermetically reproducible CEL epoch sandbox** with
   cryptographic JSONL ledger chain-linkage, enabling external auditability
   without access to live ADAAD infrastructure.

2. **DAS-DOCKER-0 constitutional prohibition on `:latest` Docker tags** —
   image digest pinning enforced at constitutional invariant level in an
   autonomous AI governance system.

3. **HMAC-SHA256 chain-prefix ledger** with `prev_digest` field validation
   in `verify_ledger()`: broken links detected at both the hash level and
   the stored-prev-digest level, providing two independent tamper signals.

---

*Governance artifact: ILA-121-2026-04-04-001*
*Ratified by: DUSTIN L REID (HUMAN-0)*
