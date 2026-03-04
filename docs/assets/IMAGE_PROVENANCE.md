# Image Provenance Manifest

This manifest tracks source, ownership, usage rights, and modification lineage for documentation images under `docs/assets/`.

## Asset inventory

| File | Source | Author/Owner | License / Usage rights | Internal-only / distribution constraints | Modification history |
| --- | --- | --- | --- | --- | --- |
| `docs/assets/governance-flow.svg` | Repository-original diagram authored for ADAAD documentation. | ADAAD maintainers (InnovativeAI project owners). | Repository documentation baseline (see `LICENSES.md`); ADAAD trademarks/names remain protected. | Public documentation use in this repository and project releases. Do not imply separate trademark grant. | Introduced in commit `a071f60` (2026-02-22), with prior asset lineage from `bb08027` merge history. |
| `docs/assets/adaad-governance-flow.svg` | Repository-original diagram authored for ADAAD governance documentation. | ADAAD maintainers (InnovativeAI project owners). | Repository documentation baseline (see `LICENSES.md`); ADAAD trademarks/names remain protected. | Public documentation use in this repository and project releases. Do not imply separate trademark grant. | Present in commit history as of `bb08027` (2026-02-21). |
| `docs/assets/architecture-simple.svg` | Repository-original architecture diagram authored for ADAAD docs. | ADAAD maintainers (InnovativeAI project owners). | Repository documentation baseline (see `LICENSES.md`); ADAAD trademarks/names remain protected. | Public documentation use in this repository and project releases. Do not imply separate trademark grant. | Present in commit history as of `bb08027` (2026-02-21). |
| `docs/assets/adaad-banner.svg` | Repository-original ADAAD branded banner. | ADAAD maintainers (InnovativeAI project owners). | **Brand/trademark-restricted visual**; usage requires owner permission consistent with `BRAND_LICENSE.md`. | **Filename-level note:** `adaad-banner.svg` is internal/owner-approved distribution only for external packaging or marketing collateral unless explicit written approval is granted by project owners. | Present in commit history as of `bb08027` (2026-02-21). |

## Third-party image status

At time of writing, no third-party image files are registered in `docs/assets/`.
If third-party images are added later, update this manifest with upstream source URL, author attribution, and explicit license terms before release.

## Update procedure

When adding or replacing an image in `docs/assets/`:

1. Add a new row for the file in this manifest.
2. Record the upstream source (if any), owner, and license/usage terms.
3. Add filename-level constraints if the image is internal-only or trademark-restricted.
4. Cross-link any non-original or restricted rights from `LICENSES.md` and/or `THIRD_PARTY_NOTICES.md`.
