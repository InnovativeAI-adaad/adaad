# ADAAD — Termux Setup Guide

**v7.0.0 · Run the full ADAAD governance server on Android via Termux**

> Tested on Android 10+ · Termux 0.118+ · Python 3.11+

---

## Why Termux?

Termux gives you a real Linux environment on Android. You can run the ADAAD
Python governance server (`server.py`), execute epochs (`app.main`), and access
the Aponi dashboard — all locally on your device, no desktop required.

---

## Quick Start (copy-paste)

```bash
# 1. Install system dependencies
pkg update && pkg upgrade -y
pkg install python git libsodium openssl -y

# 2. Clone ADAAD
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD

# 3. Run the unified onboarder (Termux-aware)
python3 onboard.py

# 4. Set a dev soulbound key (required for ledger writes)
export ADAAD_SOULBOUND_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export ADAAD_ENV=dev

# 5. Start the dashboard
python3 server.py
# → Dashboard: http://localhost:8000
```

---

## Step-by-Step

### Step 1 — Install Termux

Install Termux from F-Droid (recommended — Play Store version is outdated):

```
https://f-droid.org → search "Termux" → Install
```

> Do **not** use the Google Play Store version of Termux. It is unmaintained
> and incompatible with current packages.

### Step 2 — System packages

```bash
pkg update && pkg upgrade -y
pkg install python git libsodium openssl -y
```

| Package | Why |
|---------|-----|
| `python` | Python 3.11+ runtime |
| `git` | Clone and update ADAAD |
| `libsodium` | Required by PyNaCl (ADAAD cryptographic primitives) |
| `openssl` | Required by cryptography / TLS |

### Step 3 — Clone ADAAD

```bash
# ADAAD is not on PyPI — install from source
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
```

> **`pip install adaad` will fail** — ADAAD is not published to PyPI.
> Always use `git clone`.

### Step 4 — Run the onboarder

```bash
python3 onboard.py
```

`onboard.py` detects Termux automatically and:
- Passes `--only-binary :all: --prefer-binary` to pip — avoids source builds that
  require a C compiler (Clang is available in Termux but binary wheels are faster)
- Prints recovery instructions if any native dependency fails

If you see a `metadata-generation-failed` error for `PyNaCl`:

```bash
pkg install python-cryptography -y
python3 onboard.py   # retry
```

### Step 5 — Environment setup

```bash
# Soulbound key — required for Phase 9+ ledger writes
export ADAAD_SOULBOUND_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Environment tier
export ADAAD_ENV=dev

# Persist across sessions
echo 'export ADAAD_SOULBOUND_KEY=<your-key-here>' >> ~/.bashrc
echo 'export ADAAD_ENV=dev' >> ~/.bashrc
```

> **Never commit your soulbound key.** Use `secrets.token_hex(32)` to generate
> a fresh one. In production, source from a secret manager.

### Step 6 — Start the server

```bash
python3 server.py
```

Open Chrome on your device and navigate to `http://localhost:8000`.

The Aponi governance dashboard, constitution browser, health signals, and
all REST endpoints are available locally.

To run in the background (keep terminal free):

```bash
nohup python3 server.py > server.log 2>&1 &
echo "Server PID: $!"
```

---

## Running epochs

```bash
# Single epoch
python3 -m app.main --verbose

# Strict deterministic replay
python3 -m app.main --replay strict --verbose
```

---

## Updating ADAAD

```bash
cd ~/ADAAD
git pull
python3 onboard.py   # re-runs dependency check
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `pip install adaad` fails | ADAAD is not on PyPI — use `git clone` (see Step 3) |
| `metadata-generation-failed` for PyNaCl | `pkg install python-cryptography -y` then retry |
| `libsodium` not found at runtime | `pkg install libsodium -y` |
| `fatal: destination path 'ADAAD' already exists` | `rm -rf ADAAD` then re-clone |
| Server shows deprecation warning | Update to v7.0.0+: `git pull` |
| `ui/aponi not found` at startup | `server.py` requires the Aponi UI assets — run from the ADAAD root directory |
| Dashboard blank / connection refused | Confirm server is running: `curl http://localhost:8000/api/version` |
| Permission denied on `~/.bashrc` | Use `~/.profile` instead: `echo 'export ...' >> ~/.profile` |
| Out of memory building C extension | `pkg install python-cryptography -y` replaces the source build |

---

## What works in Termux

| Feature | Status |
|---------|--------|
| `python3 server.py` (dashboard + REST API) | ✅ Full support |
| `python3 -m app.main` (epoch execution) | ✅ Full support |
| Governance health signals (9 signals) | ✅ Full support |
| All audit ledger REST endpoints | ✅ Full support |
| `pytest` test suite | ✅ Full support |
| Android APK (Aponi native app) | ✅ Separate — see `INSTALL_ANDROID.md` |

---

## Architecture note

ADAAD's Termux support runs the **server** tier only — the same Python runtime
used in production.  The Android APK (Kotlin/Compose) is a separate native
front-end that connects to this server.  You can run both simultaneously:
start `server.py` in Termux, then open the ADAAD APK pointing at `localhost:8000`.

---

*ADAAD · MIT License · InnovativeAI LLC · Blackwell, Oklahoma*
*Issues: https://github.com/InnovativeAI-adaad/ADAAD/issues — label: `android`*
