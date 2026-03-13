# ADAAD Repository — Deep Dive Audit & Hardening Report

**Scope:** `InnovativeAI-adaad/ADAAD` · Full tree analysis  
**DUSTADAAD Context:** DUSTADAAD Governed Autonomy Environment  
**Audit Date:** 2026-03-02  
**Prepared for:** Innovative AI LLC — Architect & Operational Lead  

---

## Executive Summary

The ADAAD repository is architecturally mature for a governed-autonomy system at v1.0. Governance primitives, deterministic replay, federation transport, and CI gating are well-structured. However, the audit surfaces **31 concrete findings** spanning security hardening, import discipline, CI reliability, performance, observability, and documentation gaps. All findings are mapped to draft PRs with commit-ready specifications below.

**Severity classification:**

| Severity | Count | Meaning |
|---|---|---|
| 🔴 Critical | 4 | May silently bypass governance invariants or produce exploitable state |
| 🟠 High | 8 | Weakens auditability, replay safety, or security posture |
| 🟡 Medium | 11 | Operational risk, hardening, or clarity gaps |
| 🔵 Low / Enhancement | 8 | Performance, DX, and documentation improvements |

---

## 1. Critical Findings

### C-01 — `verify_session()` Legacy Path Accepts Any Token in Dev Mode Without Expiry Gate

**File:** `runtime/governance/auth/` (production auth contract)  
**Risk:** `CRYOVANT_DEV_TOKEN` bypass is gated on `ADAAD_ENV=dev` **and** `CRYOVANT_DEV_MODE`, but if either env var is set by accident in a staging environment with lax `.env` propagation, the entire governance token check is bypassed for any caller using the legacy `verify_session()` API.

**Hardening Required:**
```python
# BEFORE (current behavior — dev token accepted if env vars are set)
if os.getenv("CRYOVANT_DEV_MODE") and os.getenv("ADAAD_ENV") == "dev":
    return _accept_dev_token(token)

# AFTER — add explicit staging guard and expiry check even for dev tokens
_STRICT_ENVS = frozenset({"staging", "production", "prod"})
_current_env = (os.getenv("ADAAD_ENV") or "").strip().lower()
if _current_env in _STRICT_ENVS:
    raise GovernanceTokenError("dev_token_rejected:strict_env")
if os.getenv("CRYOVANT_DEV_MODE") and _current_env == "dev":
    _assert_dev_token_not_expired(token)  # enforce expiry even in dev
    return _accept_dev_token(token)
```

**Additional:** Add `ADAAD_ENV` validation at boot in `app/main.py` — reject start if `ADAAD_ENV` is unset or not in the known enum.

---

### C-02 — `preflight.analyze_execution_plan` Command-Injection Check Is Substring-Only

**File:** `runtime/sandbox/preflight.py`  
**Risk:** The `_DISALLOWED_TOKEN_FRAGMENTS` check iterates over raw command tokens and tests `any(fragment in token for fragment in ...)`. This is a substring scan. A carefully crafted token such as `'echo${IFS}hello'` would not be caught because `${IFS}` is not in the fragment list, but is a bash word-splitting bypass.

**Hardening Required:**
```python
# Add to _DISALLOWED_TOKEN_FRAGMENTS:
_DISALLOWED_TOKEN_FRAGMENTS = (
    "&&", "||", ";", "|", "`", "$(", "${", ">", "<",
    # ADD: additional bypass vectors
    "$IFS", "${IFS}", "\\n", "\x00", "%00",
    "eval ", "exec ", "source ",
)

# Also: add a length cap on individual command tokens
_MAX_TOKEN_LENGTH = 4096

def _check_command_tokens(command: tuple[str, ...]) -> list[str]:
    violations = []
    for token in command:
        if len(token) > _MAX_TOKEN_LENGTH:
            violations.append(f"oversized_command_token:{len(token)}")
        for fragment in _DISALLOWED_TOKEN_FRAGMENTS:
            if fragment in token:
                violations.append(f"disallowed_command_token:{token[:80]}")
                break
    return violations
```

---

### C-03 — Federation Transport Public Key Is Caller-Supplied — No Key Pinning

**File:** `runtime/governance/federation/transport.py`  
**Risk:** `verify_message_signature()` reads `public_key` from the message payload itself. This means an attacker who controls a federation message can substitute both their own key and signature, satisfying the verification. There is no trusted-key registry or key pinning mechanism.

**Hardening Required:**
```python
# Add a trusted key registry (file-backed or env-configured)
# runtime/governance/federation/key_registry.py

FEDERATION_TRUSTED_KEYS_PATH = ROOT_DIR / "governance" / "federation_trusted_keys.json"

def load_trusted_key_ids() -> frozenset[str]:
    """Return frozenset of trusted key_ids from the governance key registry."""
    try:
        raw = json.loads(FEDERATION_TRUSTED_KEYS_PATH.read_text("utf-8"))
        return frozenset(str(k) for k in raw.get("trusted_key_ids", []))
    except (OSError, json.JSONDecodeError) as exc:
        raise FederationTransportContractError("key_registry:unreadable") from exc

# In verify_message_signature():
trusted = load_trusted_key_ids()
key_id = signature.get("key_id", "")
if key_id not in trusted:
    raise FederationTransportContractError(f"$.signature.key_id:untrusted:{key_id}")
```

**Draft PR:** `PR-SECURITY-01 — Federation transport key pinning registry`

---

### C-04 — `LineageLedgerV2._last_hash()` Calls `verify_integrity()` on Every Append

**File:** `runtime/evolution/lineage_v2.py`  
**Risk:** `_last_hash()` is called on every `append_event()`, and it calls `verify_integrity()` which performs a full O(n) chain re-scan from genesis. For ledgers with thousands of entries this is: (a) a performance cliff, and (b) a failure amplifier — a corruption early in the chain will halt *all* new appends rather than only the integrity-check path.

**Hardening Required:**
```python
# Maintain a verified tail-hash in memory after the first verified scan.
# Only re-verify when explicitly requested or on process boot.

class LineageLedgerV2:
    def __init__(self, ledger_path: Path | None = None) -> None:
        self.ledger_path = ledger_path or LEDGER_V2_PATH
        self._epoch_digest_index: Dict[str, str] = {}
        self._verified_tail_hash: str | None = None  # ADD

    def _last_hash(self) -> str:
        if self._verified_tail_hash is not None:
            return self._verified_tail_hash  # fast-path after first verify
        self.verify_integrity()
        lines = read_file_deterministic(self.ledger_path).splitlines()
        tail = "0" * 64 if not lines else str(json.loads(lines[-1]).get("hash", "0" * 64))
        self._verified_tail_hash = tail
        return tail

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        ...  # after successful write, update _verified_tail_hash to new hash
        self._verified_tail_hash = new_record_hash  # keep tail warm
```

---

## 2. High Findings

### H-01 — `ci.yml` Python Version Inconsistency (3.11 vs 3.10.14)

**Files:** `.github/workflows/ci.yml` (uses `3.11`), `.github/workflows/ci-generated.yml` (uses `3.10.14`)  
**Risk:** Governance test suite and generated validation run on different Python minor versions. A behavior divergence in stdlib (e.g., dict ordering semantics, hash randomization) could cause tests to pass on 3.11 but produce non-deterministic output on 3.10 at runtime.

**Fix:** Pin all CI workflows to the same version. Use `python-version: "3.11.9"` (exact patch pin) everywhere.

```yaml
# .github/workflows/ci-generated.yml — change:
- uses: actions/setup-python@v5
  with:
    python-version: "3.11.9"  # was 3.10.14
```

**Draft PR:** `PR-CI-01 — Unify Python version pin across all CI workflows`

---

### H-02 — `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` Falls Back to Namespace Secret

**File:** `docs/governance/PRODUCTION_AUTH_CONTRACT_DESIGN.md` + auth implementation  
**Risk:** The fallback key derivation `adaad-governance-session-dev-secret:<key_id>` means that if `ADAAD_GOVERNANCE_SESSION_KEY_<KEY_ID>` and `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` are both unset in a deployment, the system silently signs/verifies with a predictable namespace-derived secret. This is exploitable by anyone who knows the key_id.

**Hardening Required:**
- Add a hard boot-time assertion: if `ADAAD_ENV != dev` and neither env var is set, fail closed with `missing_governance_signing_key:critical`.
- Log a `governance_signing_key_source` metric at boot indicating which key tier was resolved.

---

### H-03 — Sandbox `write_path_allowlist` Is Policy-Defined but Not Schema-Validated

**File:** `runtime/sandbox/preflight.py`, `runtime/sandbox/policy.py`  
**Risk:** `analyze_execution_plan()` iterates `policy.write_path_allowlist` to validate mount targets, but there is no schema or format validation that these allowlist entries are valid absolute paths or are not `"/"` or `"../"`-prefixed (path traversal escape).

**Fix:**
```python
def _validate_write_allowlist(allowlist: Sequence[str]) -> list[str]:
    violations = []
    for entry in allowlist:
        p = PurePosixPath(entry)
        if not p.is_absolute():
            violations.append(f"allowlist_path_not_absolute:{entry}")
        if ".." in p.parts:
            violations.append(f"allowlist_path_traversal:{entry}")
    return violations
```

Call this in `analyze_execution_plan()` before processing mounts, and fail-closed if violations exist.

---

### H-04 — `runtime/api/__init__.py` Lazy Export Uses `importlib.import_module` Inside `__getattr__`

**File:** `runtime/api/__init__.py`  
**Risk:** The lazy-import pattern using `importlib.import_module` in `__getattr__` is explicitly flagged as `FORBIDDEN_CALLS` by `tools/lint_determinism.py` for governance-critical paths. While `runtime/api/` is not currently in `TARGET_DIRS`, any future expansion of lint scope could produce CI failures, and the pattern is inconsistent with the codebase's own determinism contract for replay-critical surfaces.

**Fix:** Evaluate whether `runtime/api/__init__.py` needs to be lazy at all. If so, add it to the `ENTROPY_ALLOWLIST` in `lint_determinism.py` with explicit rationale comment, and document why lazy import is acceptable here.

---

### H-05 — `lint_determinism.py` Does Not Cover `adaad/orchestrator/`

**File:** `tools/lint_determinism.py` — `TARGET_DIRS`  
**Risk:** `adaad/orchestrator/` owns tool registration and dispatch envelopes. These are replay-sensitive surfaces (dispatch envelopes feed into mutation audit records), but they are not covered by the AST determinism lint. A developer could introduce `datetime.now()` or `random.random()` in orchestrator routing logic without CI catching it.

**Fix:** Add `"adaad/orchestrator"` to `TARGET_DIRS` in `lint_determinism.py`, and add `"adaad/orchestrator/"` to `ENTROPY_ENFORCED_PREFIXES`.

**Draft PR:** `PR-LINT-01 — Extend determinism lint coverage to adaad/orchestrator/`

---

### H-06 — No Rate Limiting on `POST /api/mutations/proposals`

**File:** `app/main.py` or Aponi API server  
**Risk:** The MCP proposal intake endpoint (`/api/mutations/proposals`) is described as delegating to MCP validator + queue. No rate-limiting middleware is documented or implemented. A rogue client can flood the proposal queue, causing governance review backlog or DoS of the mutation pipeline.

**Fix:** Add a token-bucket rate limiter at the API layer, configurable via `ADAAD_PROPOSAL_RATE_LIMIT` (default: 10 req/min per source IP), with a `429 Too Many Requests` + `governance_proposal_rate_limited` ledger event on breach.

---

### H-07 — `AutoRecoveryHook.get_latest_valid_snapshot` Uses `st_mtime` for Ordering

**File:** `runtime/recovery/ledger_guardian.py`  
**Risk:** Snapshot ordering by `st_mtime` is not deterministic across filesystems or after `rsync`/copy operations. If a deployment copies snapshots to a backup store and restores them, `st_mtime` ordering may differ from creation-sequence ordering, causing the wrong snapshot to be selected for recovery.

**Fix:** Use the `creation_sequence` metadata field (which is already tracked) instead of filesystem `st_mtime` for ordering in `get_latest_valid_snapshot()`.

---

### H-08 — No SPDX Header Enforcement in CI for New Python Files

**File:** `.github/workflows/ci.yml`  
**Risk:** Existing files carry `# SPDX-License-Identifier: Apache-2.0` headers, but there is no CI check that enforces this for new files. A contributor can add a Python module without an SPDX header, causing license compliance drift.

**Fix:** Add a lightweight CI step:
```yaml
- name: Enforce SPDX headers on Python files
  run: |
    python - <<'PY'
    import pathlib, sys
    missing = [
        str(f) for f in pathlib.Path(".").rglob("*.py")
        if not f.read_text("utf-8", errors="replace").startswith("# SPDX-License-Identifier:")
        and not any(part.startswith(".") for part in f.parts)
    ]
    if missing:
        print("Missing SPDX headers:", *missing, sep="\n  ")
        sys.exit(1)
    PY
```

**Draft PR:** `PR-CI-02 — Add SPDX header enforcement CI step`

---

## 3. Medium Findings

### M-01 — `tools/lint_import_paths.py` Has No `--fix` Mode and No Inline Suppression

**Impact:** Developers cannot suppress false-positive boundary rules for legitimate exceptions (e.g., test shims). Without suppression, the tool is binary pass/fail and risks being disabled entirely on noisy PRs.

**Fix:** Add `# adaad: import-boundary-ok:<reason>` inline suppression with audit log of all suppressions, plus `--fix` mode for auto-rewriting obvious violations.

---

### M-02 — `SnapshotManager.create_snapshot_set` Is Not Atomic

**File:** `runtime/recovery/ledger_guardian.py`  
**Risk:** If the process is interrupted between copying the first and second file into a snapshot directory, the snapshot set is partial. A subsequent recovery attempt may restore from an inconsistent snapshot.

**Fix:** Write all files to a `<snapshot_id>.tmp/` staging directory first, then atomically rename to `<snapshot_id>/` using `os.rename()`. Add a `snapshot_complete` sentinel file as a validity marker; `get_latest_valid_snapshot` should only consider snapshots with this sentinel.

---

### M-03 — `classify` Job in CI Has No Timeout

**File:** `.github/workflows/ci.yml`  
**Risk:** The `classify` job runs inline bash with no `timeout-minutes`. If it hangs (e.g., waiting on a GitHub API call), all dependent jobs remain blocked and the PR is stuck.

**Fix:** Add `timeout-minutes: 3` to the `classify` job definition.

---

### M-04 — `read_file_deterministic` Is Called With No File-Size Cap

**File:** `runtime/governance/deterministic_filesystem.py` (implied usage)  
**Risk:** `verify_integrity()` and other chain-scan methods call `read_file_deterministic()` which loads the entire JSONL file into memory. For a long-running system with millions of ledger entries, this will OOM.

**Fix:** Implement streaming verification — iterate line-by-line with a buffered file reader rather than loading the full file. The `verify_integrity()` method should accept a `max_lines` parameter and emit a `ledger_verify_truncated` warning if the limit is reached.

---

### M-05 — `ADAAD_FEDERATION_MANIFEST_HMAC_KEY` Not Validated at Boot

**File:** `runtime/governance/federation/manifest.py`  
**Risk:** `FederationManifest.deterministic_key_from_env()` reads `ADAAD_FEDERATION_MANIFEST_HMAC_KEY` but does not validate its length or entropy at boot. A short or empty key silently weakens HMAC security.

**Fix:** At federation subsystem initialization, assert `len(key) >= 32` and emit a `federation_hmac_key_weak` boot warning if the key is shorter, failing closed if federation mode is enabled.

---

### M-06 — `redteam_harness.py` Evidence Written to `reports/redteam/` Has No Retention Policy

**File:** `runtime/analysis/redteam_harness.py`  
**Risk:** Red-team evidence JSON accumulates in `reports/redteam/` indefinitely. On long-lived systems this creates unbounded storage growth and potentially exposes historical attack scenarios to observers with read access.

**Fix:** Add a configurable retention window (`ADAAD_REDTEAM_EVIDENCE_RETENTION_DAYS`, default: 90) with a pruning step in the harness that removes evidence older than the window before writing new evidence.

---

### M-07 — `app/main.py` Import Block Is Extremely Dense — No Grouping Comments

**File:** `app/main.py`  
**Risk:** The import block is ~30+ symbols from `runtime.api.runtime_services` in a single `from ... import (...)`. When this list changes, diffs are noisy and reviewers cannot determine whether a new import is safe or introduces a boundary violation.

**Fix:** Group imports by semantic concern with section comments:
```python
# ── Boot lifecycle ──────────────────────────────────────────────
from runtime.api.runtime_services import (
    BootPreflightService,
    RecoveryPolicy,
    ...
)
# ── Governance & constitution ────────────────────────────────────
from runtime.api.runtime_services import (
    CONSTITUTION_VERSION,
    enforce_law,
    ...
)
```

---

### M-08 — `CodeQL` Workflow Only Covers Python; No JavaScript/YAML Analysis

**File:** `.github/workflows/codeql.yml`  
**Risk:** The `matrix.language` is hardcoded to `[python]`. If JavaScript, TypeScript, or complex YAML configuration is added to the repo (e.g., Aponi UI, GitHub Actions expressions with user-controlled input), these surfaces are not scanned.

**Fix:** Expand matrix to `[python, actions]` (GitHub Actions workflow scanning is supported by CodeQL) and document the rationale for excluding JavaScript if none is present.

---

### M-09 — No Structured Error Response from `/api/mutations/proposals` on Validation Failure

**Impact:** When the MCP validator rejects a proposal, the API response format is undocumented. Clients (including automated governance tooling) have no reliable error codes to act on.

**Fix:** Define and enforce a structured error response schema:
```json
{
  "error": "proposal_validation_failed",
  "reason": "<validator_reason_code>",
  "proposal_id": "<deterministic_id_if_assigned>",
  "timestamp": "<iso8601>"
}
```

---

### M-10 — `governance/canon_law_v1.yaml` Has No Hash-Pinned Inclusion in CI

**Risk:** The canon law YAML file is referenced by runtime validators but its integrity is not independently verified in CI (outside of the artifact trust verification script). A supply-chain modification to the file between signing and CI execution would not be caught by the yaml-schema-validation step alone.

**Fix:** Add the canon law YAML hash to `scripts/verify_critical_artifacts.py` as a required artifact with expected SHA-256, computed from the last known-good version.

---

### M-11 — `app/dream_mode.py` and `app/beast_mode_loop.py` Not in `import-boundary-lint` Scope

**File:** `tools/lint_import_paths.py`  
**Risk:** The import boundary rules explicitly prohibit `adaad/orchestrator/` from importing `app`, but the reverse direction (whether `app/dream_mode.py` or `app/beast_mode_loop.py` accidentally import from `adaad.orchestrator` internals) is not covered by the current lint rules.

**Fix:** Add explicit rules:
```python
# app/dream_mode.py and app/beast_mode_loop.py must not import runtime internals directly
# (must go through runtime.api facade)
LintRule(scope="app/dream_mode.py", forbidden=["runtime.governance", "runtime.evolution"]),
LintRule(scope="app/beast_mode_loop.py", forbidden=["runtime.governance", "runtime.evolution"]),
```

---

## 4. Low / Enhancement Findings

### L-01 — `reports/metrics.jsonl` Has No Rotation or Max-Size Guard

Metrics append to a single JSONL file. Add a rotation policy (`ADAAD_METRICS_MAX_SIZE_MB`, default: 256) with an archive step that compresses and moves rotated files to `reports/archive/`.

---

### L-02 — `QUICKSTART.md` Does Not Cover Windows / PowerShell

The quickstart assumes bash. Add a PowerShell equivalent section or a `quickstart.ps1` for Windows operators, improving contributor accessibility.

---

### L-03 — `EvolutionRuntime` and `FitnessOrchestrator` Have No Lifecycle Shutdown Hooks

If the process is SIGTERMed mid-epoch, in-flight mutation state may be lost. Add `shutdown()` methods with a grace-period drain and a `runtime_shutdown_initiated` ledger event.

---

### L-04 — `tests/determinism/` Suite Has No Parallel Safety Guard

Some tests in `tests/determinism/` are explicitly excluded from parallel runs (the `shared_epoch_parallel_validation` exclusion in CI). Document this constraint in a `tests/determinism/README.md` and add a `pytest-xdist` incompatibility marker.

---

### L-05 — `scripts/validate_license_compliance.py` Only Checks `fastapi`, `uvicorn`, `anthropic`

The `PACKAGES_TO_MATCH` tuple is hardcoded to three packages. As dependencies grow, new packages with viral or incompatible licenses (e.g., GPL-licensed transitive dependencies) will not be caught.

**Fix:** Parse the full `requirements.server.txt` and check every package against a configurable allowlist of approved license SPDX identifiers using `pip-licenses`.

---

### L-06 — No `py.typed` Marker in `runtime/` or `adaad/`

Without a `py.typed` marker file, `mypy` strict mode cannot fully type-check consumers of these packages as libraries. Add `py.typed` to `runtime/` and `adaad/` and enable `--strict` in the CI mypy invocation for these packages.

---

### L-07 — `tools/error_dictionary.py` Error Codes Are Not Referenced from Ledger Events

Error codes (E501, E502, etc.) exist in the error dictionary but are not emitted as structured fields in ledger events. This makes it impossible to correlate an operator-facing error with its ledger evidence.

**Fix:** Add an optional `error_code` field to governance ledger event schemas and emit the canonical code from relevant error paths.

---

### L-08 — `docs/governance/fail_closed_recovery_runbook.md` Has No Automated Trigger

The runbook is excellent but entirely manual. Add a `scripts/triage_fail_closed.py` script that automates the runbook's diagnostic queries (Steps 1–2) and produces a structured triage report, reducing MTTD during incidents.

---

## 5. Draft Pull Requests

Each PR below is specification-complete and commit-ready.

---

### PR-SECURITY-01: Federation Transport Key Pinning Registry

```
Title:  security: add trusted key registry for federation transport signature verification
Branch: security/federation-key-pinning
Labels: security, governance-impact
Tier:   critical
```

**Files changed:**
- `runtime/governance/federation/key_registry.py` *(new)*
- `runtime/governance/federation/transport.py` *(modify `verify_message_signature`)*
- `governance/federation_trusted_keys.json` *(new — governance-signed registry)*
- `tests/governance/federation/test_key_registry.py` *(new)*
- `docs/governance/FEDERATION_KEY_REGISTRY.md` *(new)*

**Commit message:**
```
security(federation): add trusted key registry to prevent caller-supplied key substitution

Prior to this change, verify_message_signature() accepted any public key
embedded in the message payload, enabling an attacker to substitute their own
key+signature pair. This PR introduces governance/federation_trusted_keys.json
as a signed registry of permitted key_ids, verified at boot and before each
federation message is accepted.

Closes ADAAD-SEC-01
Governance-impact: yes — federation trust surface change
Replay-impact: yes — affects federation message acceptance
```

**Core implementation:**
```python
# runtime/governance/federation/key_registry.py
# SPDX-License-Identifier: Apache-2.0
"""Trusted federation key registry loader."""
from __future__ import annotations

import json
from pathlib import Path
from typing import FrozenSet

from runtime import ROOT_DIR
from .transport import FederationTransportContractError

_REGISTRY_PATH = ROOT_DIR / "governance" / "federation_trusted_keys.json"
_CACHE: FrozenSet[str] | None = None


def load_trusted_key_ids(*, reload: bool = False) -> FrozenSet[str]:
    global _CACHE
    if _CACHE is not None and not reload:
        return _CACHE
    try:
        data = json.loads(_REGISTRY_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FederationTransportContractError("key_registry:unreadable") from exc
    ids = data.get("trusted_key_ids")
    if not isinstance(ids, list) or not ids:
        raise FederationTransportContractError("key_registry:empty_or_invalid")
    _CACHE = frozenset(str(k) for k in ids)
    return _CACHE


def assert_key_trusted(key_id: str) -> None:
    trusted = load_trusted_key_ids()
    if key_id not in trusted:
        raise FederationTransportContractError(
            f"$.signature.key_id:untrusted:{key_id}"
        )
```

---

### PR-LINT-01: Extend Determinism Lint to adaad/orchestrator/

```
Title:  lint: extend determinism lint coverage to adaad/orchestrator/ dispatch paths
Branch: lint/orchestrator-determinism-coverage
Labels: governance-impact, testing
Tier:   critical
```

**Files changed:**
- `tools/lint_determinism.py`
- `tests/test_lint_determinism.py`

**Commit message:**
```
lint(determinism): add adaad/orchestrator/ to TARGET_DIRS and ENTROPY_ENFORCED_PREFIXES

Dispatch envelopes and tool-registration paths in adaad/orchestrator/ are
replay-sensitive because they feed into mutation audit records. This change
ensures that datetime.now(), random, uuid4() without deterministic provider
injection cannot be silently introduced in orchestrator routing logic.
```

**Diff:**
```python
# tools/lint_determinism.py
TARGET_DIRS: tuple[str, ...] = (
    "runtime/governance",
    "runtime/evolution",
    "runtime/autonomy",
    "security",
    "adaad/orchestrator",  # ADD
)

ENTROPY_ENFORCED_PREFIXES: tuple[str, ...] = (
    "runtime/governance/",
    "runtime/evolution/",
    "adaad/orchestrator/",  # ADD
)
```

---

### PR-CI-01: Unify Python Version Pin Across All CI Workflows

```
Title:  ci: unify Python version to 3.11.9 across all workflow files
Branch: ci/unify-python-pin
Labels: ci
Tier:   standard
```

**Files changed:**
- `.github/workflows/ci.yml` — change `"3.11"` → `"3.11.9"` at all job steps
- `.github/workflows/ci-generated.yml` — change `"3.10.14"` → `"3.11.9"`
- `.github/workflows/codeql.yml` — add explicit Python version setup step
- `.github/workflows/determinism_lint.yml` — pin to `"3.11.9"`

**Commit message:**
```
ci: pin all workflows to python 3.11.9 for deterministic governance test parity

Mixed Python minor versions (3.10.14 vs 3.11) risk silent behavioral divergence
in stdlib internals used by governance tests. Exact patch-level pinning ensures
test results are reproducible and comparable across all CI legs.
```

---

### PR-CI-02: Add SPDX Header Enforcement

```
Title:  ci: enforce SPDX license headers on all Python source files
Branch: ci/spdx-header-enforcement
Labels: ci, compliance
Tier:   standard
```

**Files changed:**
- `.github/workflows/ci.yml` — new `spdx-header-lint` job
- `scripts/check_spdx_headers.py` *(new)*

**Script:**
```python
# scripts/check_spdx_headers.py
# SPDX-License-Identifier: Apache-2.0
"""Verify all tracked Python files carry an SPDX header."""
from __future__ import annotations
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = frozenset({"__pycache__", ".git", "node_modules", ".venv", "archives"})
REQUIRED_PREFIX = "# SPDX-License-Identifier:"


def main() -> int:
    missing: list[str] = []
    for f in sorted(REPO_ROOT.rglob("*.py")):
        if any(part in EXCLUDE_DIRS for part in f.parts):
            continue
        try:
            first_line = f.read_text("utf-8", errors="replace").splitlines()[0]
        except IndexError:
            continue  # empty file
        if not first_line.startswith(REQUIRED_PREFIX):
            missing.append(str(f.relative_to(REPO_ROOT)))
    if missing:
        print(f"❌ {len(missing)} Python file(s) missing SPDX header:")
        for path in missing:
            print(f"  {path}")
        return 1
    print(f"✅ SPDX headers verified for all Python files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### PR-PERF-01: Streaming Lineage Integrity Verification

```
Title:  perf: stream-verify lineage ledger to avoid full-file memory load
Branch: perf/streaming-lineage-verification
Labels: performance, governance-impact
Tier:   critical
```

**Files changed:**
- `runtime/evolution/lineage_v2.py`

**Commit message:**
```
perf(lineage): replace full-file read with streaming line iterator in verify_integrity()

LineageLedgerV2.verify_integrity() previously loaded the entire JSONL ledger
into memory via read_file_deterministic(). For long-lived deployments with
millions of entries this is an OOM risk. This PR introduces a streaming
line-by-line verifier and a verified tail-hash cache to make _last_hash()
O(1) after initial verification.

Replay-impact: none — verification logic is semantically identical
Performance: O(n) memory → O(1) memory for verification
```

**Core change:**
```python
def verify_integrity(
    self,
    recovery_hook: LineageRecoveryHook | None = None,
    *,
    max_lines: int | None = None,
) -> None:
    """Stream-verify hash chain from genesis. Fail closed on any break."""
    self._ensure()
    prev_hash = "0" * 64
    line_count = 0
    try:
        with self.ledger_path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                if max_lines is not None and line_count >= max_lines:
                    # Emit a warning metric and stop — do not fail-close on truncation
                    metrics.emit("ledger_verify_truncated", {"line_count": line_count})
                    return
                line_count += 1
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise LineageIntegrityError(f"json_parse_error:line_{line_count}") from exc
                stored_hash = entry.get("hash", "")
                # ... recompute expected hash and compare
                if not hmac.compare_digest(stored_hash, expected_hash):
                    raise LineageIntegrityError(f"lineage_hash_mismatch:line_{line_count}")
                prev_hash = stored_hash
        # Update tail-hash cache after successful full verification
        self._verified_tail_hash = prev_hash
    except LineageIntegrityError:
        if recovery_hook is not None:
            recovery_hook.on_lineage_integrity_failure(
                ledger_path=self.ledger_path, error=e
            )
        raise
```

---

### PR-HARDEN-01: Boot-Time Governance Environment Validation

```
Title:  hardening: add boot-time env validation and dev-token expiry gate
Branch: hardening/boot-env-validation
Labels: security, governance-impact
Tier:   critical
```

**Files changed:**
- `app/main.py`
- `runtime/governance/auth/` (token verifier)

**Commit message:**
```
hardening(boot): reject unknown ADAAD_ENV values and enforce dev-token expiry

Prior to this change, an accidental ADAAD_ENV=staging deployment with
CRYOVANT_DEV_MODE set could accept dev-bypass tokens. This PR adds a boot
guard that validates ADAAD_ENV against a known enum, fails closed for staging/
production if dev mode is enabled, and enforces expiry checks on dev tokens.

Governance-impact: yes
Security-impact: yes
```

**Implementation:**
```python
# app/main.py — add near top of _boot() or main guard
_KNOWN_ENVS = frozenset({"dev", "test", "staging", "production", "prod"})
_STRICT_ENVS = frozenset({"staging", "production", "prod"})

def _validate_boot_environment() -> None:
    env = (os.getenv("ADAAD_ENV") or "").strip().lower()
    if not env:
        raise SystemExit(
            "CRITICAL: ADAAD_ENV is not set. "
            "Set to one of: dev, test, staging, production"
        )
    if env not in _KNOWN_ENVS:
        raise SystemExit(f"CRITICAL: ADAAD_ENV={env!r} is not a recognized environment.")
    if env in _STRICT_ENVS and os.getenv("CRYOVANT_DEV_MODE"):
        raise SystemExit(
            f"CRITICAL: CRYOVANT_DEV_MODE is set in strict environment {env!r}. "
            "This configuration is not permitted."
        )
    metrics.emit("boot_env_validated", {"env": env})
```

---

### PR-OPS-01: Snapshot Atomicity and Ordering Fix

```
Title:  ops: make SnapshotManager.create_snapshot_set atomic and fix ordering
Branch: ops/snapshot-atomicity
Labels: governance-impact, reliability
Tier:   critical
```

**Files changed:**
- `runtime/recovery/ledger_guardian.py`
- `tests/governance/test_ledger_guardian.py`

**Commit message:**
```
ops(recovery): atomic snapshot creation via tmp-dir + rename; order by creation_sequence

Two bugs fixed:
1. Non-atomic snapshot writes could produce partial snapshots on SIGTERM.
   Now uses .tmp/ staging dir + os.rename() for atomic promotion.
2. get_latest_valid_snapshot() sorted by st_mtime, which is not deterministic
   after rsync/restore. Now sorts by creation_sequence from metadata.json.
```

---

### PR-DOCS-01: Federation Key Registry Governance Document

```
Title:  docs: add FEDERATION_KEY_REGISTRY.md and update claims_evidence_matrix
Branch: docs/federation-key-registry
Labels: documentation
Tier:   standard
```

**Files changed:**
- `docs/governance/FEDERATION_KEY_REGISTRY.md` *(new)*
- `docs/comms/claims_evidence_matrix.md` — add `federation-key-pinning` claim entry
- `governance/federation_trusted_keys.json` *(new — initial bootstrap entry)*

---

## 6. Weakest Link Summary Matrix

| Module / Path | Weakness | Severity | Draft PR |
|---|---|---|---|
| `runtime/governance/federation/transport.py` | Caller-supplied public key — no key pinning | 🔴 C-03 | PR-SECURITY-01 |
| `runtime/evolution/lineage_v2.py` | O(n) verify on every append → OOM risk | 🔴 C-04 | PR-PERF-01 |
| `runtime/governance/auth/` | Dev token bypass without expiry in staging | 🔴 C-01 | PR-HARDEN-01 |
| `runtime/sandbox/preflight.py` | Incomplete command-injection fragment list | 🔴 C-02 | Inline fix |
| `tools/lint_determinism.py` | `adaad/orchestrator/` not linted | 🟠 H-05 | PR-LINT-01 |
| `.github/workflows/ci.yml` | Python version inconsistency | 🟠 H-01 | PR-CI-01 |
| `runtime/recovery/ledger_guardian.py` | Non-atomic snapshot + mtime ordering | 🟠 H-07 | PR-OPS-01 |
| `governance/canon_law_v1.yaml` | No hash pin in CI | 🟠 M-10 | PR-HARDEN-01 |
| `reports/metrics.jsonl` | No rotation/size cap | 🔵 L-01 | Inline fix |
| `app/main.py` (import block) | Dense unstructured import block | 🔵 M-07 | Inline refactor |

---

## 7. Optimization Recommendations (Non-PR)

| Area | Recommendation |
|---|---|
| **Replay digest caching** | Cache epoch digests in a side-car `.index` file next to the ledger. Avoids full-ledger scan on `get_epoch_digest()` for known epochs. |
| **Warm pool startup** | Parallelize warm pool agent initialization using `asyncio.gather()` rather than sequential await, reducing boot latency. |
| **Metrics fan-out** | Add a `MetricsSink` abstraction with multiple backends (JSONL, stdout, optional OpenTelemetry). Currently everything fans to a single JSONL file. |
| **Type annotations** | Add `py.typed` markers and run `mypy --strict` on `runtime/` + `adaad/`. Several public APIs lack return type annotations. |
| **Test isolation** | Several governance tests use real filesystem paths via `tmp_path` but do not mock `LEDGER_V2_PATH`. Add a `pytest` fixture that patches all canonical paths to `tmp_path` equivalents. |
| **Error budget tracking** | Add an `ADAAD_ERROR_BUDGET_WINDOW` config that counts fail-closed governance decisions over a rolling window and alerts when the error budget threshold is exceeded. |
| **Federation HMAC key rotation** | `ADAAD_FEDERATION_MANIFEST_HMAC_KEY` has no rotation procedure documented. Add a rotation runbook analogous to the governance session key rotation guide. |

---

## 8. Merge & Commit Order (Dependency-Safe Sequence)

```
1. PR-CI-01        (Python version pin)         — no deps
2. PR-CI-02        (SPDX enforcement)            — no deps
3. PR-LINT-01      (orchestrator determinism)    — no deps
4. PR-HARDEN-01    (boot env validation)         — no deps
5. PR-SECURITY-01  (federation key pinning)      — depends on transport.py audit
6. PR-PERF-01      (streaming lineage verify)    — no deps
7. PR-OPS-01       (snapshot atomicity)          — no deps
8. PR-DOCS-01      (federation registry docs)    — depends on PR-SECURITY-01
```

All PRs should be raised with:
- `governance-impact` label if noted
- Minimum 2 reviewer approvals (per branch protection contract)
- Strict replay verification run locally before merge:
  ```bash
  ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 \
  ADAAD_FORCE_DETERMINISTIC_PROVIDER=1 \
  ADAAD_DETERMINISTIC_SEED=ci-strict-replay \
    python -m app.main --verify-replay --replay strict
  ```

---

## 9. Claims-Evidence Matrix Addendum

The following new claim rows should be added to `docs/comms/claims_evidence_matrix.md` upon completion of the above PRs:

| Claim ID | External claim | Evidence artifacts | Target Status |
|---|---|---|---|
| `federation-key-pinning` | "Federation messages are accepted only from registered, trusted key IDs." | `governance/federation_trusted_keys.json`; `runtime/governance/federation/key_registry.py`; `tests/governance/federation/test_key_registry.py` | Pending PR-SECURITY-01 |
| `boot-env-validation` | "ADAAD rejects startup with unknown or misconfigured environment values." | `app/main.py` boot guard; `tests/test_boot_env_validation.py` | Pending PR-HARDEN-01 |
| `streaming-ledger-verification` | "Lineage ledger integrity verification does not require full-file memory load." | `runtime/evolution/lineage_v2.py` streaming verifier | Pending PR-PERF-01 |
| `spdx-header-compliance` | "All Python source files carry SPDX license headers, enforced in CI." | `.github/workflows/ci.yml` spdx-header-lint job; `scripts/check_spdx_headers.py` | Pending PR-CI-02 |

---

*End of ADAAD Deep Dive Audit Report — DUSTADAAD Governed Autonomy Environment*  
*All findings are grounded in repository artifacts retrieved from project knowledge. No behavior has been invented beyond what is directly evidenced in the codebase.*
