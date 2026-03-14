# ADAAD Documentation Visual Style Guide

![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)

> Deterministic, governance-first documentation presentation standard — applied consistently across all ADAAD docs.

**Last reviewed:** 2026-03-14

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

## 6 · Low-weight imagery policy (human-facing surfaces)

"Low-weight imagery" means visual assets are intentionally softened so technical text and policy claims remain primary.

**Approved low-weight ranges:**

| Property | Allowed range (`img-low-weight`) |
|---|---|
| Opacity | `0.40` to `0.68` |
| Filter saturation | `0.55` to `0.85` |
| Filter contrast | `0.82` to `0.95` |
| Glow / shadow alpha | up to `0.22` |

**Where this applies by default:**
- `README.md` and root/module markdown docs
- Docs HTML pages and markdown that embeds `<img ...>` blocks
- Human-facing UI panels where imagery is decorative or supportive

**Exception (full-contrast allowed):**
- Critical diagrams that carry decision-significant meaning (for example constitutional flow or security boundary diagrams) may use full contrast.
- These must be explicitly marked with `img-critical` (or `data-img-weight="critical"`) and reviewed for necessity.

### Embed examples

**Markdown/HTML embed for README/docs (preferred):**

```html
<p align="center">
  <img class="img-low-weight" data-img-weight="low"
    src="docs/assets/governance-flow.svg"
    width="760"
    alt="Governance flow from proposal through replay verification and evidence archival">
</p>
```

**Critical diagram exception:**

```html
<img class="img-critical" data-img-weight="critical"
  src="docs/assets/security-boundary-map.svg"
  alt="Security boundary map used for critical governance review">
```

**Frontend CSS example:**

```css
.img-low-weight {
  opacity: 0.58;
  filter: saturate(0.72) contrast(0.9);
}

.img-critical {
  opacity: 1;
  filter: none;
}
```

### Do / Don't matrix (representative selectors)

| Selector | Do | Don't |
|---|---|---|
| `.agent-portrait` | Apply low-weight treatment when portrait is supportive/decorative in panels. | Use full-contrast glow by default for non-critical portrait cards. |
| `.trio-banner-img` | Use `.img-low-weight` baseline in docs/human-facing banner use. | Present as dominant full-contrast hero unless the image is critical evidence. |
| `.img-critical` | Restrict to diagrams where reduced contrast harms interpretation. | Use for aesthetic preference only. |

## 7 · Alt text — Alt-text requirements

All images must include explicit alt text.

- Describe governance-relevant meaning, not visual appearance.
- Keep alt text concise (typically one sentence).
- Avoid filler prefixes like "image of."
- Decorative-only images: use `alt=""` and justify in review.

✅ `alt="Governance flow from proposal through replay verification and evidence archival"`

🚫 `alt="banner"` or `alt="image"`

---

## 8 · Tables

Prefer tables over nested bullet lists for structured comparisons. Use consistent column alignment. Table headers should be title-case or all-lowercase — not mixed.

---

## 9 · `Last reviewed` policy

- `Last reviewed` is owner-attested metadata — update it on every substantive documentation change.
- Currently policy-enforced in review, not auto-validated in CI.
- If automated staleness enforcement is introduced, it must remain deterministic and fail-closed.

---

## Change control

Visual updates must preserve deterministic, governance-first content semantics.
If a styling update requires claim changes, split into a separate content-review PR.
