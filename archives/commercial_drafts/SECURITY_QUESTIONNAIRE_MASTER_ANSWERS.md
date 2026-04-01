# Security Questionnaire — Master Answers (Procurement Fastlane)

> Owner: Security + Engineering + Legal  
> Version: 2026-03-26  
> Use: Copy/paste baseline responses into customer questionnaires and tailor fields marked `[[CUSTOMER-SPECIFIC]]`.

## 1) Company & Program Overview

- **Legal entity:** Innovative AI LLC
- **Product:** ADAAD (governed autonomous build and release control platform)
- **Primary use case:** Deterministic governance gating, replay verification, and release evidence generation for SDLC workflows.
- **Security contact:** `security@[[company-domain]]`
- **Privacy contact / DPO mailbox:** `privacy@[[company-domain]]`
- **Support contact:** `support@[[company-domain]]`

## 2) Data Handling & Privacy

### 2.1 Data classification
- We are designed to process software-delivery metadata (build/test events, policy outcomes, evidence references) rather than customer business PII by default.
- Customer-controlled data minimization is supported through scoped ingestion and field-level control.
- `[[CUSTOMER-SPECIFIC]]`: confirm whether customer will send any personal data and list categories.

### 2.2 Data residency and transfers
- Data location and transfer terms are defined contractually in the order form/DPA.
- Cross-border transfer mechanisms are documented in the DPA where applicable (for example, SCC-based transfer terms).
- `[[CUSTOMER-SPECIFIC]]`: specify required region(s).

### 2.3 Encryption
- Encryption in transit: TLS 1.2+.
- Encryption at rest: AES-256 (or cloud-provider equivalent managed encryption).
- Key management: cloud KMS/HSM-backed keys with controlled access and rotation policy.

### 2.4 Data retention and deletion
- Retention periods are customer-configurable by environment/tier.
- Deletion requests are supported per contractual timelines.
- Backups follow lifecycle policies and are purged according to retention configuration.

## 3) Access Control & Identity

- Access follows least privilege and role-based access control.
- Administrative access is restricted and auditable.
- MFA is enforced for privileged access.
- SSO/SAML/OIDC support is available for enterprise plans (`[[if enabled in SKU]]`).
- Access reviews are performed on a defined cadence and on role changes/offboarding.

## 4) Secure Development Lifecycle (SDLC)

- Source control changes are reviewed and validated through CI/CD controls.
- Determinism and replay integrity checks are part of release governance.
- Security fixes are prioritized by severity and tracked to closure.
- Dependency and artifact integrity verification is part of release checks.
- Release evidence is captured for auditability.

## 5) Application & Infrastructure Security

- Network segmentation and environment isolation are applied by environment tier.
- Secrets are stored in managed secret stores, not plaintext in source control.
- Logging and audit trails are immutable/tamper-evident by design patterns.
- Baseline hardening controls are verified via automated gates.

## 6) Monitoring, Detection, and Incident Response

- Centralized logging with alerting for security-relevant events.
- Defined incident response process with triage, containment, and post-incident review.
- Customer notifications for confirmed security incidents follow contractual/legal obligations.
- Tabletop or response process validation occurs on a recurring schedule.

## 7) Vulnerability Management

- Routine scanning of dependencies and images (`[[if containerized scope]]`).
- Risk-ranked remediation SLAs by severity.
- Critical issues receive expedited handling and out-of-band patching when required.
- Compensating controls documented when immediate patching is not feasible.

## 8) Third-Party Risk & Subprocessors

- Material subprocessors are documented and disclosed through the DPA or trust documentation.
- Third-party services are selected with security due diligence and contractual protections.
- Changes to subprocessors follow notification terms in applicable agreements.

## 9) Business Continuity & Disaster Recovery

- Backup strategy and restoration procedures are documented.
- Recovery objectives (RTO/RPO) are defined by service tier and environment.
- Recovery testing is performed periodically and tracked.

## 10) Compliance & Assurance

- Compliance mappings and evidence are maintained in an indexed package (see `COMPLIANCE_EVIDENCE_INDEX.md`).
- Customer audit requests can be supported under NDA and contractual terms.
- Policy artifacts are version-controlled and available upon request.

## 11) Common Questionnaire Short Answers (Copy/Paste)

- **Do you encrypt data in transit and at rest?** Yes (TLS 1.2+ in transit, AES-256 or cloud equivalent at rest).
- **Do you enforce MFA for admin users?** Yes.
- **Do you support SSO?** Yes for enterprise plans (`[[confirm SKU/config]]`).
- **Do you maintain audit logs?** Yes, with tamper-evident and retention-controlled logging patterns.
- **Do you have incident response procedures?** Yes, with defined notification workflow.
- **Do you use subprocessors?** Yes, as listed in contractual/privacy documentation.
- **Can customers request deletion/export?** Yes, subject to contractual scope and retention settings.

## 12) Redlines / Approval Required Before Sending

- Legal review required for: indemnities, liability caps, data transfer annexes, security addenda.
- Security review required for: penetration testing details, architecture deep-dive, key management specifics.
- Sales may send this template only after replacing all `[[CUSTOMER-SPECIFIC]]` placeholders.
