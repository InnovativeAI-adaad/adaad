# ADAAD Documentation — v9.0.0

**Version:** 9.0.0 | **Phase:** 65 — Emergence | **Released:** 2026-03-13

> The world's first constitutional AI mutation engine: governed, deterministic, self-evolving.

---

## Documentation Index

### Governance & Architecture
| Document | Description |
|---|---|
| `governance/ARCHITECT_SPEC_v8.0.0.md` | Canonical architecture specification — all invariants, rules, and organ contracts |
| `governance/CONSTITUTION.md` | The 21 constitutional rules (16 pre-v2 + 5 GovernanceGateV2) |
| `governance/V8_HUMAN_GATE_READINESS.md` | Human gate signoff tracker — all 6 gates SIGNED_OFF for v9.0.0 |
| `governance/ADAAD_PR_PROCESSION_2026-03-v2.md` | PR milestone tracker through v9.0.0 |

### Phase Upgrade Plans
Located in `governance/phase_plans/` — one plan per phase capturing pre-work analysis, invariant contracts, test acceptance criteria, and post-merge verification.

### Evidence Artifacts
Located in `../artifacts/governance/` — cryptographically signed evidence bundles for every human-gated decision.

| Bundle | Gate | Phase |
|---|---|---|
| `phase65/mutation_target_signoff.json` | HUMAN-0 — mutation target selection | 65 |
| `phase65/v9_release_audit_report.json` | AUDIT-0 — 22/22 tests pass | 65 |
| `phase65/v9_replay_verification.json` | REPLAY-0 — 0 divergences | 65 |
| `phase64/cel_dry_run_signoff.json` | CEL-DRY-RUN — all 14 steps dry-run verified | 64 |
| `phase63/governance_gate_v2_signoff.json` | GATE-V2-RULES — GovernanceGateV2 accepted | 63 |
| `phase59/capability_graph_v2_signoff.json` | CAP-REGISTRY — 10 bootstrap capabilities | 59 |

---

## System Overview — v9.0.0

### What Changed in v9.0.0

Phase 65 (Emergence) wired together all nine evolutionary organs into a single, live, self-governing loop:

- **`evolution_loop.py`** now routes `run_epoch()` through `_run_cel_epoch()` when `ADAAD_CEL_ENABLED=true`
- **`cel_wiring.py`** gained `build_cel()`, `is_cel_enabled()`, `assert_cel_enabled_or_raise()`
- **`capability_graph.py`** gained `CapabilityChange` dataclass + `record_capability_change()` — the capability mutation ledger
- **`CapabilityGraph`** class consolidates capability change recording with hash-chaining
- `_emit_capability_changes()` is called from `_run_cel_epoch()` for every promoted candidate
- All 6 human gates for the v8→v9 transition signed off and evidenced

### The 14-Step CEL Sequence

Every epoch under `ADAAD_CEL_ENABLED=true` executes these steps in strict order (`CEL-ORDER-0`):

```
Step  1  MODEL-DRIFT-CHECK    Verify CodeIntelModel hasn't drifted
Step  2  LINEAGE-SNAPSHOT     Snapshot current LineageEngine state
Step  3  FITNESS-BASELINE     Record FitnessEngineV2 pre-epoch baseline
Step  4  PROPOSAL-GENERATE    ProposalEngine → LLM-backed candidates
Step  5  AST-SCAN             StaticSafetyScanner — 4 constitutional rules
Step  6  SANDBOX-EXECUTE      SandboxTournament in ephemeral clone
Step  7  REPLAY-VERIFY        SANDBOX-DIV-0 — hash equivalence check
Step  8  FITNESS-SCORE        FitnessEngineV2 composite score (7 signals)
Step  9  GOVERNANCE-GATE-V2   GovernanceGateV2 — 5 AST-aware rules
Step 10  GOVERNANCE-GATE      GovernanceGate — 16 pre-v2 rules
Step 11  LINEAGE-REGISTER     LineageEngine.register() for promoted candidates
Step 12  PROMOTION-DECISION   CapabilityGraph update + PromotionEvent emit
Step 13  EPOCH-EVIDENCE-WRITE Hash-chained EpochEvidence ledger append
Step 14  STATE-ADVANCE        Epoch counter increment + journal event
```

Skipping any step or executing out of order raises `CELOrderViolation`. No exception.

---

## Module Reference

### `runtime/evolution/cel_wiring.py`

```python
build_cel(*, sandbox_only: bool, ...) -> LiveWiredCEL
    # Factory. Reads ADAAD_SANDBOX_ONLY env var when sandbox_only not explicitly set.
    # Returns LiveWiredCEL with _dry_run=sandbox_only.

is_cel_enabled() -> bool
    # Returns True iff ADAAD_CEL_ENABLED=true in environment.

assert_cel_enabled_or_raise() -> None
    # Raises RuntimeError if CEL is not enabled.
```

### `runtime/evolution/evolution_loop.py`

```python
EvolutionLoop.run_epoch(context) -> EpochResult
    # Routes to _run_cel_epoch() when ADAAD_CEL_ENABLED=true,
    # otherwise to _run_legacy_epoch() (Phase 64 and prior behavior).

EvolutionLoop._run_cel_epoch(context) -> EpochResult
    # Builds LiveWiredCEL, runs it, extracts promoted IDs,
    # calls _emit_capability_changes(), wraps into EpochResult.

EvolutionLoop._emit_capability_changes(promoted_ids, epoch_evidence_hash) -> None
    # Fail-safe. Writes CapabilityChange entries to CapabilityGraph.
    # Exceptions are logged and swallowed — never propagated.

@dataclass
EpochResult:
    ...
    cel_result: Optional[object] = None   # Added Phase 65
```

### `runtime/capability_graph.py`

```python
@dataclass
CapabilityChange:
    node_id: str                  # capability node being changed
    old_version: str              # semver before
    new_version: str              # semver after
    epoch_evidence_hash: str      # SHA-256 of the epoch evidence record
    proposal_hash: str            # SHA-256 of the winning proposal
    timestamp: str                # ISO-8601

    @property
    change_id: str
        # SHA-256[:16] of "node_id:proposal_hash:epoch_evidence_hash"
        # Deterministic — identical inputs always produce identical IDs (INTEL-DET-0)

    def to_dict(self) -> dict
        # Returns ledger-ready record including change_id


def record_capability_change(change: CapabilityChange, ledger_path: Path = ...) -> str
    # Appends JSONL to ADAAD_CAP_CHANGE_LEDGER (default: data/capability_changes.jsonl).
    # Fail-safe on IOError. Returns SHA-256 digest of the appended record.


class CapabilityGraph:
    def __init__(self, ledger_path: Path = ...)
    def record_change(self, change: CapabilityChange) -> str
        # Delegates to record_capability_change.
```

### `runtime/tools/mutation_guard.py`

```python
apply_dna_mutation(agent_id: str, ops: list) -> dict
    # Applies JSON-Patch ops to agent DNA file.
    # UPSERT behaviour: if DNA file does not exist and all ops are "set"/"add"/"replace",
    #   bootstraps an empty {} DNA and proceeds. Non-upsert ops against missing files
    #   still raise FileNotFoundError.
    # Intermediate dict nodes are auto-vivified for set/add ops (no KeyError on deep paths).
    # Returns: {agent_id, parent_lineage, child_lineage, checksum, applied, skipped}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ADAAD_CEL_ENABLED` | `false` | `true` activates 14-step ConstitutionalEvolutionLoop routing |
| `ADAAD_SANDBOX_ONLY` | `false` | `true` runs CEL in dry-run mode — no real writes |
| `ADAAD_CAP_CHANGE_LEDGER` | `data/capability_changes.jsonl` | Path for CapabilityChange JSONL ledger |
| `ADAAD_DETERMINISTIC_LOCK` | `0` | `1` enforces deterministic-only execution paths |
| `ADAAD_REPLAY_PROOF_HMAC_SECRET_PROOF_KEY` | (required in prod) | HMAC secret for replay proof signing |
| `ADAAD_REPLAY_PROOF_PRIVATE_KEY_REPLAY_PROOF_ED25519_DEV` | (required in prod) | Ed25519 private key for replay attestation |
| `ADAAD_ANTHROPIC_API_KEY` | — | Enables live LLM proposals in ProposalEngine |

---

## Test Coverage by Phase

| Phase | Test File | Tests | Scope |
|---|---|---|---|
| 57 | `tests/evolution/test_phase57_*.py` | 16 | ProposalEngine, PROP-AUTO-0..5 |
| 58 | `tests/mutation/test_phase58_*.py` | 60 | CodeIntelModel, FunctionGraph, HotspotMap |
| 59 | `tests/capability/test_phase59_*.py` | 59 | CapabilityRegistry, Tier-0 guard |
| 60 | `tests/mutation/test_phase60_*.py` | 59 | ASTDiffPatch, StaticSafetyScanner, SandboxTournament |
| 61 | `tests/evolution/test_phase61_*.py` | 62 | LineageEngine, niches, epistasis |
| 62 | `tests/evolution/test_phase62_*.py` | ~50 | FitnessEngineV2, FIT-BOUND-0 |
| 63 | `tests/governance/test_phase63_*.py` | ~55 | GovernanceGateV2, exception tokens |
| 64 | `tests/evolution/test_phase64_*.py` | ~45 | LiveWiredCEL, 14-step sequence |
| **65** | **`tests/evolution/test_phase65_emergence.py`** | **22** | **CEL wiring, CapabilityChange, routing** |
| determinism | `tests/determinism/` | 102 | Replay attestation, boot profile, determinism |

---

*ADAAD Documentation — v9.0.0 — Phase 65: Emergence — 2026-03-13*
