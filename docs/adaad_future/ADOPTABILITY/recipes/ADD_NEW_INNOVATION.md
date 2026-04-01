# Recipe: Implement a New Innovation

**Audience:** ADAAD LEAD (and future contributors with HUMAN-0 delegation)  
**Use when:** Beginning any phase from Phase 100 onward  
**Time estimate:** 2–4 hours per phase (scaffold → full implementation)

---

## Prerequisites

- [ ] Predecessor phase is merged and tagged (verify `last_completed_phase` in agent_state)
- [ ] Git token available at `/mnt/project/git_token`
- [ ] Repo cloned and on `main` at latest SHA
- [ ] Claude API key available (for governance artifact generation)

---

## Step 1 — Environment Setup

```bash
GIT_TOKEN=$(cat /mnt/project/git_token)
cd /path/to/adaad
git config user.email "weirdo@innovativeai.llc"
git config user.name "InnovativeAI"
git remote set-url origin "https://${GIT_TOKEN}@github.com/InnovativeAI-adaad/adaad.git"
git pull origin main
```

Verify state:
```bash
python3 -c "
import json
s = json.load(open('.adaad_agent_state.json'))
print('Last phase:', s['last_completed_phase'])
print('Current version:', s['current_version'])
print('Next PR:', s['next_pr'])
"
```

---

## Step 2 — HUMAN-0 Plan Ratification

**Before writing any code**, read the phase plan:
```
docs/plans/PHASE_NNN_PLAN.md
```

HUMAN-0 (Dustin L. Reid) must declare:
> "Phase NNN plan ratified. Branch may open."

Document this in the session. The agent records it in `human0_signoffs`.

---

## Step 3 — Branch

```bash
PHASE=100
INNOV=15
NAME="agent-reputation-staking"
BRANCH="feat/phase${PHASE}-innov${INNOV}-${NAME}"

git checkout -b "${BRANCH}"
echo "Branch: ${BRANCH}"
```

---

## Step 4 — Read the Scaffold

```bash
# Identify the scaffold file
ls runtime/innovations30/

# Read the existing scaffold
cat runtime/innovations30/reputation_staking.py  # example for INNOV-15
```

**What the scaffold has:**
- Module docstring with innovation description
- Constants
- Dataclass definitions
- Class skeleton with method stubs
- `__all__` export

**What the promotion adds:**
- Full method implementations
- Hard-class invariant assertions
- `_persist()` / `_load()` JSONL append-only persistence
- SHA-256 digest computation on all records
- HUMAN-0 advisory trigger points
- CEL integration hooks

---

## Step 5 — Implement

### 5a. Promote the scaffold to full implementation

Key patterns required in every innovation module:

**Ledger-first persistence (Pattern: `-0` invariant)**
```python
def stake(self, agent_id, mutation_id, epoch_id, amount=None):
    # ... compute amount ...
    record = StakeRecord(...)
    
    # STAKE-0: ledger persists BEFORE balance mutates
    self._persist(record)           # ← write to JSONL first
    self._wallets[agent_id] -= amount  # ← then update memory
    
    return record
```

**Deterministic digest (Pattern: `-DETERM-0` invariant)**
```python
def __post_init__(self):
    if not self.stake_digest:
        payload = f"{self.agent_id}:{self.mutation_id}:{self.staked_amount}"
        self.stake_digest = "sha256:" + hashlib.sha256(
            payload.encode()
        ).hexdigest()[:16]
```

**Fail-open load (universal pattern)**
```python
def _load(self):
    if self.ledger_path.exists():
        try:
            for line in self.ledger_path.read_text().splitlines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        # ... reconstruct record ...
                    except Exception:
                        pass  # corrupt line silently skipped
        except Exception:
            pass  # fail-open: missing file is not an error
```

**Append-only JSONL persistence**
```python
def _persist(self, record):
    import dataclasses
    self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with self.ledger_path.open('a') as f:
        f.write(json.dumps(dataclasses.asdict(record)) + '\n')
```

### 5b. Register invariants

Add to the module's module-level docstring or a dedicated `INVARIANTS` dict:
```python
INVARIANTS = {
    "STAKE-0": "Hard: ledger persists before balance mutates",
    "STAKE-DETERM-0": "Hard: stake_digest deterministic from agent_id:mutation_id:amount",
    "STAKE-HUMAN-0": "Hard: balance ceiling advisory at 10x initial",
    "STAKE-BURN-0": "Hard: no partial burns — atomically full or zero",
}
```

### 5c. Wire into ConstitutionalEvolutionLoop (CEL)

Check which CEL step is the correct integration point:
```python
# In runtime/evolution/constitutional_evolution_loop.py
# Find the appropriate step and add:
stake_record = self.reputation_staking.stake(
    agent_id=proposal.agent_id,
    mutation_id=proposal.mutation_id,
    epoch_id=epoch_id
)
```

---

## Step 6 — Write 30 Tests

File: `tests/test_innovations30.py`

Find the existing T(NNN) test markers or add after the last test class.

```python
@pytest.mark.phase100
class TestAgentReputationStaking:
    """T100-ARS-01 through T100-ARS-30"""
    
    def test_T100_ARS_01_register_agent(self, tmp_path):
        """T100-ARS-01: Register agent with initial balance."""
        from runtime.innovations30.reputation_staking import ReputationStakingLedger
        ledger = ReputationStakingLedger(
            tmp_path / "stakes.jsonl",
            tmp_path / "wallets.json"
        )
        ledger.register_agent("agent-a", initial_balance=100.0)
        assert ledger.balance("agent-a") == 100.0

    def test_T100_ARS_08_stake_digest_determinism(self, tmp_path):
        """T100-ARS-08: Identical inputs → identical digest."""
        from runtime.innovations30.reputation_staking import StakeRecord
        r1 = StakeRecord("a1", "m1", "e1", 5.0, 100.0)
        r2 = StakeRecord("a1", "m1", "e1", 5.0, 100.0)
        assert r1.stake_digest == r2.stake_digest
    
    # ... 28 more tests ...
```

**Add pytest mark to `pytest.ini`:**
```ini
[pytest]
markers =
    ...
    phase100: Phase 100 INNOV-15 [Agent Reputation Staking] (ARS) tests
```

---

## Step 7 — Run Tests

```bash
# Run only the new phase tests
python3 -m pytest tests/test_innovations30.py -m phase100 -v

# Run full suite to check for regressions
python3 -m pytest --tb=short -q 2>&1 | tail -20
```

All 30 new tests must PASS. Zero regressions in existing suite.

---

## Step 8 — Governance Artifacts

```bash
mkdir -p artifacts/governance/phase100
```

**phase100_sign_off.json** — fill from template in `GOVERNANCE/templates/`:
```json
{
  "phase": 100,
  "innovation": "INNOV-15",
  "scope": "Agent Reputation Staking — 30/30 tests green — 4 STAKE invariants — v9.33.0 release",
  "governor": "DUSTIN L REID",
  "date": "2026-04-XX",
  "session_digest": "phase100-ars-impl-2026-04-XX",
  "attestation_ref": "ILA-100-2026-04-XX-001",
  "gate_results": {"tier_0": "pass", "tier_1": "pass", "tier_2": "pass", "tier_3": "pass"},
  "new_invariants": ["STAKE-0", "STAKE-DETERM-0", "STAKE-HUMAN-0", "STAKE-BURN-0"],
  "cumulative_hard_invariants": 50,
  "test_count": 2774,
  "release_tag": "v9.33.0"
}
```

**replay_digest.txt** — fill from template  
**tier_summary.json** — fill from template  
**identity_ledger_attestation.json** — fill from ILA template

---

## Step 9 — Version / Changelog / Roadmap

```bash
# Update VERSION
echo "9.33.0" > VERSION

# Update pyproject.toml
sed -i 's/^version = ".*"/version = "9.33.0"/' pyproject.toml

# Prepend to CHANGELOG.md (use the established format)
# Check existing entries for format reference
head -40 CHANGELOG.md
```

**CHANGELOG entry format:**
```markdown
## [9.33.0] — YYYY-MM-DD — Phase 100 · INNOV-15 Agent Reputation Staking (ARS)

**Branch:** `feat/phase100-innov15-agent-reputation-staking`
**HUMAN-0 Gate:** Dustin L. Reid — ratified YYYY-MM-DD
**Tests:** T100-ARS-01..30 (30/30 PASS)
**Evidence:** `artifacts/governance/phase100/phase100_sign_off.json` · ILA-100-YYYY-MM-DD-001

### Phase 100: INNOV-15 — Agent Reputation Staking (ARS)
...
```

---

## Step 10 — Agent State Update

Update `.adaad_agent_state.json`:
```python
import json
from datetime import date

with open('.adaad_agent_state.json') as f:
    state = json.load(f)

state['last_completed_phase'] = "Phase 100 · INNOV-15 Agent Reputation Staking (ARS)"
state['current_version'] = "9.33.0"
state['software_version'] = "9.33.0"
state['version'] = "9.33.0"
state['phase'] = 101
state['phase_label'] = "Phase 101 — INNOV-16 Emergent Role Specialization"
state['last_innovation'] = "INNOV-15"
state['next_pr'] = "PR-PHASE101-01 (Phase 101 — INNOV-16 Emergent Role Specialization)"
state['last_invocation'] = str(date.today())
state['value_checkpoints_reached'].extend([
    "phase100-stake-ledger-first",
    "phase100-stake-determ-verified",
    "phase100-ars-complete",
    "v9.33.0-released"
])
state['human0_signoffs'].append({
    "date": str(date.today()),
    "governor": "DUSTIN L REID",
    "scope": "Phase 100 INNOV-15 Agent Reputation Staking — 30/30 tests — 4 invariants — v9.33.0",
    "session_digest": "phase100-ars-impl-" + str(date.today()),
    "attestation_ref": "ILA-100-" + str(date.today()) + "-001"
})

with open('.adaad_agent_state.json', 'w') as f:
    json.dump(state, f, indent=2)
```

---

## Step 11 — Commit

```bash
git add -A
git commit -m "feat(phase100): INNOV-15 Agent Reputation Staking (ARS) v9.33.0

- ReputationStakingLedger: stake/settle/balance with JSONL ledger
- StakeRecord: deterministic stake_digest sha256(agent:mutation:amount)
- STAKE-0: ledger-first invariant (persist before balance mutates)
- STAKE-DETERM-0: stake_digest determinism invariant
- STAKE-HUMAN-0: balance ceiling advisory at 10x initial
- STAKE-BURN-0: atomic burn invariant
- 30/30 T100-ARS tests passing
- Cumulative Hard-class invariants: 50
- ILA-100-$(date +%Y-%m-%d)-001

HUMAN-0: Dustin L. Reid — phase100-ars-impl-$(date +%Y-%m-%d)
Gate: tier_0=pass tier_1=pass tier_2=pass tier_3=pass"
```

---

## Step 12 — Push, Merge, Tag

```bash
# Push branch
git push origin feat/phase100-innov15-agent-reputation-staking

# HUMAN-0 pre-merge checkpoint: governor confirms all looks good

# Merge to main (no-FF)
git checkout main
git merge --no-ff feat/phase100-innov15-agent-reputation-staking \
  -m "Merge phase100: INNOV-15 Agent Reputation Staking (ARS) v9.33.0"
git push origin main

# Tag
git tag -a v9.33.0 -m "Phase 100: INNOV-15 Agent Reputation Staking (ARS)"
git push origin v9.33.0

echo "Phase 100 complete. v9.33.0 released."
```

---

## Step 13 — Verify

```bash
# Confirm version hygiene
python3 -c "
v = open('VERSION').read().strip()
import tomllib
t = tomllib.load(open('pyproject.toml','rb'))['tool']['poetry']['version']
import re
c = re.search(r'\[(\d+\.\d+\.\d+)\]', open('CHANGELOG.md').read()).group(1)
print(f'VERSION={v} pyproject={t} CHANGELOG={c}')
assert v == t == c, 'VERSION MISMATCH'
print('Version hygiene: OK')
"

# Confirm test count
python3 -m pytest --collect-only -q 2>/dev/null | tail -3
```

---

## Repeat For Next Phase

```bash
# What's next?
python3 -c "
import json
s = json.load(open('.adaad_agent_state.json'))
print('Next:', s['next_pr'])
"
```

The sequence is locked. Follow `ROADMAP/MASTER_EXECUTION_PLAN.md`.
