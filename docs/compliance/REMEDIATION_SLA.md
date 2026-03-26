# Security Remediation SLA

## Purpose

This policy defines mandatory fix timelines, governance escalation, and disclosure rules for security findings across API/auth/governance surfaces.

## Severity Classification and Fix Deadlines

Time-to-remediate starts at the timestamp when a finding is marked **Confirmed**.

| Severity | First response (acknowledge + owner) | Containment target | Full remediation target | Max extension |
| --- | --- | --- | --- | --- |
| Critical | 4 hours | 24 hours | 7 calendar days | 3 days (security lead + executive approval) |
| High | 1 business day | 3 calendar days | 14 calendar days | 7 days (security lead approval) |
| Medium | 3 business days | As needed by triage | 45 calendar days | 14 days (documented risk acceptance) |
| Low | 5 business days | Not typically required | 90 calendar days | 30 days (documented backlog rationale) |
| Informational | 10 business days | N/A | Next planned governance/docs cycle | N/A |

## Mandatory Workflow

1. **Intake:** log finding with severity, affected assets, exploitability, and reporter context.
2. **Validation:** reproduce and confirm impact under controlled conditions.
3. **Assignment:** name remediation owner and due date from SLA table.
4. **Containment:** apply mitigations for Critical/High before permanent fix when needed.
5. **Remediation:** land fix with tests and governance evidence updates.
6. **Verification:** confirm closure with independent reviewer and CI controls.
7. **Closure:** mark complete only when code, evidence, and disclosure obligations are satisfied.

## CI Governance Enforcement

- SLA breach status must be visible in governance reporting.
- Critical/High open findings block release promotion unless an explicit, signed risk acceptance is recorded.
- Quarterly security review completion and artifact publication are required controls in CI governance policy.

## Public-Facing Disclosure Policy

### Coordinated Vulnerability Disclosure

- Report intake channel: security contact process in `TRUST_CENTER.md`.
- Reporter acknowledgement target: within **3 business days**.
- Status updates: at least every **7 calendar days** for active High/Critical investigations.

### Disclosure Timelines

- **Critical/High:** public advisory target within **30 days** of confirmation, or sooner if actively exploited.
- **Medium:** public advisory in next regular security bulletin cycle (target **90 days**).
- **Low/Informational:** roll-up disclosure in periodic transparency update.

### Advisory Content Minimums

Each public advisory should include:

- impacted component/surface;
- affected versions or deployment windows;
- severity and impact summary;
- mitigation/remediation guidance;
- credit (if reporter consents);
- disclosure date and revision history.

### Exceptions

Disclosure may be delayed only when immediate publication would materially increase exploitation risk or violate legal constraints. Delays require documented approval by security leadership and legal counsel.
