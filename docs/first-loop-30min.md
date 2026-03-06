# First Loop in 30 Minutes

This walkthrough runs one full ADAAD cycle:

1. boot,
2. Dream task discovery,
3. mutation evaluation/promotion,
4. replay verification,
5. inspection of manifests + ledger events.

## 0) Prereqs (2 min)

Preferred setup flow:

```bash
python onboard.py
```

Fallback (if onboarding is unavailable in your environment):

```bash
pip install -r requirements.server.txt
```

## 1) Boot the orchestrator (5 min)

```bash
python -m app.main --replay audit
```

Expected checkpoint:

- Dashboard is reachable at `http://localhost:8080`.
- Boot/replay events are appended to `reports/metrics.jsonl`.
- Replay verification is written to the ledger and replay manifest directory.

## 2) Verify Dream task discovery happened (5 min)

In another shell:

```bash
tail -n 100 reports/metrics.jsonl | rg 'dream_discovery|dream_health_ok|dream_candidate_generated|dream_mutation_fitness'
```

Expected key events:

- `dream_discovery`
- `dream_health_ok`
- `dream_candidate_generated`
- `dream_mutation_fitness`

Dream manifests are written into each staged mutation directory:

```bash
find adaad/agents/lineage/_staging -name dream_manifest.json -print
```

## 3) Verify mutation evaluation + promotion (8 min)

Check Beast evaluation and promotion events:

```bash
tail -n 200 reports/metrics.jsonl | rg 'beast_cycle_start|beast_fitness_scored|mutation_promoted|mutation_discarded'
```

Check ledger records:

```bash
tail -n 200 security/ledger/lineage.jsonl | rg 'ancestry_validated|mutation_promoted|replay_verified'
```

Promotion artifacts appear under lineage (moved from `_staging` into the lineage directory):

```bash
find adaad/agents/lineage -maxdepth 2 -type f | rg 'mutation.json|dream_manifest.json'
```

## 4) Run replay verification-only mode (5 min)

```bash
python -m app.main --verify-replay --replay strict
```

Expected checkpoint:

- Replay result is emitted as `replay_verified` in the ledger (`security/ledger/lineage.jsonl`).
- Replay manifest JSON appears in `security/replay_manifests/`.

Inspect replay manifests:

```bash
find security/replay_manifests -type f -name '*.json' | tail -n 5
```

## 5) Optional: run the smallest single-agent example (5 min)

```bash
python examples/single-agent-loop/run.py
```

This keeps Dream scope constrained to one local example agent and demonstrates the same discovery → staging → promotion chain in an isolated example workspace.

## Troubleshooting: file not generated

If a file from steps 2–3 is missing, confirm you used full boot mode:

- `python -m app.main --replay audit` runs Dream/Beast and can produce staging + promotion artifacts.
- `python -m app.main --verify-replay --replay strict` is verification-only and only guarantees replay outputs (ledger `replay_verified` + `security/replay_manifests/*.json`).
- `python -m app.main --exit-after-boot --replay audit` exits before mutation cycle, so Dream/Beast artifact files are not expected.
