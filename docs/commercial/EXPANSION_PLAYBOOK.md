# Expansion Playbook

## Purpose
This playbook defines objective expansion triggers, a repeatable QBR operating model, and upgrade recommendation rules for Customer Success, Account Management, and Solutions teams.

---

## 1) Expansion Trigger Definitions

Expansion recommendations must be evidence-backed using the prior two completed quarters (or at least 90 days for newer customers).

### A. Seat Growth Threshold

Trigger an expansion recommendation when **either** of the following is true:

- **Sustained growth:** Active named users increase by **>= 25% quarter-over-quarter**.
- **Capacity pressure:** Utilization exceeds **85% of contracted seats** for **30 consecutive days**.

**Evidence required:**
- Active named users by month
- Contracted seat count
- 30-day utilization trendline

### B. Usage Growth Threshold

Trigger an expansion recommendation when **either** of the following is true:

- **Workflow growth:** In-scope governed workflows increase by **>= 30% quarter-over-quarter**.
- **Release volume growth:** Monthly governed release events increase by **>= 40% versus baseline quarter**.

**Evidence required:**
- Governed workflow count by month
- Release event volume by month
- Baseline quarter comparison table

### C. Compliance / Reporting Feature Usage

Trigger an expansion recommendation when **all** of the following are true:

- Customer enables compliance or reporting features in production (e.g., evidence export, audit package generation, control mapping).
- Feature is used in at least **2 monthly cycles** within a quarter.
- Customer requests additional reporting scope, retention, or executive/compliance-facing dashboards.

**Evidence required:**
- Feature enablement date
- Usage events by feature and month
- Request log for enhanced reporting/compliance scope

### D. Multi-Environment Deployment Requests

Trigger an expansion recommendation when **either** of the following is true:

- Customer asks to onboard **2+ additional environments** (e.g., staging + prod, prod-us + prod-eu).
- Customer requests cross-region or multi-business-unit deployment that exceeds current plan boundaries.

**Evidence required:**
- Environment request inventory
- Current contracted environment entitlement
- Proposed target state (environments, regions, business units)

---

## 2) Expansion Qualification Criteria

A recommended upgrade should only be submitted when all criteria below are met:

1. **Business value confirmed:** At least one business KPI improved (velocity, risk reduction, audit readiness, or cost efficiency).
2. **Operational readiness confirmed:** Customer has an executive sponsor and technical owner for expanded scope.
3. **No unresolved blocker:** Security, legal, or procurement blockers are either closed or have target dates.
4. **Commercial alignment:** Proposed SKU/packaging maps directly to observed usage and next-quarter goals.

If any criterion is missing, maintain customer on current plan and open a remediation success plan.

---

## 3) QBR Cadence and Roles

- **Cadence:** Quarterly (standard), with monthly health checks for high-growth accounts.
- **Owner:** Customer Success Manager (CSM)
- **Contributors:** Account Executive (AE), Solutions Engineer (SE), Customer technical owner, Executive sponsor
- **Output:** QBR package, expansion recommendation (if triggered), and 90-day success plan

---

## 4) QBR Template (Customer-Facing)

Use this template in all QBRs.

### QBR Header
- Customer:
- Quarter reviewed:
- CSM:
- AE:
- Executive sponsor:
- Technical owner:

### Section 1 — Objectives and Outcomes
- Strategic objectives for the quarter
- Progress status per objective (Met / Partially Met / Not Met)
- Top business outcomes achieved

### Section 2 — Adoption and Value Metrics
- Active seats (contracted vs used)
- Governed workflows and release volume trends
- Evidence/compliance feature usage summary
- Environment footprint and deployment coverage
- KPI deltas vs prior quarter

### Section 3 — Risks and Blockers
- Open risks (technical, operational, commercial)
- Severity and owner
- Mitigation plan and target date

### Section 4 — Expansion Trigger Review
- Seat growth trigger status: Met / Not Met
- Usage growth trigger status: Met / Not Met
- Compliance/reporting trigger status: Met / Not Met
- Multi-environment trigger status: Met / Not Met
- Trigger evidence links

### Section 5 — Next-Quarter Plan
- Joint priorities
- Adoption milestones
- Success criteria and owners
- Executive decision date

---

## 5) Internal QBR Prep Template (CSM/AE)

Use this before each customer QBR.

### Data Preparation Checklist
- [ ] Seat utilization report generated
- [ ] Workflow/release usage report generated
- [ ] Compliance/reporting usage report generated
- [ ] Environment request and entitlement map updated
- [ ] Customer goals and renewal timeline confirmed

### Internal Readout Fields
- Account health score:
- Renewal date:
- Current plan/SKU:
- Expansion potential (Low / Medium / High):
- Recommended path (No change / Targeted expansion / Full upgrade):
- Commercial owner:
- Risks to decision:

---

## 6) Upgrade Recommendation Rules

Apply these rules after every QBR.

### Rule 1 — Seat-Driven Upgrade
Recommend seat expansion when seat growth threshold is met and sustained for at least one full quarter.

### Rule 2 — Usage-Driven Upgrade
Recommend usage-tier upgrade when workflow or release growth thresholds are met and customer projects continued growth in next quarter.

### Rule 3 — Compliance/Reporting Upgrade
Recommend compliance/reporting package upgrade when compliance/reporting trigger is met and customer requires broader audit outputs, control mappings, or retention/reporting depth.

### Rule 4 — Environment Upgrade
Recommend environment expansion when multi-environment trigger is met and requested target state exceeds current contractual environment limits.

### Rule 5 — Combined Trigger Escalation
If **2 or more triggers** are met in the same QBR period, recommend a bundled upgrade path with phased onboarding plan and executive review within 30 days.

### Rule 6 — Do-Not-Upgrade Guardrail
Do **not** recommend upgrade when adoption quality is weak (e.g., sustained low usage, unresolved blockers, or absent executive sponsorship). Instead, open a corrective success plan and reassess next QBR.

---

## 7) Recommendation Output Format

Every expansion recommendation must include:

1. **Trigger summary:** Which trigger(s) were met
2. **Evidence summary:** Quantified metrics and date range
3. **Proposed upgrade:** SKU/packaging change
4. **Expected business impact:** KPIs expected to improve
5. **Implementation plan:** Owners, milestones, and timeline
6. **Decision deadline:** Date and stakeholder approvers

---

## 8) 90-Day Post-Upgrade Success Plan Template

- Upgrade start date:
- Scope activated:
- New success KPIs:
- Milestones at Day 30 / Day 60 / Day 90:
- Adoption owner(s):
- Risk review cadence:
- Executive check-in date:

A post-upgrade QBR addendum should be published by Day 90 to validate realized value and confirm retention trajectory.
