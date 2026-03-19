# Installing ADAAD on Android
**InnovativeAI LLC · Version synced from `VERSION` during docs publish · Free · No Play Store required**

> **Minimum:** Android 8.0 (API 26) · ~50 MB storage · Internet for workspace sync

---

## 🏆 Recommended — Obtainium (auto-updates, one-time setup)

Obtainium tracks GitHub Releases and auto-installs updates. Set it once, stay
current forever.

**Step 1 — Get Obtainium** (if not already installed)

Install Obtainium itself from F-Droid or its own GitHub Releases:
- F-Droid: `https://f-droid.org` → search *Obtainium*
- Direct: `https://github.com/ImranR98/Obtainium/releases` → download `.apk`

**Step 2 — Add ADAAD**

Option A — One-tap import (open this link on your phone):
```
obtainium://app/https://github.com/InnovativeAI-adaad/ADAAD
```

Option B — Manual add:
1. Open Obtainium → tap **+**
2. Paste `https://github.com/InnovativeAI-adaad/ADAAD`
3. Obtainium auto-detects the `adaad-community-*.apk` asset filter
4. Tap **Save** then **Install**

**Step 3 — Done.** Obtainium checks for new releases on your schedule.

![QR — Obtainium import](docs/assets/qr/obtainium_install_android_doc.svg)
*Scan to auto-import in Obtainium*

---

## ⚡ Fastest — Direct APK (sideload)

**On your Android device:**

1. Open `https://github.com/InnovativeAI-adaad/ADAAD/releases/latest`
   or scan this QR code: ![QR — Releases](docs/assets/qr/releases_install_android_doc.svg)
2. Tap the `adaad-community-*.apk` file to download
3. When the download completes, tap **Open** in the notification
4. Android shows **"Install unknown app"** — tap **Settings** → enable
   *Allow from this source* → press back → tap **Install**
5. Tap **Open** — ADAAD launches

> **Why the extra step?** Android requires a one-time permission to install
> apps from outside the Play Store. It only applies to the app you used to
> download the file (your browser). It does not affect other apps.

---

## 🌐 Instant — Web App (PWA, no download at all)

Works in **Chrome for Android** (version 80+). No APK, no permissions needed.

1. Open **Chrome** on Android and visit:
   `https://innovativeai-adaad.github.io/ADAAD/`
2. Wait for the page to load, then tap the **⋮ three-dot menu** (top right)
3. Tap **Add to Home screen**
4. Tap **Add** in the confirmation dialog
5. Find the ADAAD icon on your home screen — tap to launch

The PWA opens in standalone mode (no browser chrome). The Aponi governance
dashboard, constitution browser, and ledger viewer all work offline once loaded.
Mutation proposals require a live workspace endpoint.

![QR — PWA](docs/assets/qr/pwa_install_android_doc.svg)
*Scan to open the web app directly*

---

## 📦 Privacy-First — F-Droid

F-Droid builds APKs from source and verifies them independently. Best for users
who want fully auditable, reproducible builds.

### Option A: Self-Hosted Repo (available now)

1. Open the **F-Droid** app
2. Go to **Settings → Repositories → +**
3. Paste: `https://innovativeai-adaad.github.io/adaad-fdroid/repo`
   or scan: ![QR — F-Droid](docs/assets/qr/fdroid_install_android_doc.svg)
4. Tap **Add repository**
5. F-Droid refreshes — search **ADAAD** → Install

### Option B: Official F-Droid (submission in progress, ~1–4 weeks)

Once approved, ADAAD will appear in the default F-Droid repository. Search
*ADAAD* in the F-Droid app. No repository URL needed.

---

## 🖥️ All-in-One Install Page

Visit our dedicated install page for a visual, QR-code-first guide:

`https://innovativeai-adaad.github.io/ADAAD/install`

![QR — Install page](docs/assets/qr/install_page_install_android_doc.svg)
*Scan to open the full install guide on your phone*

---

## Verify APK Integrity

Every release APK is signed with the InnovativeAI LLC certificate.
To verify before installing:

```bash
# On a desktop with Android SDK tools:
apksigner verify --print-certs adaad-community-3.1.0.apk
```

Expected certificate fingerprint:
```
SHA-256: E2:04:C6:F3:97:A2:58:D0:42:29:9E:F7:EC:6A:35:8D:
         64:2E:62:77:BD:32:42:B5:A4:85:81:BF:F2:E5:27:ED
```

SHA-256 hash of the APK itself is published alongside every release asset
as `adaad-community-*.apk.sha256`.

---

## 🔧 Developer / Termux (run ADAAD Python server on-device)

Termux lets you run the full ADAAD Python server on Android without a computer.

### Prerequisites

```bash
pkg update && pkg upgrade -y
pkg install python git libsodium openssl -y
```

### Clone and run

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python3 onboard.py
```

`onboard.py` detects Termux automatically and uses `--only-binary :all:` to
skip packages that require a C compiler.  If any native dependency fails:

```bash
# Install Termux-packaged equivalents
pkg install python-cryptography -y
# Then retry
python3 onboard.py
```

### Run the governance dashboard

```bash
# Generate a dev soulbound key (required for ledger writes)
export ADAAD_SOULBOUND_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export ADAAD_ENV=dev

python3 server.py
# Dashboard available at http://localhost:8000
```

To persist the key across sessions, add the `export` line to `~/.bashrc`.

> **Note:** `pip install adaad` requires Python ≥ 3.11. Most Android environments (Termux, Pydroid3) run Python 3.10 — use the source install below for Android.
> Install from source via `git clone` as shown above.

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| *"Install blocked"* | Settings → Apps → Special app access → Install unknown apps → your browser → Allow |
| *"App not installed"* (after blocked) | Delete the partial download, re-download, try again |
| *App opens blank* | Check you have internet; the app needs to reach your workspace endpoint on first launch |
| *Can't find APK in Obtainium* | Confirm you pasted the full URL: `https://github.com/InnovativeAI-adaad/ADAAD` |
| *F-Droid repo not updating* | F-Droid → Repositories → tap the ADAAD repo → Refresh |
| *PWA "Add to Home screen" not shown* | Must use Chrome (not Firefox or Samsung Browser) — visit the page, wait 30s |
| *`pip install adaad` fails on Android* | Android Python is typically 3.10; package requires ≥ 3.11 — use `git clone https://github.com/InnovativeAI-adaad/ADAAD.git` instead |
| *`metadata-generation-failed` in Termux* | Run `pkg install libsodium python-cryptography -y` then `python3 onboard.py` |
| *`on_event` deprecation warning* | FastAPI lifespan APIs are now the canonical startup/shutdown path; update to the latest main branch and restart the server process |
| *Server exits immediately in Termux* | Ensure `ui/aponi` exists; run `python3 server.py` from the ADAAD directory |

File a bug: `https://github.com/InnovativeAI-adaad/ADAAD/issues` — label: `android`

---

*ADAAD · MIT License · InnovativeAI LLC · Blackwell, Oklahoma*
