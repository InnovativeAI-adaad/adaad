# ADAAD — Phone Setup (Dustin's Device)

**Branch:** `device/phone-armv8l`  
**Architecture:** armv8l (32-bit ARM, Termux)

This branch is optimised for your phone. It uses pydantic v1 (pure Python) instead of pydantic v2 (requires Rust), which is what was failing.

---

## First time setup

```bash
cd ~/ADAAD
python3 onboard_phone.py
```

That's it. It will:
- Install phone-safe dependencies from `requirements.phone.txt`
- Set up your soulbound key (saved to `~/.adaad_phone.env`)
- Write `start_phone.sh`
- Validate governance schemas

---

## Every other time — start the dashboard

```bash
cd ~/ADAAD
bash start_phone.sh
```

Open **Chrome** on your phone and go to: **`http://127.0.0.1:8000`**

The Aponi governance dashboard shows health signals, audit ledger entries, and gate status.

---

## Why port 8000, not 8080?

The Aponi UI has `http://127.0.0.1:8000` hardcoded as its API base URL. Running the server on port 8080 causes the UI to show **"Backend unreachable / gate_ok=false"**. Always use port 8000 (the default, which `start_phone.sh` sets).

---

## Why can't I run `python -m app.main`?

`app.main` runs evolution epochs, which requires the `anthropic` Python package. That package depends on `jiter` (a Rust extension), and `jiter` fails to build on armv8l:

```
maturin failed
  Caused by: Unsupported Android architecture: armv8l
```

The governance **dashboard** (`server.py`) does not require `anthropic` and runs fine. Epoch execution from the phone isn't currently supported on armv8l.

---

## Why `UI is disabled until Cryovant verifies the environment`?

`CRYOVANT_DEV_MODE` wasn't set. `start_phone.sh` sets it to `1` automatically, which puts Cryovant into development pass-through mode and unlocks the UI.

---

## Update ADAAD

```bash
cd ~/ADAAD
git pull
python3 onboard_phone.py   # re-runs dependency check
```

---

## Troubleshooting

| Problem | Fix |
|:---|:---|
| `metadata-generation-failed` for pydantic-core or jiter | You're on main branch — switch to phone branch: `git checkout device/phone-armv8l` |
| `source .venv/bin/activate: No such file or directory` | Run `python3 onboard_phone.py` first — it creates the venv |
| `Address already in use` on port 8000 | A previous server is still running. Kill it: `pkill -f uvicorn` |
| Gate shows LOCKED / Backend unreachable | You're on port 8080 — use `bash start_phone.sh` not `uvicorn ... --port 8080` |
| `UI is disabled until Cryovant verifies` | Use `bash start_phone.sh` — it sets `CRYOVANT_DEV_MODE=1` |
| `No module named 'fastapi'` | Run `python3 onboard_phone.py` — it installs everything |

---

## What works on this branch

| Feature | Status |
|:---|:---|
| Governance dashboard (`server.py`) | ✅ |
| All 9 health signals (`GET /governance/health`) | ✅ |
| All audit ledger REST endpoints | ✅ |
| Mutation proposal endpoint | ✅ |
| Constitutional gate status | ✅ |
| Evolution epochs (`python -m app.main`) | ⚠️  Requires `anthropic` — fails on armv8l |
| Ed25519 replay attestation | ⚠️  Requires `pkg install python-nacl` |
| Test suite (`pytest tests/`) | ❌  Tests require pydantic v2 / starlette 0.52. Not applicable on phone branch. |

---

*ADAAD · MIT License · InnovativeAI LLC · Blackwell, Oklahoma*
