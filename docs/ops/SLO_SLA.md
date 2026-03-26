# ADAAD Operational SLO/SLA Policy

## 1) Scope and Intent

This document defines operational SLO/SLA commitments for ADAAD service SKUs and ties each commitment to currently available telemetry and governance-health signals.

The policy is **fail-closed for governance posture**: service reliability is considered non-compliant when governance-health floors are violated, even if infrastructure-level uptime appears healthy.

## 2) SKU Uptime Targets

Uptime is measured per calendar month.

| SKU | Intended consumers | Monthly availability SLO | Error budget/month | Notes |
|---|---|---:|---:|---|
| Community | Public/free tier usage, best-effort operations | 99.50% | 3h 39m 12s | Lower operational guarantee; same governance fail-closed posture. |
| Standard | Internal production workloads | 99.90% | 43m 50s | Default managed operations objective. |
| Enterprise | Mission-critical and contractual workloads | 99.95% | 21m 55s | Highest service objective; fastest incident-response SLA. |

### 2.1 Availability determination (control-plane + governance)

A minute is counted **available** only when all are true:

1. Health endpoint responds successfully (`/health` for MCP server and other service-specific health routes).  
2. Key read-only governance telemetry routes are available (`/evolution/telemetry-health`, `/metrics/review-quality`).  
3. Governance health posture is not in a blocked condition (determinism and review-quality floors remain above thresholds).

## 3) Key API Latency and Error Objectives

These objectives apply to the key operational APIs.

| API/group | p50 latency objective | p95 latency objective | Error-rate objective | Source baseline |
|---|---:|---:|---:|---|
| Critical read GETs (`/api/health`, `/api/nexus/health`, `/governance/health`, `/api/status`) | <= 80 ms | <= 160 ms | 0.0% | `config/server_endpoint_perf_budgets.v1.json` |
| Websocket connect (`/ws/events`) | <= 120 ms | <= 220 ms | 0.0% | `config/server_endpoint_perf_budgets.v1.json` |
| MCP `/health` | <= 80 ms | <= 160 ms | 0.0% | Aligned to critical read GETs |
| MCP `/tools/list`, `/evolution/telemetry-health` | <= 120 ms | <= 220 ms | <= 0.1% | Aligned to lightweight control-plane reads |
| MCP `/mutation/propose` | <= 250 ms | <= 500 ms | <= 0.5% | Includes proposal validation and queue append path |

> Note: endpoint budgets for the first two rows are already versioned in repo performance policy and enforced by benchmark/regression tooling.

## 4) Severity Definitions and Response-Time Commitments

| Severity | Definition | Initial acknowledgement | Mitigation start | Update cadence | Target containment |
|---|---|---:|---:|---:|---:|
| Sev-1 (Critical) | Multi-SKU outage, governance health block, replay divergence trend, or widespread write-path failure | <= 15 min | <= 30 min | Every 30 min | <= 4 hours |
| Sev-2 (High) | Partial outage, elevated API error rate, sustained SLO breach risk | <= 30 min | <= 60 min | Every 60 min | <= 1 business day |
| Sev-3 (Medium) | Degraded non-critical path, warning-level governance signals | <= 4 hours | <= 1 business day | Daily | <= 5 business days |
| Sev-4 (Low) | Cosmetic/docs/non-user-impacting issue | <= 1 business day | Planned backlog | Weekly | Planned release |

### 4.1 Governance-triggered severity escalation

Any of the following immediately escalates to at least **Sev-2**, and to **Sev-1** when persistent or coupled with API impact:

- `reviewed_within_sla_percent < 95%`.
- `largest_reviewer_share > 0.60`.
- `override_rate_percent > 20%`.
- Replay determinism failures (`ReplayVerificationEvent` failures) or governance-health blocked status.

## 5) Maintenance Windows and Status Communication Protocol

## 5.1 Planned maintenance windows

- **Standard window:** Saturdays 02:00–04:00 UTC.
- **Emergency maintenance:** Any time with Sev-1 justification and explicit incident record.

Planned maintenance communication minimums:

- T-72h: announce scope, expected impact, rollback path.
- T-24h: reminder with exact start/end and impacted APIs.
- T+0h: start notice.
- T+End: completion note with outcome and any residual risk.

## 5.2 Incident/status communication protocol

1. Create/attach incident identifier.
2. Publish user-visible status by severity window (from section 4).
3. Include at minimum:
   - impacted SKUs,
   - impacted APIs,
   - start time (UTC),
   - current mitigation action,
   - next update ETA.
4. Publish final RCA summary for Sev-1/Sev-2 within 5 business days.

## 6) Telemetry Backing: Existing Signals

The following telemetry/governance signals already exist and should be used immediately for SLO posture reporting.

| SLO/SLA area | Existing telemetry signal | Where it comes from | Compliance use |
|---|---|---|---|
| Review SLA quality | `governance_review_quality` events (`latency_seconds`, `sla_seconds`, `within_sla`, reviewer concentration, override rates via summary) | `runtime/governance/review_quality.py` + metrics JSONL sink | Governance SLO pass/fail and severity escalation input |
| Determinism/replay health | `ReplayVerificationEvent` in metrics lineage rollups | `runtime/metrics_analysis.py` rolling determinism score | Hard reliability guardrail for governance-safe uptime |
| Governance debt posture | `GOVERNANCE_DEBT_EVENT_TYPE` (`compound_debt_score`) | `runtime/governance/review_quality.py` summary integration | Leading indicator for reliability risk |
| Evolution health indicators | `/evolution/telemetry-health` (`acceptance_rate`, `weight_bounds`, `plateau_frequency`, `agent_distribution`, `bandit_activation`) | `runtime/mcp/evolution_pipeline_tools.py` + `runtime/autonomy/epoch_telemetry.py` | Governance health context for operational risk |
| API performance budgets | Versioned endpoint budgets + regression thresholds | `config/server_endpoint_perf_budgets.v1.json` | Latency/error objective source-of-truth |
| Metrics envelope integrity | Structured fields (`timestamp`, `event`, `level`, `payload`) | `runtime/metrics.py` | Consistent compliance calculations across events |

## 7) What Must Be Measured for Full Compliance

The current telemetry provides strong governance and benchmark evidence, but monthly SLA-grade compliance requires the following additional **continuous** measurements:

1. **Per-endpoint request telemetry (production traffic):**
   - route,
   - status code,
   - latency_ms,
   - response_size_bytes,
   - timestamp,
   - SKU attribution.
2. **Availability probe ledger:**
   - 1-minute synthetic checks per key endpoint,
   - explicit pass/fail per minute,
   - probe source/region,
   - maintenance-window exclusion markers.
3. **Error-rate denominator integrity:**
   - total requests and failed requests per endpoint per 1-minute bucket.
4. **Status communication evidence:**
   - incident timeline events,
   - outbound status updates with timestamps,
   - acknowledgement/mitigation SLA timers.
5. **Monthly compliance rollup artifact:**
   - per-SKU availability,
   - per-API latency/error percentile tables,
   - governance SLO results,
   - incident/SLA attainment report.

## 8) Compliance Calculation Rules

- **Availability %** = (eligible available minutes / eligible total minutes) × 100.  
- Planned maintenance minutes are excluded only when communications followed section 5.1 protocol.  
- Governance hard-fail windows (determinism/governance blocked state) are counted unavailable for Standard and Enterprise SKUs.  
- Monthly compliance report is required by the 3rd business day of the next month.

