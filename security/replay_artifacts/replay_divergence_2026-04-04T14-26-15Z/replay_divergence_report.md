# Replay Divergence Artifact Report

- Generated at: `2026-04-04T14:26:17Z`
- Replay command: `python -m app.main --verify-replay --replay strict`
- Verify target: `all_epochs`
- Decision: `fail_closed`

## Digest Comparison
- Base digest: `a`
- Current digest: `b`

## Normalized First Divergence
- Epoch: `all_epochs`
- First differing path: `digest`

## Environment Flags
- `ADAAD_CEL_ENABLED=true`
- `ADAAD_DETERMINISTIC_SEED=orchestrator-test-seed`
- `ADAAD_DISABLE_MUTABLE_FS=1`
- `ADAAD_DISABLE_NETWORK=1`
- `ADAAD_ENV=dev`
- `ADAAD_FORCE_DETERMINISTIC_PROVIDER=1`
- `ADAAD_FORCE_TIER=SANDBOX`
- `ADAAD_POLICY_ARTIFACT_SIGNING_KEY=test-key`
- `ADAAD_SANDBOX_CONTAINER_ROLLOUT=off`
- `ADAAD_SANDBOX_ONLY=true`
- `CRYOVANT_DEV_MODE=1`

## Determinism Lint Summary
- Command: `python tools/lint_determinism.py runtime/ security/ adaad/orchestrator/ app/main.py`
- Return code: `1`
- Status: `violations`

```text
runtime/innovations30/__init__.py:147:10: forbidden_dynamic_execution
runtime/innovations30/__init__.py:86:18: forbidden_dynamic_execution
app/main.py:118:32: forbidden_dynamic_execution
determinism lint failed: 3 issue(s)
```

## Artifact Files
- JSON: `/home/claude/adaad/security/replay_artifacts/replay_divergence_2026-04-04T14-26-15Z/replay_divergence_report.json`
- Markdown: `/home/claude/adaad/security/replay_artifacts/replay_divergence_2026-04-04T14-26-15Z/replay_divergence_report.md`
