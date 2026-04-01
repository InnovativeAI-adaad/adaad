# Phase Launch Checklist

**Use before opening any phase branch.**  
All items must be checked before `git checkout -b`.

---

## Pre-Launch Gate

### Predecessor Verification
- [ ] `last_completed_phase` in agent_state matches expected predecessor
- [ ] `current_version` matches the predecessor's release version
- [ ] Predecessor's git tag exists: `git tag | grep vX.XX.0`
- [ ] Predecessor's CHANGELOG entry is at the top of `CHANGELOG.md`

### Plan Readiness
- [ ] Phase plan exists at `docs/plans/PHASE_NNN_PLAN.md`
- [ ] Phase plan has been read by HUMAN-0
- [ ] HUMAN-0 has declared: *"Phase NNN plan ratified. Branch may open."*
- [ ] `next_pr` in agent_state correctly identifies this phase

### Environment
- [ ] `git pull origin main` — working from latest main
- [ ] Python environment is functional: `python3 -m pytest --collect-only -q 2>/dev/null | tail -3`
- [ ] Git token is current: `curl -s -H "Authorization: token $(cat /mnt/project/git_token)" https://api.github.com/user | python3 -m json.tool | grep login`
- [ ] Scaffold module exists: `ls runtime/innovations30/`

### Branch Naming
- [ ] Branch name follows convention: `feat/phaseNNN-innovNN-kebab-name`
- [ ] Branch name has not been used before: `git branch -a | grep feat/phaseNNN`

---

**If all items checked:** Open branch and begin implementation.  
**If any item fails:** Resolve before proceeding. Do not open branch.
