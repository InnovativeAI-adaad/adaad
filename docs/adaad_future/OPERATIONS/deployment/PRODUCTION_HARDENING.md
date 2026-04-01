# Production Hardening Guide

**Status:** Reference document — applies from v9.33.0 onward (post-reputation-staking)  
**Authority:** HUMAN-0 — Dustin L. Reid

---

## System Health Indicators

### Green (All Clear)
- Mirror Test accuracy ≥ 0.80 (once INNOV-30 ships)
- All agents balance ≥ MIN_STAKE
- Governance debt score < 0.70
- Constitutional entropy drift < 0.20
- DorkEngine fallback usage < 10% of requests
- All tier gates passing on latest commit

### Yellow (Monitor Closely)
- Mirror Test accuracy 0.70–0.79 — trending investigation needed
- Any agent balance < MIN_STAKE × 5 — near bankruptcy
- Governance debt score 0.70–0.89 — approaching bankruptcy threshold
- Constitutional entropy drift 0.20–0.29 — approaching warning threshold
- DorkEngine fallback usage 10–30% — Groq/Ollama connectivity issues
- Any tier-2 gate showing intermittent failures

### Red (HUMAN-0 Action Required)
- Mirror Test accuracy < 0.70 — calibration epoch mandatory
- Any agent balance = 0 — economic bankruptcy, quarantine agent
- Governance debt score ≥ 0.90 — BANK-0 trigger, declare bankruptcy
- Constitutional entropy drift ≥ 0.30 — double-HUMAN-0 required for amendments
- DorkEngine fallback usage > 50% — LLM connectivity crisis
- Any tier-1 gate failing — no merges until resolved

---

## Deployment Checklist

### Pre-Deployment
```bash
# Verify version alignment
python3 -c "
v = open('VERSION').read().strip()
import tomllib
t = tomllib.load(open('pyproject.toml','rb'))['tool']['poetry']['version']
assert v == t, f'Version mismatch: {v} vs {t}'
print(f'Version: {v} OK')
"

# Run full test suite
python3 -m pytest --tb=short -q

# Verify governance artifacts
ls artifacts/governance/phase$(python3 -c "import json; print(json.load(open('.adaad_agent_state.json'))['phase'] - 1)")/

# Check data directory
ls data/ 2>/dev/null || echo "data/ not yet created — will be created on first run"
```

### Environment Variables Required
```bash
# LLM providers (free tier)
GROQ_API_KEY=gsk_...           # Groq free tier key

# Ollama (optional — detected automatically)
# OLLAMA_HOST=http://localhost:11434  # default

# ADAAD runtime
ADAAD_ENV=production           # or development
ADAAD_LOG_LEVEL=INFO
ADAAD_DATA_DIR=/var/adaad/data # or ./data for local
ADAAD_ARTIFACT_DIR=./artifacts

# GitHub (for auto-sync)
GITHUB_TOKEN=$(cat /mnt/project/git_token)
```

### Data Directory Initialization
```bash
mkdir -p data/
# Files created automatically on first run:
# data/reputation_stakes.jsonl    (INNOV-15)
# data/agent_wallets.json         (INNOV-15)
# data/emergent_roles.json        (INNOV-16)
# data/postmortem_interviews.jsonl (INNOV-17)
# data/governance_windows.jsonl   (INNOV-18)
# data/mutation_archaeology.jsonl (INNOV-19)
# data/constitutional_gaps.jsonl  (INNOV-20)
# data/bankruptcy_declarations.jsonl (INNOV-21)
# data/external_signals.jsonl     (INNOV-22)
# data/mirror_test_records.jsonl  (INNOV-30)
```

---

## Backup Procedures

### Critical Data (back up daily)
```bash
# Snapshot all ADAAD data
SNAPSHOT_DIR="/backup/adaad/$(date +%Y%m%d)"
mkdir -p "$SNAPSHOT_DIR"

# Data files (JSONL — append only, easy to verify)
cp -r data/ "$SNAPSHOT_DIR/data/"

# Governance artifacts (immutable after phase merge)
cp -r artifacts/ "$SNAPSHOT_DIR/artifacts/"

# Agent state (changes every session)
cp .adaad_agent_state.json "$SNAPSHOT_DIR/"

# Verify backup integrity
python3 -c "
import json, pathlib
for f in pathlib.Path('$SNAPSHOT_DIR/data').glob('*.jsonl'):
    lines = f.read_text().splitlines()
    valid = sum(1 for l in lines if l.strip())
    errors = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            json.loads(line)
        except:
            errors += 1
    print(f'{f.name}: {valid} records, {errors} errors')
"
```

### Restore from Backup
```bash
RESTORE_FROM="/backup/adaad/20260401"
cp -r "$RESTORE_FROM/data/" ./data/
cp "$RESTORE_FROM/.adaad_agent_state.json" .
# Do NOT restore artifacts/ — they're in git
git checkout artifacts/
```

---

## Incident Response Runbook

### Incident: GovernanceBankruptcy declared (INNOV-21)
1. Check `data/bankruptcy_declarations.jsonl` for latest declaration
2. Do NOT approve any new proposals
3. Notify HUMAN-0 immediately
4. Review `debt_score` and `health_score` in declaration
5. Activate RemediationAgent: see `GOVERNANCE/HUMAN0_PROTOCOL_V2.md` emergency procedures
6. Monitor health score over next 5 epochs
7. After 5 clean epochs and health ≥ 0.65: HUMAN-0 discharge authorization
8. Record discharge in agent_state `human0_signoffs`

### Incident: Mirror Test calibration triggered (INNOV-30)
1. Check `data/mirror_test_records.jsonl` for accuracy breakdown
2. Identify lowest-accuracy category (rules/outcome/fitness)
3. Block new evolution epochs until calibration completes
4. Notify HUMAN-0 of calibration trigger
5. Run calibration epoch (historical replay, supervised)
6. Run mini-mirror-test (10 cases, threshold 0.75)
7. After passing mini-test: resume normal evolution

### Incident: Constitutional entropy drift ≥ 0.30 (INNOV-26)
1. Block all further amendments
2. Notify HUMAN-0: double-HUMAN-0 required
3. Review amendment history since last clean state
4. First sign-off: "Amendment proposal accepted in principle. Cooling period begins."
5. Wait 10 epochs (CEB-COOL-0 enforced computationally)
6. Second sign-off: "Cooling period complete. Amendment authorized."
7. Record both sign-offs in agent_state

### Incident: LLM provider failure (DorkEngine fallback > 50%)
1. Check Groq API status: https://status.groq.com
2. Check Ollama: `curl http://localhost:11434/api/tags`
3. If both unavailable: DorkEngine continues — no service interruption
4. When restored: test Groq with single request, then enable
5. Log recovery in session notes

---

## Performance Tuning

### JSONL File Management
JSONL files grow indefinitely. When files exceed 100MB:
```bash
# Archive old entries (keep last 10,000 lines)
for f in data/*.jsonl; do
    lines=$(wc -l < "$f")
    if [ "$lines" -gt 10000 ]; then
        echo "Archiving $f ($lines lines)"
        tail -10000 "$f" > "${f}.new"
        mv "$f" "${f}.archive.$(date +%Y%m%d)"
        mv "${f}.new" "$f"
    fi
done
```

### Constitutional Archaeology Query Optimization
As archaeology grows, queries slow down. When query latency > 5s:
```bash
# Build reverse index for archaeology queries
python3 -c "
import json
from pathlib import Path

index = {}
for line in Path('data/mutation_archaeology.jsonl').read_text().splitlines():
    if not line.strip():
        continue
    event = json.loads(line)
    mid = event.get('mutation_id', '')
    if mid not in index:
        index[mid] = []
    index[mid].append(event)

Path('data/archaeology_index.json').write_text(json.dumps(index, indent=2))
print(f'Index built: {len(index)} mutations indexed')
"
```

---

*Production hardening guide — authority: ADAAD LEAD, InnovativeAI LLC*
