# ADAAD Documentation Visual Style Guide

![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)

> Deterministic, governance-first documentation presentation standard — applied consistently across all ADAAD docs.

**Last reviewed:** 2026-03-05

---

## Scope

This guide defines the baseline visual style for all ADAAD documentation. It standardizes formatting without changing technical claims, security posture, or governance meaning.

---

## 1 · Badge style — Approved badge style

Badges communicate governance state and stable metadata — not marketing claims.

**Rules:**
- Use flat shields with explicit label/value semantics.
- Keep badge text deterministic and auditable (no dynamic counters).
- Consistent ordering in hero blocks:
  1. Status
  2. Governance
  3. Determinism / Replay
  4. Runtime or language metadata

**Approved examples:**

```md
![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)
![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)
![Replay: Deterministic](https://img.shields.io/badge/Replay-Deterministic-0ea5e9)
```

**For-the-badge (hero use only):**

```md
![Replay](https://img.shields.io/badge/Replay-Deterministic-0ea5e9?style=for-the-badge)
![Evidence](https://img.shields.io/badge/Evidence-Ledger_Anchored-22c55e?style=for-the-badge)
![Policy](https://img.shields.io/badge/Policy-Constitutional-f97316?style=for-the-badge)
```

---

## 2 · Document header pattern

Every high-traffic doc must open with a predictable header envelope:

1. H1 title
2. Badge row (optional but preferred)
3. One-sentence governance-first summary blockquote
4. `Last reviewed` marker

```md
# Document Title

![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)
![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)

> One-sentence deterministic/governance-first summary.

**Last reviewed:** 2026-03-05
```

---

## 3 · Horizontal rule usage

Use `---` horizontal rules to separate major sections in long documents. This improves scannability without headers competing with H2-level structure.

---

## 4 · Callout blocks

Use plain Markdown blockquotes for deterministic rendering portability.

| Symbol | Use case |
|---|---|
| `> ✅ **Do this:**` | Required action |
| `> ⚠️ **Caveat:**` | Known limitation or risk |
| `> 🚫 **Out of scope:**` | Explicit exclusion |
| `> ℹ️ **Note:**` | Informational aside |

**Rules:**
- Keep callouts short and operational.
- Do not restate policy in conflicting terms.
- Avoid speculative language.

---

## 5 · Image placement and widths

- Use centered HTML blocks when image layout control is required.
- Recommended widths:

| Image type | Width |
|---|---|
| Hero / banner | `780–900` |
| Flow / process diagrams | `640–760` |
| Inline supporting visuals | `480–640` |

Example:

```html
<p align="center">
  <img src="assets/governance-flow.svg" width="760"
    alt="Governance flow from proposal through replay verification and evidence archival">
</p>
```

Place the primary image near the top (after the summary blockquote). Avoid repeated large images in the same viewport.

---

## 6 · Alt text — Alt-text requirements

All images must include explicit alt text.

- Describe governance-relevant meaning, not visual appearance.
- Keep alt text concise (typically one sentence).
- Avoid filler prefixes like "image of."
- Decorative-only images: use `alt=""` and justify in review.

✅ `alt="Governance flow from proposal through replay verification and evidence archival"`

🚫 `alt="banner"` or `alt="image"`

---

## 7 · Tables

Prefer tables over nested bullet lists for structured comparisons. Use consistent column alignment. Table headers should be title-case or all-lowercase — not mixed.

---

## 8 · `Last reviewed` policy

- `Last reviewed` is owner-attested metadata — update it on every substantive documentation change.
- Currently policy-enforced in review, not auto-validated in CI.
- If automated staleness enforcement is introduced, it must remain deterministic and fail-closed.

---

## Change control

Visual updates must preserve deterministic, governance-first content semantics.
If a styling update requires claim changes, split into a separate content-review PR.
