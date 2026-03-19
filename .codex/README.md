# ADAAD — Codex Environment Reference

## Workspace Layout

| Path | Purpose |
|---|---|
| `/workspace/adaad/` | Canonical repo root (lowercase — Linux FS is case-sensitive) |
| `.codex/setup.sh` | Full bootstrap (run once on fresh containers) |
| `.codex/maintenance.sh` | Fast re-assertion (run on cache-resumed containers) |
| `.codex/preflight_stub.py` | Contract gate scaffold (promoted to `scripts/preflight.py`) |
| `.codex/setup_manifest.json` | Audit anchor: git SHA, runtime, dep hash, timestamp |
| `.codex/dep_snapshot.sha256` | SHA-256 of `pip freeze` output post-install |

## Governance Invariants

| Code | Enforcement |
|---|---|
| `INV-PATH` | Workspace resolved at runtime; never hardcoded |
| `INV-RUNTIME` | Python 3.11.x pinned; setup + maintenance both assert |
| `INV-DEP` | Dep snapshot SHA-256 recorded; drift triggers reinstall |
| `INV-PREFLIGHT` | Contract gate runs before any ADAAD execution |
| `INV-AUDIT` | Setup manifest written and updated on every container start |
| `INV-FAIL-CLOSED` | Every gate exits non-zero on failure; no silent pass-throughs |
| `INV-CONSTITUTION` | CONSTITUTION_VERSION must be present before execution |

## Codex UI Settings Checklist

```
Container image : universal
Workspace dir   : /workspace/adaad          ← lowercase, matches repo name
Setup script    : .codex/setup.sh
Maintenance     : .codex/maintenance.sh
Internet access : Common dependencies        ← pip, PyPI
HTTP methods    : GET, HEAD, OPTIONS         ← sufficient for pip install
```

## Root Cause of Original Failure

```
/tmp/4LMoJ9-setup_script.sh: line 7: cd: /workspace/ADAAD: No such file or directory
```

Codex clones to `/workspace/{repo_name}` where `repo_name` is the
**exact slug** of the repository as it appears in GitHub (case-sensitive
on Linux ext4/overlayfs). The repository slug is `adaad` (lowercase),
so the clone lands at `/workspace/adaad`. Any inline setup script that
hardcodes `/workspace/ADAAD` will fail on every fresh container.

**Fix**: resolve the path dynamically (see `setup.sh`) and set the
Codex UI "Workspace directory" field to `/workspace/adaad`.
