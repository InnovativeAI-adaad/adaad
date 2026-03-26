# ADAAD Extension SDK Specification (v2026-03)

## Purpose

This specification defines how third-party and internal plugins integrate with ADAAD runtime surfaces while preserving fail-closed governance, deterministic replay, and evidence traceability.

## 1) Plugin manifest schema (`plugin.manifest.v1`)

Required fields:

- `schema_version`: must equal `plugin.manifest.v1`
- `plugin_id`: immutable reverse-DNS style identifier (example: `com.example.risk_scanner`)
- `plugin_version`: semantic version (SemVer)
- `display_name`: human-readable name
- `owner`: team or organization
- `entrypoint`: import path + callable contract
- `declared_extension_points`: list of extension point IDs requested by the plugin
- `sandbox_profile`: requested least-privilege profile
- `resource_limits`: CPU/memory/wall-clock budgets
- `replay_contract`: deterministic input/output commitment for replay compatibility
- `capability_flags`: explicit list of optional capabilities
- `signature`: detached signature metadata for provenance

Example manifest:

```json
{
  "schema_version": "plugin.manifest.v1",
  "plugin_id": "com.example.risk_scanner",
  "plugin_version": "1.4.0",
  "display_name": "Risk Scanner",
  "owner": "Innovative AI LLC",
  "entrypoint": {
    "module": "plugins.risk_scanner",
    "callable": "register"
  },
  "declared_extension_points": [
    "mutation.pre_submit",
    "evidence.bundle.enrichment"
  ],
  "sandbox_profile": "strict_readonly",
  "resource_limits": {
    "cpu_seconds": 10,
    "memory_mb": 256,
    "wall_seconds": 15
  },
  "replay_contract": {
    "deterministic": true,
    "input_schema": "mutation.proposal.v1",
    "output_schema": "mutation.proposal.enriched.v1",
    "stateful": false
  },
  "capability_flags": ["ledger_read", "evidence_write_fragment"],
  "signature": {
    "key_id": "plugin-signing-2026-q1",
    "algorithm": "ed25519",
    "manifest_sha256": "<sha256>",
    "signature_b64": "<base64>"
  }
}
```

## 2) Security sandbox constraints

All plugins execute in a fail-closed sandbox. The runtime rejects any manifest that cannot satisfy the minimum constraints below.

- Network disabled by default (egress denied).
- File system write disabled except approved temp scratch path.
- No shell/process spawning unless explicitly allowlisted by profile.
- Memory/CPU/wall-clock hard caps enforced.
- Import boundary restrictions: plugin imports must remain inside approved extension packages.
- Secret access is denied unless explicitly allowlisted by capability + environment profile.
- Sandbox policy violations produce governance evidence and block plugin activation.

Profile tiers:

- `strict_readonly` (default): no writes, no egress, deterministic-only I/O.
- `strict_ephemeral_write`: limited temp write, no egress.
- `governed_privileged` (rare): gated by explicit constitutional approval and additional review.

## 3) Deterministic replay compatibility checks

Before certification and at activation time, plugins must pass replay compatibility checks:

1. Canonical manifest hash match across repeated loads.
2. Deterministic fixture replay (same input corpus => same output hashes).
3. Replay environment fingerprint compatibility (provider/runtime/profile stable).
4. Entropy discipline pass (`ADAAD_FORCE_DETERMINISTIC_PROVIDER=1` compatible).
5. Divergence threshold is zero for strict mode.

Any divergence in strict mode is a certification blocker.

## 4) Certification workflow and signed artifact

Certification stages:

1. **Submit** manifest + source digest + requested extension points.
2. **Static validation** against `plugin.manifest.v1` and import/sandbox policy.
3. **Replay validation** using deterministic fixture set and strict replay policy.
4. **Security validation** (capability review, deny-by-default checks).
5. **Governance attestation** and artifact signing.
6. **Registry publication** as approved plugin release.

Signed certification artifact schema (`plugin.certification.v1`):

```json
{
  "schema_version": "plugin.certification.v1",
  "plugin_id": "com.example.risk_scanner",
  "plugin_version": "1.4.0",
  "manifest_sha256": "<sha256>",
  "source_bundle_sha256": "<sha256>",
  "approved_extension_points": [
    "mutation.pre_submit",
    "evidence.bundle.enrichment"
  ],
  "sandbox_profile": "strict_readonly",
  "replay_digest": "<sha256>",
  "replay_mode": "strict",
  "certified_at_utc": "2026-03-26T00:00:00Z",
  "expires_at_utc": "2027-03-26T00:00:00Z",
  "issuer": "adaad-certifier",
  "signature": {
    "key_id": "adaad-certifier-2026-q1",
    "algorithm": "ed25519",
    "payload_sha256": "<sha256>",
    "signature_b64": "<base64>"
  }
}
```

Activation rules:

- Plugin activation requires a valid, non-expired certification artifact.
- Certification manifest hash must match the runtime-loaded manifest hash.
- Runtime or schema major-version incompatibility blocks activation.
- Revoked key IDs fail closed.

## 5) Runtime/API extension points

Canonical extension points are exposed through `runtime.api.extensions.extension_sdk_descriptor()` and `/api/extensions/spec`.

Current points:

- `mutation.pre_submit`
- `mutation.post_decision`
- `evidence.bundle.enrichment`
- `api.audit.augment`

Each point publishes:

- I/O contract ID
- determinism requirement
- sandbox requirement
- owning runtime surface

## 6) Compatibility and deprecation policy

Compatibility policy:

- API major version (`v1`) is stable for all extension endpoints in this cycle.
- Manifest/certification schema additions are backward compatible within major version.
- Breaking schema changes require new major schema IDs (for example `plugin.manifest.v2`).

Deprecation policy:

- Minimum compatibility window: 180 days after deprecation notice.
- Target removal window: 365 days after notice.
- Deprecation signals must be emitted via:
  - OpenAPI `deprecated: true`
  - `X-ADAAD-Deprecation` header
  - `X-ADAAD-Sunset` header

Any extension point in `deprecated` state must document migration targets before sunset.
