# `_inbox` lifecycle and retention rules

`_inbox/` is an intake workspace for non-canonical assets. Treat it as a short-lifecycle staging area, not long-term storage.

## Folder purpose

| Subfolder | Intended use | Git retention |
|---|---|---|
| `media/` | Curated assets actively referenced by docs/UI (logos, banners, approved audio/image assets) | Keep only intentionally referenced files |
| `reports/` | Temporary analyst exports and intermediate reports | Prefer external artifact storage; commit only if a report is explicitly linked from versioned docs |
| `proposals/` | Active proposal inputs under review | Keep only current source inputs |
| `proposals/captures/` | Transient ingestion captures (raw snapshots, browser exports) | Do **not** commit capture payloads (placeholder `.gitkeep` only) |
| `proposals/exports/` | Generated one-off exports from tooling | Do **not** commit export payloads (placeholder `.gitkeep` only) |

## `_inbox/proposals` classification (2026-03-14 audit)

### Active workflow inputs (kept in `_inbox/proposals`)
- `ADAAD_2.0_Engineering_Proposal.docx`
- `ADAAD_v8_Unified_Roadmap (2).docx`
- `ADAAD_Thesis.html`
- `adaad-explainer.html`

### Historical captures (moved to archive)
- `ADAAD_Founder_Plan_Proposal (1).html`
- `index.html`
- `InnovativeAI-adaad_ADAAD_ ADAAD — Autonomous Device-Anchored Adaptive Development. Full local AI ecosystem (Beast Mode, Dream Mode, Cryovant, Aponi Dashboard)..html`

Archive index: `docs/archive/inbox-proposals/README.md`.

## Purge policy

Purge or archive `_inbox` content when any of the following is true:

1. The file is a raw capture/export that is not directly consumed by repository code or canonical docs.
2. The file has been superseded by a newer versioned source.
3. The file is larger than needed for routine review and exists only for one-off provenance.
4. The related proposal/review cycle is closed.

When archival is required, move the artifact to `docs/archive/` (or an approved external artifact store) and add/update a short index entry describing origin, date, and reason.
