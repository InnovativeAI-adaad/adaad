# Licensing Overview

- **Repository license**: MIT License (see `LICENSE`).
- **Documentation and examples**: MIT License unless otherwise stated in-file.
- **Tests, tools, and scripts**: MIT License unless otherwise stated.

## Third-party dependencies

Third-party packages retain their own licenses. Review dependency manifests and
upstream project notices before redistribution in regulated environments.


## License compatibility quick matrix

| Dependency license family | Compatibility with ADAAD MIT distribution | Notes |
| --- | --- | --- |
| MIT / BSD / ISC | Compatible | Preferred for low-friction redistribution. |
| Apache-2.0 | Compatible | Preserve NOTICE/attribution obligations where required. |
| GPL / AGPL / copyleft | Case-by-case review required | Require legal review before redistribution in regulated releases. |

## Compliance automation

Run `python scripts/validate_license_compliance.py` in CI to verify MIT baseline
license artifacts and SPDX/header guardrails.

## Documentation image provenance and brand constraints

- Image provenance manifest: `docs/assets/IMAGE_PROVENANCE.md`.
- All current `docs/assets/` images are repository-authored; no third-party image license is currently recorded.
- ADAAD brand visuals and marks remain trademark-restricted; see `BRAND_LICENSE.md` and filename-level notes in the image manifest before reuse outside repository docs/releases.
