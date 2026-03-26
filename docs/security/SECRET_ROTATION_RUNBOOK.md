# Secret Rotation Runbook (Post-Detection)

## Scope

This runbook is invoked whenever repository secret-scanning gates detect potential plaintext credentials.

## Trigger sources

- `python scripts/scan_secrets.py --path .`
- `.pre-commit-config.yaml` local hook `plaintext-secret-scan`
- `.github/workflows/ci.yml` secret scan step
- `.github/workflows/secret_scan.yml` deterministic + gitleaks scans

## Mandatory operator actions

1. **Contain**
   - Freeze release activity for affected branch/PR.
   - Identify exact credential type and impacted provider/service.
2. **Rotate and revoke**
   - Revoke exposed token/key at provider immediately.
   - Issue replacement credential following least-privilege policy.
3. **Repository remediation**
   - Remove plaintext secret from tracked files.
   - If already committed, execute approved history-remediation process.
4. **Verification**
   - Run scanner: `python scripts/scan_secrets.py --path .`
   - Run required governance/test gates before merge.
5. **Evidence and closure**
   - Record incident summary, rotation timestamp, and verification outcome in operator evidence records.
   - Link remediation evidence in release/PR documentation as required.

## Invariants

- Do not suppress scanner rules to pass CI.
- Do not replace leaked values with alternate real credentials.
- Only placeholder templates may remain in tracked examples.
