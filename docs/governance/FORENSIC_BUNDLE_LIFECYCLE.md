# Forensic Bundle Lifecycle

Forensic bundles under `reports/forensics/` are immutable evidence exports. Retention and cleanup must preserve auditability.

## Lifecycle invariants

1. Bundles are canonical JSON and immutable after write.
2. Retention decisions are deterministic for a fixed `--now-epoch` input.
3. Cleanup actions are logged append-only to `retention_disposition.jsonl`.

## Retention automation

Use the deterministic helper script:

```bash
# Dry run (no deletion)
python scripts/enforce_forensic_retention.py \
  --export-dir reports/forensics \
  --retention-days 365 \
  --now-epoch 1700000000 \
  --dry-run

# Enforce deletion of expired bundles + append disposition log
python scripts/enforce_forensic_retention.py \
  --export-dir reports/forensics \
  --retention-days 365 \
  --now-epoch 1700000000 \
  --enforce
```

## Operator notes

- `export_metadata.retention_days` (when present) overrides default retention.
- If a bundle cannot be parsed, the script fails closed and performs no deletion.
- Schedule at least daily in production orchestration with explicit timestamp input.
- Evidence export signing is fail-closed: configure either `ADAAD_EVIDENCE_BUNDLE_KEY_<KEY_ID>` (preferred, where `<KEY_ID>` is uppercased and `-` is replaced with `_`) or `ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY`.
- If neither signing key env var is present for the selected `ADAAD_EVIDENCE_BUNDLE_KEY_ID`, export fails with deterministic error `missing_export_signing_secret:<key_id>`.


## Optional systemd scheduling

Use the provided units under `ops/systemd/`:

```bash
sudo cp ops/systemd/adaad-forensic-retention.service /etc/systemd/system/
sudo cp ops/systemd/adaad-forensic-retention.timer /etc/systemd/system/

# Optional: override install path when ADAAD is not deployed at /opt/adaad
printf 'ADAAD_ROOT=/srv/adaad\n' | sudo tee /etc/default/adaad >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now adaad-forensic-retention.timer
```

The service invokes `ops/systemd/run_forensic_retention.sh`, which resolves `ADAAD_ROOT` (default: repo root when run directly, `/opt/adaad` when run via the service), passes an explicit epoch timestamp to the deterministic retention script, and appends disposition logs.


See also: [Environment variable catalog](../ENVIRONMENT_VARIABLES.md) for `ADAAD_ROOT` and related operational controls.
