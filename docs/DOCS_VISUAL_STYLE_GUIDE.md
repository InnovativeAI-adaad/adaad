# ADAAD Documentation Visual Style Guide

> Deterministic, governance-first documentation presentation standard.

**Last reviewed:** 2026-03-04

## Scope and intent

This guide defines the baseline visual style for high-traffic ADAAD documentation.
It standardizes formatting without changing technical claims, security posture, or governance meaning.

## 1) Approved badge style

Use badges to communicate governance state and stable metadata, not marketing claims.

### Rules

- Prefer flat shields with explicit label/value semantics.
- Keep badge text deterministic and auditable (no dynamic counters).
- Use consistent ordering when grouped:
  1. Status
  2. Governance
  3. Determinism/Replay
  4. Runtime or language metadata
- Keep total badge count concise in hero blocks.

### Approved examples

```md
![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)
![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)
![Replay: Deterministic](https://img.shields.io/badge/Replay-Deterministic-0ea5e9)
```

## 2) Hero/header pattern

Each high-traffic doc should begin with a predictable header envelope:

1. H1 title
2. Optional approved badges row
3. One-sentence governance-first summary blockquote
4. `Last reviewed` marker

### Header template

```md
# Document Title

![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)
![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)

> One-sentence deterministic/governance-first summary.

**Last reviewed:** YYYY-MM-DD
```

## 3) Callout blocks

Use plain Markdown blockquotes for deterministic rendering portability.

### Allowed callouts

- `> ✅ **Do this:** ...`
- `> ⚠️ **Caveat:** ...`
- `> 🚫 **Out of scope:** ...`
- `> ℹ️ **Note:** ...`

### Rules

- Keep callouts short and operational.
- Do not restate policy in conflicting terms.
- Avoid speculative language.

## 4) Image width and placement

- Use centered HTML blocks only when image layout control is required.
- Recommended widths:
  - Hero/banner image: `680-900`
  - Flow/process diagrams: `640-780`
  - Inline supporting visuals: `480-680`
- Place primary image near top (after summary) and avoid repeated large images in the same viewport.

Example:

```html
<p align="center">
  <img src="assets/governance-flow.svg" width="760" alt="Governance flow from proposal through replay verification and evidence archival">
</p>
```

## 5) Alt-text requirements

All images must include explicit alt text.

### Alt-text standard

- Describe governance-relevant meaning, not purely visual appearance.
- Keep alt text concise (typically one sentence).
- Avoid filler prefixes like "image of".
- If decorative-only, use empty alt (`alt=""`) and justify usage in review.

### Good example

`alt="Governance flow from proposal through replay verification and evidence archival"`

### Avoid

`alt="banner"`

## Change control

Visual updates must preserve deterministic, governance-first content semantics.
If a styling update appears to require claim changes, split into a separate content-review PR.


## 6) Last reviewed policy

- `Last reviewed` is an owner-attested metadata field and must be updated on each substantive documentation change.
- This field is currently policy-enforced in review, not freshness-auto-validated in CI.
- If automated staleness enforcement is introduced later, it must remain deterministic and fail-closed.
