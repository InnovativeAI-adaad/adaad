# ADAADChat GitHub App — Setup Guide

## What ADAADChat already has

The server stack is **fully built and committed**:

| File | Role |
|---|---|
| `server.py` → `POST /webhook/github` | Receives GitHub webhook events |
| `app/github_app.py` | Signature verify, dispatch, governance bridge |
| `runtime/integrations/github_app_token.py` | JWT generation + installation token |
| `runtime/governance/external_event_bridge.py` | SHA-256 hash-chained audit ledger |

You need to: (1) configure the GitHub App settings page, (2) set env vars, (3) give it a public URL.

---

## Step 1 — GitHub App Settings (do this on the settings page now)

### Webhook

| Field | Value |
|---|---|
| **Webhook URL** | `https://YOUR_DOMAIN/webhook/github` (see Step 3 for how to get this) |
| **Webhook Secret** | Generate a strong secret — you will set this as `GITHUB_WEBHOOK_SECRET` |
| **Active** | ✅ checked |

### Repository Permissions

Set these on the **Permissions & Events** tab:

| Permission | Level |
|---|---|
| Contents | Read |
| Issues | Read & Write |
| Pull requests | Read & Write |
| Checks | Read |
| Metadata | Read (mandatory) |
| Commit statuses | Read |

### Subscribe to Events

Check all of these:

- ✅ Push
- ✅ Pull request
- ✅ Pull request review
- ✅ Issues
- ✅ Issue comment
- ✅ Check run
- ✅ Check suite
- ✅ Installation
- ✅ Installation repositories

### Where to install

Set to **Only on this account** (InnovativeAI-adaad org) — install on the `adaad` repo.

---

## Step 2 — Download Your Private Key

On the settings page → **Private keys** section, download the `.pem` file for the key you want to use (the more recent one: `g8brQSr3bt2r6GJyzuBlgGlxJ9mBhEFTK/WGtC931ww=`).

Save it as `security/keys/adaadchat.pem` (already gitignored).

---

## Step 3 — Get Your Installation ID

After installing the app on the repo, get the installation ID:

```bash
# Option A: from the install URL
# After install, the URL will be:
# https://github.com/apps/adaadchat/installations/XXXXXXXX
# That XXXXXXXX is your installation ID

# Option B: via API (after setting private key)
python runtime/integrations/github_app_token.py
# If ADAAD_GITHUB_APP_ID and ADAAD_GITHUB_INSTALL_ID aren't set yet,
# check the GitHub App settings page -> Install -> the install URL
```

---

## Step 4 — Environment Variables

Create `.env` in the repo root (never commit this):

```bash
# ── ADAADChat GitHub App ────────────────────────────────────────────────────
GITHUB_APP_ID=3013088
GITHUB_APP_CLIENT_ID=Iv23liYNPdEjUgXwiT8Y

# Webhook HMAC secret — must match what you set on the GitHub App settings page
GITHUB_WEBHOOK_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">

# Private key — either file path or inline PEM
ADAAD_GITHUB_KEY_PATH=security/keys/adaadchat.pem
# OR inline (useful for cloud deployments):
# ADAAD_GITHUB_KEY_PEM=-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----

# Required by github_identity_config.py
ADAAD_GITHUB_APP_ID=3013088
ADAAD_GITHUB_INSTALL_ID=<your installation ID from Step 3>

# ── Server ──────────────────────────────────────────────────────────────────
ADAAD_HOST=0.0.0.0
ADAAD_PORT=8080
ADAAD_ENV=production

# ── Governance audit fallback log ────────────────────────────────────────────
ADAAD_GITHUB_AUDIT_LOG=data/github_app_events.jsonl
```

---

## Step 5 — Run the Server

### Local dev (with ngrok for a public webhook URL)

```bash
# Terminal 1 — start the ADAAD server
pip install -r requirements.txt
source .env  # or: export $(cat .env | xargs)
python server.py
# → Unified server → http://localhost:8080/

# Terminal 2 — expose locally via ngrok
ngrok http 8080
# Ngrok gives you: https://abc123.ngrok.io
# Set Webhook URL in GitHub App settings to:
#   https://abc123.ngrok.io/webhook/github
```

### Production (Render / Railway / Fly.io)

```bash
# Render: set Start Command to:
uvicorn server:app --host 0.0.0.0 --port $PORT

# All env vars above go into Render's Environment tab
# Webhook URL = https://your-app.onrender.com/webhook/github
```

### Verify the connection

After starting the server and setting the Webhook URL, click **"Redeliver"** on any recent delivery in the GitHub App settings, or trigger a test ping. You should see in server logs:

```
INFO: GitHub webhook event=ping delivery=abc-123
INFO: GitHub App ping — zen: Keep it logically awesome.
```

---

## Step 6 — Slash Commands in Issues/PRs

Once installed on the repo, anyone can use in an issue or PR comment:

```
/adaad status     → emits governance status event to audit ledger
/adaad dry-run    → triggers governed dry-run signal
/adaad help       → emits help event
```

These are handled by `app/github_app.py → _handle_slash_command()`.

---

## Quick verification checklist

```bash
# 1. Server starts without import errors
python server.py

# 2. Webhook endpoint responds
curl -s -X POST http://localhost:8080/webhook/github \
  -H "x-github-event: ping" \
  -H "content-type: application/json" \
  -d '{"zen":"test"}' | python -m json.tool
# Expected: {"status": "ok", "event": "ping", "zen": "test"}
# (in dev mode — no GITHUB_WEBHOOK_SECRET set — signature is bypassed)

# 3. In production mode (with secret set), unsigned request returns 401
GITHUB_WEBHOOK_SECRET=mysecret ADAAD_ENV=production \
  curl -s -X POST http://localhost:8080/webhook/github \
  -d '{}' | python -m json.tool
# Expected: {"detail": "invalid_webhook_signature"}

# 4. Governance events appear in the audit log
tail -f data/github_app_events.jsonl
# (populated on push/PR events after installation)
```

---

## What events flow to the governance ledger

| GitHub event | Governance signal emitted |
|---|---|
| `push` to `main` | `push.main` → `ExternalGovernanceSignal` in `external_event_bridge` |
| PR merged to main | `pr.merged` → GovernanceGate pre-check → ledger entry |
| Check run failure | `ci.failure` → ledger entry |
| `/adaad status` comment | `slash_command` → ledger entry |
| Any push/PR (non-main) | `pr.updated` → ledger entry |
| Installation | logged, no governance emission |

All signals are **advisory only** — `GITHUB-APP-MUT-0` guarantees no autonomous mutation is triggered by webhook events. Governance gate is observational.
