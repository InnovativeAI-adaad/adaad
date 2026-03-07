# ADAAD — Quick Start

> **First time?** Just run: `python onboard.py` — it handles everything.

---

## One command

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python onboard.py
```

`onboard.py` sets up your environment, validates governance schemas, and runs a governed dry-run. No manual steps required.

---

## What success looks like

```
  ✔ Python 3.11.9
  ✔ Virtual environment ready
  ✔ Dependencies installed
  ✔ ADAAD_ENV=dev
  ✔ Workspace initialized
  ✔ Governance schemas valid
  ✔ Dry-run complete — no files modified

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ADAAD is ready.

  Run the dashboard:   python server.py
  Run an epoch:        python -m app.main --verbose
  Architecture docs:   docs/EVOLUTION_ARCHITECTURE.md
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Manual setup (fallback when `python onboard.py` is unavailable)

```bash
# 1. Environment
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.server.txt

# 2. Configure
export ADAAD_ENV=dev

# 3. Initialize
python nexus_setup.py

# 4. Verify
python -m app.main --dry-run --replay audit --verbose
```

---

## Run modes

| Command | What it does |
|---|---|
| `python -m app.main --dry-run --replay audit` | Safe first run — no files modified |
| `python -m app.main --verbose` | Full run with detailed logging |
| `python -m app.main --replay strict --verbose` | Strict determinism verification |
| `python server.py` | Start the Aponi dashboard at `localhost:8000` |

---

## Hermetic / CI mode

```bash
export ADAAD_FORCE_DETERMINISTIC_PROVIDER=1
export ADAAD_DETERMINISTIC_SEED=ci-seed
export ADAAD_DISABLE_MUTABLE_FS=1
export ADAAD_DISABLE_NETWORK=1
python -m app.main --replay audit
```

---

## Dashboard

```bash
python server.py --host 0.0.0.0 --port 8000
```

- UI: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/api/health`

---

## Environment variables

| Variable | Purpose | Required |
|---|---|---|
| `ADAAD_ENV` | `dev` · `test` · `staging` · `production` | Always |
| `ADAAD_CLAUDE_API_KEY` | Anthropic key for AI mutation proposals | AI mode |
| `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` | HMAC key for session tokens | Strict envs |
| `CRYOVANT_DEV_MODE` | Dev-only overrides (rejected in strict envs) | Never in prod |

Full reference: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | Re-activate venv: `source .venv/bin/activate` |
| `ADAAD_ENV is not set` | `export ADAAD_ENV=dev` |
| Replay fails on first run | Normal — run audit mode first to establish baseline |
| Policy rejection in dry-run | Expected fail-closed behaviour — inspect `--verbose` output |
| Dashboard unreachable | Check server started: `curl http://127.0.0.1:8000/api/health` |

---

## Federation mode (multi-repo)

> Only needed for deployments connecting multiple ADAAD nodes. Single-repo deployments skip this entirely.

```bash
# Required: valid HMAC key material for the federation transport
export ADAAD_FEDERATION_ENABLED=true
export ADAAD_FEDERATION_HMAC_KEY=<your-key-from-secret-manager>

# Start with federation enabled
python -m app.main --verbose
```

The boot guard validates key material before any federation surface activates. Absent or undersized key → `FederationKeyError` (fail-closed). Key rotation procedure: `docs/runbooks/hmac_key_rotation.md`.

---

## Clean reset

```bash
rm -rf reports security/ledger security/replay_manifests
python onboard.py
```

---

## Next

- [Architecture](docs/EVOLUTION_ARCHITECTURE.md) — how the evolution loop works
- [Constitution](docs/CONSTITUTION.md) — governance rules
- [Contributing](CONTRIBUTING.md) — how to contribute
- [Security](docs/SECURITY.md) — key handling and threat model
