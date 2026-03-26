# SLA / SLO Sheet (Procurement Fastlane)

> Purpose: Buyer-facing reliability and support commitments summary for early procurement review.  
> Owner: Support + Operations + Legal  
> Version: 2026-03-26

## 1) Service Scope

- Covered service: ADAAD hosted control and evidence services (`[[define exact SKU/service scope in order form]]`).
- Exclusions: customer-managed systems, third-party outages outside provider control, scheduled maintenance windows (with notice).

## 2) Availability Targets (SLO)

| Metric | Target | Measurement Window | Notes |
|---|---|---|---|
| Monthly service availability | 99.9% | Calendar month | Excludes approved maintenance |
| API success rate | 99.9% | Calendar month | 5xx errors counted as failures |
| Median API latency (core endpoints) | <= 300 ms | Monthly p50 | Region/network dependent |
| Evidence pipeline completion | >= 99.5% | Calendar month | For in-scope events |

## 3) Support Response Targets

| Severity | Definition | Initial Response Target | Update Cadence | Target Resolution Objective |
|---|---|---|---|---|
| Sev 1 | Production outage / critical security impact | 1 hour | Every 2 hours | Continuous effort to mitigate |
| Sev 2 | Major degradation / key function impaired | 4 hours | Daily or as agreed | 1-2 business days target |
| Sev 3 | Partial impact / workaround exists | 1 business day | Every 2 business days | 5 business days target |
| Sev 4 | Informational / low impact request | 2 business days | Weekly or as agreed | Planned release cycle |

## 4) Escalation Path

1. Submit case via support channel with severity and impact summary.
2. Duty manager triage and acknowledge.
3. Engineering escalation for Sev 1/2.
4. Executive escalation available for sustained Sev 1 events.

## 5) Incident Communication Commitments

- Incident acknowledgement within severity response target.
- Status-page or direct customer updates for material incidents.
- Post-incident summary (RCA) for Sev 1 and qualifying Sev 2 incidents.

## 6) Service Credits (Fallback Structure)

| Monthly Availability | Service Credit |
|---|---|
| >= 99.9% | No credit |
| < 99.9% and >= 99.5% | 5% monthly fee credit |
| < 99.5% and >= 99.0% | 10% monthly fee credit |
| < 99.0% | 15% monthly fee credit |

- Credits are typically capped at a negotiated monthly maximum.
- Credit mechanism and exclusions are governed by MSA/order form language.

## 7) Customer Responsibilities

- Maintain accurate technical and incident contacts.
- Configure integration and authentication per implementation guide.
- Promptly provide incident reproduction data where available.
- Use supported versions and follow published change notices.

## 8) Change Management & Maintenance

- Planned maintenance windows are communicated in advance where practicable.
- Emergency maintenance is used only when required for service integrity/security.
- Material SLA/SLO changes follow contract change-control terms.
