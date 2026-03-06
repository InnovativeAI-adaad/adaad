# Installing ADAAD on Android
**InnovativeAI LLC · v3.1.0-dev · Free · No Play Store required**

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

![QR — Obtainium import](docs/assets/qr/obtainium.svg)
*Scan to auto-import in Obtainium*

---

## ⚡ Fastest — Direct APK (sideload)

**On your Android device:**

1. Open `https://github.com/InnovativeAI-adaad/ADAAD/releases/latest`
   or scan this QR code: ![QR — Releases](docs/assets/qr/releases.svg)
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

![QR — PWA](docs/assets/qr/pwa.svg)
*Scan to open the web app directly*

---

## 📦 Privacy-First — F-Droid

F-Droid builds APKs from source and verifies them independently. Best for users
who want fully auditable, reproducible builds.

### Option A: Self-Hosted Repo (available now)

1. Open the **F-Droid** app
2. Go to **Settings → Repositories → +**
3. Paste: `https://innovativeai-adaad.github.io/adaad-fdroid/repo`
   or scan: ![QR — F-Droid](docs/assets/qr/fdroid.svg)
4. Tap **Add repository**
5. F-Droid refreshes — search **ADAAD** → Install

### Option B: Official F-Droid (submission in progress, ~1–4 weeks)

Once approved, ADAAD will appear in the default F-Droid repository. Search
*ADAAD* in the F-Droid app. No repository URL needed.

---

## 🖥️ All-in-One Install Page

Visit our dedicated install page for a visual, QR-code-first guide:

`https://innovativeai-adaad.github.io/ADAAD/install`

![QR — Install page](docs/assets/qr/install_page.svg)
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

## Troubleshooting

| Problem | Solution |
|---------|---------|
| *"Install blocked"* | Settings → Apps → Special app access → Install unknown apps → your browser → Allow |
| *"App not installed"* (after blocked) | Delete the partial download, re-download, try again |
| *App opens blank* | Check you have internet; the app needs to reach your workspace endpoint on first launch |
| *Can't find APK in Obtainium* | Confirm you pasted the full URL: `https://github.com/InnovativeAI-adaad/ADAAD` |
| *F-Droid repo not updating* | F-Droid → Repositories → tap the ADAAD repo → Refresh |
| *PWA "Add to Home screen" not shown* | Must use Chrome (not Firefox or Samsung Browser) — visit the page, wait 30s |

File a bug: `https://github.com/InnovativeAI-adaad/ADAAD/issues` — label: `android`

---

*ADAAD · MIT License · InnovativeAI LLC · Blackwell, Oklahoma*
