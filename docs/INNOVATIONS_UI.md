# Phase 69 — Aponi Innovations UI

**Status:** ✅ shipped (v9.4.0) · **Branch:** `phase69/aponi-innovations-ui`

## Summary

Phase 69 wires the full innovations stack into the Aponi dashboard as a new **Innovations** tab (keyboard shortcut `7`). The UI is built to a **neuro-cosmic luxury** design aesthetic — Syne display font, JetBrains Mono for all data, three-color agent identity system, animated constellation galaxy canvas, and living narrative timeline arcs.

---

## New Tab: Innovations (✦ Innovations)

Five sub-panels accessible via pill navigation:

### 1. Oracle
Query ADAAD's evolutionary history with the deterministic Oracle engine. Pre-set query chips (`divergence`, `rejected`, `performance`, `contributed`) plus free-text input. Results rendered in JetBrains Mono with gold glow. Demo fallback when server not connected.

### 2. Story Mode
Living narrative timeline: each epoch rendered as a colored arc with agent badge and outcome. Architect = ice cyan, Dream = aurora magenta, Beast = ember orange. Promoted = bio-green, Rejected = red. Self-Reflection banners surface automatically when a reflection report is in state.

### 3. Galaxy (Federated Evolution Map)
Full-screen animated HTML5 canvas constellation. Repositories as glowing cyan stars with pulsing halos. Mutation flow paths as gradient light beams. Divergence events as orange flare paths with high-density particle streams. 120-star background field with independent twinkle animation. Refreshes from `/innovations/federation-map` on tab load.

### 4. Seeds (Capability Seeds)
Bio-green registration form: seed_id, lane, intent, scaffold, author. Seeds appear as living list items with glow filter. Idempotent — re-registration shows existing state. Wired to `POST /innovations/seeds/register` and `GET /innovations/seeds`.

### 5. Agents (Mutation Personalities)
Three agent identity cards — Architect, Dream, Beast — each with animated vector bars, active epoch indicator, and persisted profile metadata loaded from `GET /innovations/personality-profiles`.

Each card now surfaces:
- current persisted philosophy + vector state
- deterministic vector delta from latest epoch (`vector_before` → `vector_after`)
- win/loss counters and recent epoch outcomes tied to persona choices
- live badge updates from the innovations websocket `personality` frame

---

## Design System

| Token | Value | Use |
|-------|-------|-----|
| `--arch` | `#00e5ff` | Architect — ice cyan |
| `--dream` | `#e040fb` | Dream — aurora magenta |
| `--beast` | `#ff6d00` | Beast — ember orange |
| `--seed-glow` | `#69ff47` | Seeds — bio-green |
| `--oracle-glow` | `#ffe57f` | Oracle — gold |

**Fonts:** Syne (800/700/600) for headings and nav · JetBrains Mono (600/500/400) for all data/code

**Motion:** `arc-enter` stagger on story timeline · spring fill on personality vectors · `orbit` particle animation on galaxy paths · `spin` on oracle loading indicator

---

## Files

| File | Change |
|------|--------|
| `ui/aponi/innovations_panel.js` | New 1118-line self-contained panel module |
| `ui/aponi/index.html` | Innovations tab added; script included; `render()` hooked; keyboard shortcut `7` documented |

---

## Architecture

`innovations_panel.js` is a self-contained IIFE that:
- Injects its own CSS on first load (no build step required)
- Exposes `window._innovationsPanel.view()` consumed by Aponi's `render()`
- Reads `window._adaadState.baseUrl` for API calls (set by Aponi before calling `view()`)
- All API calls gracefully fall back to demo data — dashboard is fully usable offline
