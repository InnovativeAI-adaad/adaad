# ADAAD — Quick Start

> **First time?** Just run: `python onboard.py` — it handles everything.

---

## One command

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python onboard.py
```

`onboard.py` sets up your environment, validates governance schemas, and runs a governed dry-run. No manual steps required. Safe to re-run any time.

**On Android / Termux:** See [`TERMUX_SETUP.md`](TERMUX_SETUP.md) for the complete guide.

---

## What success looks like

```
  ✔ Python 3.12.x
  ✔ Virtual environment created (.venv)
  ✔ Dependencies installed
  ✔ ADAAD_ENV=dev
  ✔ Workspace valid
  ✔ Governance schemas valid
  ✔ Dry-run complete  (fail-closed behaviour confirmed)

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ADAAD is ready.

  Run the dashboard   python server.py
  Run an epoch        adaad demo
  Inspect ledger      adaad inspect-ledger data/evolution_ledger.jsonl
  Propose mutation    adaad propose "upgrade system x"
  Strict replay       python -m app.main --replay strict --verbose
  Architecture docs   ARCHITECTURE.md
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### CLI Interface

ADAAD now includes a formal CLI. To use it, ensure `scripts/` is in your PATH or call it directly:

```bash
./scripts/adaad --help
./scripts/adaad demo
./scripts/adaad inspect-ledger <path>
./scripts/adaad propose "<description>"
```

> **Soulbound key warning** — You'll see this on first run. It's expected:
>
> ```
> ⚠  ADAAD_SOULBOUND_KEY is not set.
>    Phase 9+ soulbound ledger writes will be fail-closed without it.
>    Generate a dev key: python -c "import secrets; print(secrets.token_hex(32))"
>    export ADAAD_SOULBOUND_KEY=<your-key>
> ```
>
> For local development, generate a key and export it. For production, source from a secret manager.

---

## Manual setup (fallback)

Use this if `python onboard.py` is unavailable.

```bash
# Option A — Install from PyPI (Python ≥ 3.11, recommended)
pip install adaad

# Option B — Run from source
# 1. Virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1

# 2. Dependencies
python -m pip install --upgrade pip
pip install -r requirements.server.txt

# 3. Configure
export ADAAD_ENV=dev
export ADAAD_SOULBOUND_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# 4. Initialize workspace
python nexus_setup.py

# 5. Verify
python -m app.main --dry-run --replay audit --verbose
```

---

## Run the governance dashboard

```bash
python server.py
# → http://localhost:8000
```

The Aponi dashboard shows live governance health signals, audit ledger entries, mutation history, and constitution state.

---

## Run an epoch

```bash
# Single governed epoch
python -m app.main --verbose

# Strict deterministic replay (must set ADAAD_DETERMINISTIC_SEED)
export ADAAD_DETERMINISTIC_SEED=my-seed
python -m app.main --replay strict --verbose
```

---

## Run the test suite

```bash
# Fast targeted suite (governance + determinism)
pytest tests/governance/ tests/determinism/ -q

# Full suite
pytest tests/ -q
```

3828+ tests passing. All 20 previously-tracked failures resolved as of v7.0.0.

---

## Key environment variables

| Variable | Default | What it does |
|:---|:---|:---|
| `ADAAD_ENV` | — | Set to `dev` for local development |
| `ADAAD_SOULBOUND_KEY` | — | Required for Phase 9+ ledger writes. 32-byte hex. |
| `ADAAD_REPLAY_MODE` | `off` | Set to `strict` for byte-identical deterministic replay |
| `ADAAD_DETERMINISTIC_SEED` | — | Required when `ADAAD_REPLAY_MODE=strict` |
| `ADAAD_GATE_LOCKED` | — | Set to `1` to lock the GovernanceGate in CI |
| `ADAAD_DISPATCH_LATENCY_BUDGET_MS` | `50.0` | Dispatch latency threshold for governance audit events |

Full reference: [`docs/ENVIRONMENT_VARIABLES.md`](docs/ENVIRONMENT_VARIABLES.md)

---

## Where to go next

| Goal | Resource |
|:---|:---|
| Understand the architecture | [`docs/ARCHITECTURE_CONTRACT.md`](docs/ARCHITECTURE_CONTRACT.md) |
| Read the constitution | [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) |
| Android / Termux install | [`TERMUX_SETUP.md`](TERMUX_SETUP.md) · [`INSTALL_ANDROID.md`](INSTALL_ANDROID.md) |
| Current roadmap | [`ROADMAP.md`](ROADMAP.md) |
| Full changelog | [`CHANGELOG.md`](CHANGELOG.md) |
| Full docs index | [`docs/README.md`](docs/README.md) |
