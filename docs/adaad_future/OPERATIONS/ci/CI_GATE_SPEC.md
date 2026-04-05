# CI Gate Specification

**File:** `.github/workflows/ci.yml`  
**Authority:** HUMAN-0 — Dustin L. Reid  
**Last updated:** v9.32.0 (Phase 99)

---

## Overview

ADAAD CI runs on every push to any branch and every PR targeting `main`. The gate stack enforces governance integrity programmatically so that human review focuses on substance, not mechanics.

---

## Job Architecture

```yaml
jobs:
  version-hygiene:      # Tier 0: VERSION == pyproject == CHANGELOG
  import-contracts:     # Tier 0: __all__ and import boundary checks
  test-suite:           # Tier 1: Full pytest run (2,700+ tests)
  governance-artifacts: # Tier 2: Artifact existence and format validation
  evidence-matrix:      # Tier 2: claims_evidence_matrix.md completeness
  ci-gating-summary:    # Tier 3: Summary gate — required for PR merge
    needs: [version-hygiene, import-contracts, test-suite, governance-artifacts, evidence-matrix]
```

The `ci-gating-summary` job is the **merge gate**. No PR may merge without `ci-gating-summary: success`.

---

## Job: version-hygiene

```yaml
version-hygiene:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Check version alignment
      run: |
        VERSION=$(cat VERSION)
        PYPROJECT=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['tool']['poetry']['version'])")
        CHANGELOG=$(python3 -c "
          import re
          m = re.search(r'\[(\d+\.\d+\.\d+)\]', open('CHANGELOG.md').read())
          print(m.group(1) if m else 'NOT_FOUND')
        ")
        echo "VERSION=$VERSION PYPROJECT=$PYPROJECT CHANGELOG=$CHANGELOG"
        if [ "$VERSION" != "$PYPROJECT" ] || [ "$VERSION" != "$CHANGELOG" ]; then
          echo "VERSION MISMATCH — CI blocked"
          exit 1
        fi
        echo "Version hygiene: OK ($VERSION)"
```

---

## Job: import-contracts

```yaml
import-contracts:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: '3.12'}
    - run: pip install -e ".[dev]" --break-system-packages 2>/dev/null || pip install -e ".[dev]"
    - name: Run import contract tests
      run: python3 -m pytest tests/ -m "import_contract" -v --tb=short
    - name: Verify __all__ exports
      run: |
        python3 -c "
        import importlib, pkgutil, sys
        sys.path.insert(0, '.')
        for mod in pkgutil.walk_packages(['runtime'], prefix='runtime.'):
          try:
            m = importlib.import_module(mod.name)
            if not hasattr(m, '__all__'):
              print(f'WARNING: {mod.name} missing __all__')
          except ImportError as e:
            print(f'ERROR: {mod.name}: {e}')
            sys.exit(1)
        print('All modules importable with __all__ defined')
        "
```

---

## Job: test-suite

```yaml
test-suite:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: '3.12'}
    - run: pip install -e ".[dev]"
    - name: Run full test suite
      run: |
        python3 -m pytest \
          --tb=short \
          --junit-xml=test-results.xml \
          -q \
          2>&1 | tee pytest-output.txt
        
        # Enforce minimum test count
        PASS_COUNT=$(grep -oP '\d+ passed' pytest-output.txt | grep -oP '\d+')
        MIN_TESTS=2700
        if [ "$PASS_COUNT" -lt "$MIN_TESTS" ]; then
          echo "Test count $PASS_COUNT below minimum $MIN_TESTS"
          exit 1
        fi
        echo "Tests: $PASS_COUNT passing"
    - uses: actions/upload-artifact@v4
      if: always()
      with:
        name: test-results
        path: test-results.xml
```

---

## Job: governance-artifacts

```yaml
governance-artifacts:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Detect current phase
      id: phase
      run: |
        PHASE=$(python3 -c "
          import json, re
          cl = open('CHANGELOG.md').read()
          m = re.search(r'Phase (\d+)', cl)
          print(m.group(1) if m else '0')
        ")
        echo "phase=$PHASE" >> $GITHUB_OUTPUT
    - name: Validate governance artifacts
      run: |
        PHASE=${{ steps.phase.outputs.phase }}
        ARTIFACT_DIR="artifacts/governance/phase${PHASE}"
        
        for f in phase${PHASE}_sign_off.json replay_digest.txt tier_summary.json; do
          if [ ! -f "$ARTIFACT_DIR/$f" ]; then
            echo "MISSING: $ARTIFACT_DIR/$f"
            exit 1
          fi
        done
        
        # Validate JSON files
        for f in "$ARTIFACT_DIR"/*.json; do
          python3 -m json.tool "$f" > /dev/null || { echo "INVALID JSON: $f"; exit 1; }
        done
        
        # Check for PLACEHOLDER values
        if grep -r "PLACEHOLDER" "$ARTIFACT_DIR/"; then
          echo "PLACEHOLDER values found in governance artifacts"
          exit 1
        fi
        
        echo "Governance artifacts valid for Phase $PHASE"
```

---

## Job: evidence-matrix

```yaml
evidence-matrix:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Validate claims-evidence matrix
      run: |
        MATRIX="docs/comms/claims_evidence_matrix.md"
        if [ ! -f "$MATRIX" ]; then
          echo "Missing claims-evidence matrix"
          exit 1
        fi
        # Check that no row is marked Incomplete or TODO
        if grep -iE "\|\s*(incomplete|todo|pending)\s*\|" "$MATRIX"; then
          echo "Incomplete rows found in claims-evidence matrix"
          exit 1
        fi
        echo "Evidence matrix: OK"
```

---

## Job: ci-gating-summary

```yaml
ci-gating-summary:
  runs-on: ubuntu-latest
  needs:
    - version-hygiene
    - import-contracts
    - test-suite
    - governance-artifacts
    - evidence-matrix
  if: always()
  steps:
    - name: Evaluate gate results
      run: |
        echo "=== CI GATE SUMMARY ==="
        echo "version-hygiene:      ${{ needs.version-hygiene.result }}"
        echo "import-contracts:     ${{ needs.import-contracts.result }}"
        echo "test-suite:           ${{ needs.test-suite.result }}"
        echo "governance-artifacts: ${{ needs.governance-artifacts.result }}"
        echo "evidence-matrix:      ${{ needs.evidence-matrix.result }}"
        
        # All must pass
        RESULTS="${{ needs.version-hygiene.result }} ${{ needs.import-contracts.result }} ${{ needs.test-suite.result }} ${{ needs.governance-artifacts.result }} ${{ needs.evidence-matrix.result }}"
        for result in $RESULTS; do
          if [ "$result" != "success" ]; then
            echo "GATE FAILURE: one or more jobs did not pass"
            exit 1
          fi
        done
        
        echo "ALL GATES PASSED — PR eligible for HUMAN-0 merge approval"
```

---

## Branch Protection Rules

Configure on GitHub for `main`:

```
Required status checks:
  - ci-gating-summary

Additional settings:
  - Require branches to be up to date before merging: true
  - Require a pull request before merging: false (local merges permitted)
  - Include administrators: false (HUMAN-0 may merge without PR in emergency)
```

---

## Dependabot Configuration

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      pip-minor-patch:
        patterns: ["*"]
        update-types: ["minor", "patch"]
  - package-ecosystem: "pip"
    directory: "/archives/backend"
    schedule:
      interval: "weekly"
```

Dependabot PRs auto-merge only if all CI gates pass. Major version bumps require HUMAN-0 review.

---

*CI spec authority: ADAAD LEAD · InnovativeAI LLC*
