# Sales Playbook

## Purpose
This playbook standardizes how we qualify, run, and convert pilots into annual contracts using objective evidence from product telemetry.

---

## 1) Target ICP by Segment

### Segment A: Regulated Enterprise (Financial Services, Healthcare, Insurance)
- **Company profile:** 1,000+ employees, dedicated security/compliance teams, multi-region operations.
- **Buying committee:** CIO/CTO, CISO, VP Engineering, Procurement, Legal.
- **Pain profile:** High change-risk, strict auditability needs, cross-team release coordination issues.
- **Primary use cases:** Governance enforcement, deterministic release validation, audit evidence automation.
- **Trigger events:** Audit findings, failed releases, merger integration, policy modernization.
- **Typical contract shape:** 12–36 month term, enterprise security/legal review, SSO/SCIM requirement.

### Segment B: Mid-Market Platform Teams (B2B SaaS)
- **Company profile:** 200–1,000 employees, 5–30 platform/security engineers.
- **Buying committee:** VP Engineering, Head of Platform, Security Lead, Finance.
- **Pain profile:** Slow release cycles, rising incident cost, fragmented governance controls.
- **Primary use cases:** CI governance gates, release evidence completeness, replay/determinism checks.
- **Trigger events:** Growth-stage scale issues, customer security escalations, SLA pressure.
- **Typical contract shape:** 12-month annual with optional expansion by team/repo count.

### Segment C: Public Sector / Government Contractors
- **Company profile:** Prime contractors and agencies with formal controls and procurement workflows.
- **Buying committee:** Program Manager, ISSO, Procurement Officer, Legal.
- **Pain profile:** Proof-of-control requirements, rigorous accreditation artifacts, chain-of-custody constraints.
- **Primary use cases:** Immutable evidence trails, policy-based release enforcement, compliance reporting.
- **Trigger events:** New program award, control-gap remediation, authority-to-operate deadlines.
- **Typical contract shape:** Pilot-to-annual conversion with strict documentation milestones.

### Segment D: AI-Native Product Organizations
- **Company profile:** AI-first teams shipping model-backed features weekly or faster.
- **Buying committee:** CTO, AI Platform Lead, Security/Governance owner.
- **Pain profile:** Non-deterministic outcomes, difficult rollback/replay validation, governance drift.
- **Primary use cases:** Determinism controls, policy checkpointing, production telemetry-backed go/no-go.
- **Trigger events:** Reliability incidents, model governance requirements, enterprise customer demands.
- **Typical contract shape:** Annual subscription with usage and environment-based expansion.

---

## 2) Discovery Call Checklist

Use this checklist in every first call. A deal is not qualified until all critical fields are completed.

### A. Business Qualification
- [ ] What strategic initiative is this tied to (risk reduction, release velocity, compliance, cost)?
- [ ] Is there an executive sponsor with budget authority?
- [ ] What is the commercial deadline (quarter-end, audit date, renewal event)?
- [ ] Is there an approved budget range for pilot and annual rollout?

### B. Technical Qualification
- [ ] Current SDLC and CI/CD stack documented.
- [ ] Repo topology and deployment model understood (mono/multi repo, cloud/on-prem/hybrid).
- [ ] Security/compliance boundaries identified.
- [ ] Existing telemetry sources confirmed (CI logs, deploy events, incident data, policy events).

### C. Pain and Baseline
- [ ] Quantified current state: release frequency, change failure rate, MTTR, audit prep hours.
- [ ] Top 3 operational risks ranked by business impact.
- [ ] Recent examples of failed/blocked releases captured.
- [ ] Baseline measurement window agreed (typically prior 30–90 days).

### D. Pilot Readiness
- [ ] Pilot owner assigned (customer-side technical lead).
- [ ] Legal/procurement path identified.
- [ ] Security review requirements identified (questionnaire, pen test, DPA, etc.).
- [ ] Success criteria tentatively agreed and documented.

### E. Conversion Path
- [ ] Annual contract path and required approvers mapped.
- [ ] Expansion scope identified (teams, repos, environments).
- [ ] Contracting timeline and blockers captured.

---

## 3) Two-Week Paid Pilot Template

**Pilot term:** 14 calendar days  
**Pilot type:** Paid, fixed-scope, success-metric driven  
**Pilot price:** Set per segment and environment complexity

### Pilot Scope (Fixed)
1. Enable product in one production-like environment.
2. Integrate telemetry export and baseline ingest.
3. Activate agreed governance gates for one defined workflow.
4. Run at least one real release cycle through gated flow.
5. Deliver quantified value proof report and executive readout.

### Week-by-Week Plan

#### Week 1 (Setup + Baseline)
- Day 1–2: Kickoff, technical onboarding, data access confirmation.
- Day 3–4: Baseline metrics ingestion and validation.
- Day 5: First governance-gated run and issue triage.

**Week 1 deliverables**
- Pilot plan sign-off
- Baseline metrics snapshot
- Integration checklist complete

#### Week 2 (Execution + Value Proof)
- Day 6–9: Operate in live workflow, measure outcomes.
- Day 10–11: Joint review of blocked/allowed changes and policy outcomes.
- Day 12–13: Draft conversion recommendation and ROI summary.
- Day 14: Executive readout and annual proposal presentation.

**Week 2 deliverables**
- Final telemetry export package
- Value proof scorecard
- Annual conversion decision memo

### Roles and Responsibilities
- **Customer sponsor:** Owns business outcome and decision timeline.
- **Customer technical lead:** Owns deployment and data access.
- **Vendor CSM/AE:** Owns commercial process and conversion package.
- **Vendor solutions engineer:** Owns implementation and metric integrity.

### Pilot Commercial Terms (Template)
- Paid pilot fee credited toward year-1 annual contract upon conversion within 30 days.
- Scope-limited support and defined environment cap.
- No custom feature development included unless separately scoped.

---

## 4) Success Metrics Required to Convert to Annual Contract

All conversion metrics are measured against pre-pilot baseline and validated in telemetry export.

### Mandatory Conversion Thresholds
- **Governance coverage:** ≥ 90% of in-scope release workflows run through active policy gates.
- **Evidence completeness:** 100% of in-scope releases produce complete evidence records.
- **Determinism/replay integrity:** 0 unresolved replay divergence for in-scope releases.
- **Operational improvement:** Achieve at least 2 of the following:
  - ≥ 20% reduction in release validation cycle time
  - ≥ 25% reduction in policy-related deployment incidents
  - ≥ 30% reduction in manual audit evidence collection effort
- **Stakeholder adoption:** Technical lead + executive sponsor sign-off documented.
- **Security/legal viability:** No unresolved blocker in security or legal review path.

### Conversion Decision Rule
Convert to annual contract when all mandatory thresholds are met and financial terms are approved by both parties.

---

## 5) Legal & Procurement Packet Checklist

Prepare this packet by Day 5 of the pilot to avoid conversion delays.

### Commercial Documents
- [ ] Order form / quote with pilot credit terms
- [ ] Annual subscription proposal with SKU assumptions
- [ ] Pricing sheet and expansion model

### Legal Documents
- [ ] Master Services Agreement (MSA) or equivalent
- [ ] Data Processing Addendum (DPA), if applicable
- [ ] Security addendum / information security exhibit
- [ ] SLA / support policy
- [ ] Acceptable use and privacy documentation

### Security & Compliance Artifacts
- [ ] Security questionnaire response set
- [ ] Architecture/security overview
- [ ] Data flow diagram (including sub-processors where required)
- [ ] Latest penetration test summary or equivalent assurance artifact
- [ ] Compliance mappings (SOC 2 / ISO 27001 / other, where applicable)

### Procurement Workflow Items
- [ ] Vendor onboarding form
- [ ] Tax and banking forms
- [ ] Insurance certificates
- [ ] Procurement system registration details
- [ ] Signature authority matrix and approval routing

---

## 6) Standardized “Value Proof” Export (from Product Telemetry)

Use this standard export for every pilot so conversion decisions are evidence-based and comparable.

### Export Requirements
- **Format:** CSV + JSON bundle
- **Window:** Baseline period + full pilot period
- **Granularity:** Per release/workflow event
- **Integrity:** Timestamped, immutable export hash included

### Required Fields
| Field | Description |
|---|---|
| `customer_id` | Customer/account identifier |
| `pilot_id` | Unique pilot identifier |
| `environment` | Environment name (staging/prod-like) |
| `repo_or_service` | Repository or service identifier |
| `workflow_id` | CI/CD workflow identifier |
| `release_id` | Release/deployment identifier |
| `event_timestamp_utc` | UTC event timestamp |
| `policy_gate_result` | `allow` / `block` / `warn` |
| `policy_ids_triggered` | Policies evaluated/triggered |
| `evidence_record_id` | Linked evidence artifact ID |
| `evidence_complete` | Boolean completeness flag |
| `replay_status` | `pass` / `diverged` / `not_applicable` |
| `validation_cycle_minutes` | End-to-end validation duration |
| `incident_linked` | Boolean for post-release incident linkage |
| `manual_audit_hours_estimate` | Estimated manual audit prep effort |
| `export_hash_sha256` | Integrity hash for exported row set |

### Standard Scorecard Outputs
- Governance coverage (% in-scope workflows gated)
- Evidence completeness (% complete evidence records)
- Replay integrity (% pass, count diverged)
- Validation cycle time improvement (% delta vs baseline)
- Incident rate delta (% delta vs baseline)
- Manual audit effort delta (% delta vs baseline)

### Executive Value Narrative (Attach to Export)
- Business objective targeted
- Baseline vs pilot quantified deltas
- Risks reduced and controls strengthened
- Annual rollout recommendation with expected 12-month impact

---

## 7) Handoff Artifacts for Annual Contracting
- Final value proof export bundle (CSV/JSON + scorecard + hash)
- Pilot closeout summary and conversion recommendation
- Completed legal/procurement packet
- Annual order form ready for signature

This playbook is mandatory for all paid pilots that are intended to convert to annual subscription contracts.
