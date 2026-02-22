# Governance Enforcement

Required branch protections for `main`:

- Required status checks must pass before merge.
- Required pull request approvals: minimum 2 reviewers for governance/security scope.
- Force pushes are disabled.
- Linear commit history is required.

Required CI checks:

- `pytest tests/ -q`
- Determinism lint (`python tools/lint_determinism.py ...`) when the lint file is present.
- Governance suite (`pytest tests/ -k governance -q`)
- Branch protection validation workflow.

- `Branch Protection Check` workflow validates required branch settings via GitHub API.

- Branch protection check requires `GITHUB_TOKEN` permission `administration: read` (granted by org admin).
- Branch protection check enforces `required_pull_request_reviews.required_approving_review_count >= 2`.
- Release evidence gate executes governance/sandbox tests with `PYTHONPATH=.` on Python 3.11 for parity with CI.


## Implementation status alignment (v0.70.0)

- CI enforces full suite, governance suite, and required determinism lint checks.
- Branch protection verification checks `required_status_checks`, `enforce_admins`, and a minimum of 2 required approvals.
- Release evidence gate runs replay-proof verification and governance/sandbox suites with `PYTHONPATH=.` on Python 3.11.
- Lineage continuity helper is wired conservatively: enforced when lineage_v2 chain resolves for the request agent; genesis/journal invariants remain authoritative fallback.
