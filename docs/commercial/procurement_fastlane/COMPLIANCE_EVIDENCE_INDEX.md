# Compliance Evidence Index (Procurement Fastlane)

> Purpose: A buyer-ready index of evidence artifacts and where to source each during diligence.  
> Owner: Security + Compliance + Legal  
> Last updated: 2026-03-26

## 1) How to Use This Index

- Provide this index in day-0 diligence package.
- Attach artifacts based on customer-required framework(s).
- If an artifact is NDA-restricted, mark as “Available under NDA.”

## 2) Evidence Catalog

| Control Domain | Evidence Artifact | Status | Source / Owner | Notes |
|---|---|---|---|---|
| Security program | Security policy set | Available under NDA | Security | Version-controlled policy bundle |
| Access control | RBAC/MFA standard + access review record | Available under NDA | Security + IT | Last review date included |
| Encryption | Encryption standard and key-management summary | Shareable summary | Security/Platform | Detailed config under NDA |
| Vulnerability mgmt | Vulnerability management SOP + remediation report sample | Available under NDA | Security Eng | SLA table included |
| Incident response | IR plan + tabletop summary | Available under NDA | Security | Redacted timeline sample |
| Logging/audit | Audit logging standard + sample evidence record | Available under NDA | Platform | Includes retention controls |
| Business continuity | Backup/restore and DR runbook summary | Available under NDA | Ops | Includes RTO/RPO target sheet |
| Privacy | DPA template + privacy notice | Shareable | Legal/Privacy | Include latest template versions |
| Subprocessors | Current subprocessor list | Shareable | Legal/Privacy | Include notice/update path |
| Product assurance | Architecture/security one-pager | Shareable | Product + Security | Use current one-pager |
| Commercial reliability | SLA/SLO sheet | Shareable | Support + Ops | Version tied to MSA/SOW |

## 3) Framework Mapping Starter (Customize Per Buyer)

| Framework | Typical Requested Controls | Evidence Rows to Attach |
|---|---|---|
| SOC 2-like review | Security, availability, confidentiality | Security program, access control, logging/audit, BC/DR |
| ISO 27001-aligned review | ISMS controls, risk treatment, supplier mgmt | Security policy set, vulnerability mgmt, subprocessors, IR |
| HIPAA-sensitive review | Access, audit, incident, BA terms | Access control, logging/audit, IR plan, DPA/legal terms |
| Financial services review | Change control, traceability, resilience | Product assurance, evidence artifacts, BC/DR, SLA/SLO |

## 4) Evidence Delivery Rules

- Provide only minimum necessary artifacts for stated review scope.
- Redact sensitive infrastructure details unless contractually required.
- Track every shared artifact in deal data room log.
- Ensure artifact version/date is visible on each file.

## 5) Day-0 Attachments (Default)

1. Architecture + security one-pager
2. Security questionnaire master answers
3. DPA/MSA fallback clauses (or current legal templates)
4. SLA/SLO sheet
5. This compliance evidence index
