# Diagram Ownership

This file defines canonical ownership and update boundaries for shared documentation diagrams.

Diagrams are normative representations of governance and architecture boundaries; they must not contradict runtime contracts.

## Canonical diagrams

| Diagram | Canonical file | Conceptual boundary | Primary owners |
| --- | --- | --- | --- |
| Governance flow | `docs/assets/governance-flow.svg` | End-to-end governed mutation lifecycle from proposal to evidence archival. | Governance + Runtime maintainers |
| Governance evidence flow | `docs/assets/adaad-governance-flow.svg` | Policy/replay gate ordering and enforcement evidence path. | Governance maintainers |
| Architecture summary | `docs/assets/architecture-simple.svg` | Layer boundaries and ownership across trust/governance/execution surfaces. | Architecture + Runtime maintainers |

## Update policy

1. Update the canonical diagram asset first.
2. Verify all embedding docs still match the updated concept and terminology.
3. If semantics changed (not just styling), update related captions/legends in:
   - `README.md`
   - `docs/ARCHITECTURE_CONTRACT.md`
   - `docs/GOVERNANCE_ENFORCEMENT.md`
   - `docs/governance/founders_law_v2.md`
4. Include diagram update rationale in PR description when conceptual meaning changes.

## Drift prevention checklist

- [ ] Terminology is aligned between diagram labels and surrounding doc text.
- [ ] Evidence path wording remains consistent with replay and ledger constraints.
- [ ] Layer boundaries in docs remain consistent with architecture contract terminology.
- [ ] Diagram version or update date remains current if semantic changes occur.


## Version tracking

When a diagram semantic meaning changes, append a short note to the owning PR and update this file with a date stamp in the PR description (for audit traceability).
