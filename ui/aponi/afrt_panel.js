/**
 * ADAAD Aponi — AFRT Panel (Phase 92 / INNOV-08)
 * ─────────────────────────────────────────────────
 * Real-time Adversarial Fitness Red Team findings dashboard.
 *
 * Displays:
 *   • Live AFRT_VERDICT WebSocket events from the CEL
 *   • Per-proposal adversarial case stream (1–5 cases each)
 *   • RedTeamFindingsReport: PASS / RETURNED verdict badges
 *   • Uncovered path surfaces that triggered adversarial probing
 *   • Report hash chain (AFRT-DETERM-0 auditability)
 *   • Ledger commit status (AFRT-LEDGER-0 trace_committed indicator)
 *
 * Constitutional wire-in:
 *   • Connects to GET /governance/afrt/findings  (REST snapshot)
 *   • Subscribes to AFRT_VERDICT WebSocket events (live stream)
 *   • AFRT-0: approval_emitted is NEVER rendered as approval;
 *     any approval_emitted=true is surfaced as a CONSTITUTIONAL VIOLATION alert.
 *
 * Self-contained: injects CSS, owns state, graceful-degrades if endpoint absent.
 */
(function (global) {
  "use strict";

  /* ══════════════════════════════════════════════════════════════════════
     CONSTANTS / CONFIG
  ══════════════════════════════════════════════════════════════════════ */
  const AFRT_VERSION        = "92.0";
  const FINDINGS_ENDPOINT   = "/governance/afrt/findings";
  const WS_EVENT_TYPE       = "AFRT_VERDICT";
  const MAX_FINDINGS_SHOWN  = 30;   // rolling window
  const POLL_INTERVAL_MS    = 8000; // fallback poll when WS unavailable

  /* ══════════════════════════════════════════════════════════════════════
     CSS INJECTION
  ══════════════════════════════════════════════════════════════════════ */
  const AFRT_CSS = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
      --afrt-bg:         #0b0c0f;
      --afrt-panel:      #16181d;
      --afrt-border:     #2b2f36;
      --afrt-text:       #f5f7fa;
      --afrt-muted:      #8c919b;
      --afrt-pass:       #22c55e;
      --afrt-returned:   #f97316;
      --afrt-violation:  #ef4444;
      --afrt-accent:     #3b82f6;
      --afrt-mono:       'JetBrains Mono', 'Courier New', monospace;
      --afrt-sans:       'Inter', Arial, sans-serif;
      --afrt-glow-pass:  0 0 18px rgba(34,197,94,0.18);
      --afrt-glow-ret:   0 0 18px rgba(249,115,22,0.18);
      --afrt-glow-viol:  0 0 24px rgba(239,68,68,0.35);
    }

    .afrt-wrap {
      background: var(--afrt-bg);
      color: var(--afrt-text);
      font-family: var(--afrt-sans);
      padding: 20px;
      border-radius: 10px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      animation: afrt-enter 0.4s cubic-bezier(.22,1,.36,1) both;
    }
    @keyframes afrt-enter {
      from { opacity: 0; transform: translateY(12px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    /* ── Header ─────────────────────────────────────────────────────── */
    .afrt-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--afrt-border);
      padding-bottom: 12px;
    }
    .afrt-header-title {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .afrt-header-title h2 {
      font-size: 18px;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.3px;
    }
    .afrt-version-badge {
      background: var(--afrt-panel);
      border: 1px solid var(--afrt-border);
      color: var(--afrt-muted);
      font-family: var(--afrt-mono);
      font-size: 10px;
      padding: 2px 7px;
      border-radius: 4px;
    }
    .afrt-live-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--afrt-pass);
      box-shadow: 0 0 8px rgba(34,197,94,0.6);
      animation: afrt-pulse 2s ease-in-out infinite;
    }
    .afrt-live-dot.offline {
      background: var(--afrt-muted);
      box-shadow: none;
      animation: none;
    }
    @keyframes afrt-pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50%       { opacity: 0.5; transform: scale(0.85); }
    }

    /* ── Stats bar ───────────────────────────────────────────────────── */
    .afrt-stats {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }
    .afrt-stat-card {
      background: var(--afrt-panel);
      border: 1px solid var(--afrt-border);
      border-radius: 8px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .afrt-stat-label {
      font-size: 10px;
      color: var(--afrt-muted);
      text-transform: uppercase;
      letter-spacing: 0.6px;
    }
    .afrt-stat-value {
      font-family: var(--afrt-mono);
      font-size: 22px;
      font-weight: 600;
      line-height: 1;
    }
    .afrt-stat-value.pass    { color: var(--afrt-pass); }
    .afrt-stat-value.ret     { color: var(--afrt-returned); }
    .afrt-stat-value.neutral { color: var(--afrt-text); }
    .afrt-stat-value.viol    { color: var(--afrt-violation); }

    /* ── Findings feed ───────────────────────────────────────────────── */
    .afrt-feed-header {
      font-size: 12px;
      color: var(--afrt-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .afrt-feed {
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-height: 520px;
      overflow-y: auto;
      padding-right: 4px;
    }
    .afrt-feed::-webkit-scrollbar { width: 4px; }
    .afrt-feed::-webkit-scrollbar-track { background: transparent; }
    .afrt-feed::-webkit-scrollbar-thumb { background: var(--afrt-border); border-radius: 2px; }

    /* ── Finding card ────────────────────────────────────────────────── */
    .afrt-finding {
      background: var(--afrt-panel);
      border: 1px solid var(--afrt-border);
      border-radius: 8px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      transition: border-color 0.2s;
    }
    .afrt-finding.pass     { border-left: 3px solid var(--afrt-pass);      box-shadow: var(--afrt-glow-pass); }
    .afrt-finding.returned { border-left: 3px solid var(--afrt-returned);  box-shadow: var(--afrt-glow-ret); }
    .afrt-finding.violation{ border-left: 3px solid var(--afrt-violation); box-shadow: var(--afrt-glow-viol); }

    .afrt-finding-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .afrt-proposal-id {
      font-family: var(--afrt-mono);
      font-size: 11px;
      color: var(--afrt-accent);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 280px;
    }
    .afrt-verdict-badge {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
      padding: 3px 10px;
      border-radius: 4px;
      white-space: nowrap;
    }
    .afrt-verdict-badge.pass {
      background: rgba(34,197,94,0.15);
      color: var(--afrt-pass);
      border: 1px solid rgba(34,197,94,0.3);
    }
    .afrt-verdict-badge.returned {
      background: rgba(249,115,22,0.15);
      color: var(--afrt-returned);
      border: 1px solid rgba(249,115,22,0.3);
    }
    .afrt-verdict-badge.violation {
      background: rgba(239,68,68,0.2);
      color: var(--afrt-violation);
      border: 1px solid rgba(239,68,68,0.5);
      animation: afrt-viol-pulse 1s ease-in-out infinite;
    }
    @keyframes afrt-viol-pulse {
      0%, 100% { box-shadow: 0 0 4px rgba(239,68,68,0.4); }
      50%       { box-shadow: 0 0 14px rgba(239,68,68,0.8); }
    }

    .afrt-finding-meta {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }
    .afrt-meta-item {
      font-size: 11px;
      color: var(--afrt-muted);
    }
    .afrt-meta-item span {
      color: var(--afrt-text);
      font-family: var(--afrt-mono);
      font-size: 11px;
    }

    /* ── Adversarial cases list ──────────────────────────────────────── */
    .afrt-cases-toggle {
      font-size: 11px;
      color: var(--afrt-accent);
      cursor: pointer;
      background: none;
      border: none;
      padding: 0;
      text-align: left;
      font-family: var(--afrt-sans);
    }
    .afrt-cases-toggle:hover { text-decoration: underline; }
    .afrt-cases-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-top: 4px;
    }
    .afrt-case-row {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--afrt-border);
      border-radius: 6px;
      padding: 8px 12px;
      display: flex;
      align-items: flex-start;
      gap: 10px;
    }
    .afrt-case-outcome {
      font-size: 10px;
      font-weight: 700;
      width: 68px;
      flex-shrink: 0;
      margin-top: 1px;
    }
    .afrt-case-outcome.survived  { color: var(--afrt-pass); }
    .afrt-case-outcome.falsified { color: var(--afrt-violation); }
    .afrt-case-detail {
      flex: 1;
      min-width: 0;
    }
    .afrt-case-path {
      font-family: var(--afrt-mono);
      font-size: 10px;
      color: var(--afrt-accent);
      word-break: break-all;
    }
    .afrt-case-desc {
      font-size: 10px;
      color: var(--afrt-muted);
      margin-top: 2px;
    }
    .afrt-case-id {
      font-family: var(--afrt-mono);
      font-size: 9px;
      color: #444b58;
      margin-top: 2px;
    }

    /* ── Report hash ─────────────────────────────────────────────────── */
    .afrt-hash-row {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .afrt-hash-label {
      font-size: 10px;
      color: var(--afrt-muted);
      white-space: nowrap;
    }
    .afrt-hash-value {
      font-family: var(--afrt-mono);
      font-size: 10px;
      color: #444b58;
      word-break: break-all;
      flex: 1;
    }
    .afrt-ledger-badge {
      font-size: 9px;
      padding: 1px 6px;
      border-radius: 3px;
      white-space: nowrap;
    }
    .afrt-ledger-badge.committed {
      background: rgba(34,197,94,0.12);
      color: var(--afrt-pass);
      border: 1px solid rgba(34,197,94,0.2);
    }
    .afrt-ledger-badge.pending {
      background: rgba(234,179,8,0.12);
      color: #eab308;
      border: 1px solid rgba(234,179,8,0.2);
    }

    /* ── Violation alert ─────────────────────────────────────────────── */
    .afrt-violation-alert {
      background: rgba(239,68,68,0.1);
      border: 1px solid var(--afrt-violation);
      border-radius: 8px;
      padding: 14px 16px;
      color: var(--afrt-violation);
      font-size: 13px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    /* ── Empty / loading states ──────────────────────────────────────── */
    .afrt-empty {
      text-align: center;
      color: var(--afrt-muted);
      font-size: 13px;
      padding: 40px 0;
    }
    .afrt-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      color: var(--afrt-muted);
      font-size: 13px;
      padding: 30px 0;
    }
    .afrt-spinner {
      width: 16px;
      height: 16px;
      border: 2px solid var(--afrt-border);
      border-top-color: var(--afrt-accent);
      border-radius: 50%;
      animation: afrt-spin 0.8s linear infinite;
    }
    @keyframes afrt-spin {
      to { transform: rotate(360deg); }
    }

    /* ── Constitutional footer ───────────────────────────────────────── */
    .afrt-footer {
      border-top: 1px solid var(--afrt-border);
      padding-top: 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }
    .afrt-footer-inv {
      font-family: var(--afrt-mono);
      font-size: 9px;
      color: #2b2f36;
      letter-spacing: 0.3px;
    }
    .afrt-footer-inv.active { color: #3b82f6; }
  `;

  /* ══════════════════════════════════════════════════════════════════════
     STATE
  ══════════════════════════════════════════════════════════════════════ */
  const state = {
    findings: [],      // RedTeamFindingsReport[]
    totalEvaluated: 0,
    totalPass: 0,
    totalReturned: 0,
    violationDetected: false,
    wsConnected: false,
    loading: true,
    expandedCases: new Set(),  // proposal_ids with cases expanded
    ws: null,
    pollTimer: null,
  };

  /* ══════════════════════════════════════════════════════════════════════
     RENDER
  ══════════════════════════════════════════════════════════════════════ */
  function render(container) {
    container.innerHTML = "";

    // Inject CSS once
    if (!document.getElementById("adaad-afrt-styles")) {
      const style = document.createElement("style");
      style.id = "adaad-afrt-styles";
      style.textContent = AFRT_CSS;
      document.head.appendChild(style);
    }

    const wrap = document.createElement("div");
    wrap.className = "afrt-wrap";

    // AFRT-0 violation alert (structural hard block)
    if (state.violationDetected) {
      const alert = document.createElement("div");
      alert.className = "afrt-violation-alert";
      alert.innerHTML = `
        ⛔ AFRT-0 CONSTITUTIONAL VIOLATION DETECTED
        &mdash; approval_emitted=true received from AFRT engine.
        HUMAN-0 alert required. Epoch halted.
      `;
      wrap.appendChild(alert);
    }

    // Header
    wrap.appendChild(buildHeader());

    // Stats bar
    wrap.appendChild(buildStats());

    // Feed
    const feedHeader = document.createElement("div");
    feedHeader.className = "afrt-feed-header";
    feedHeader.textContent = "Red Team Findings — Live Stream";
    wrap.appendChild(feedHeader);

    if (state.loading) {
      const loading = document.createElement("div");
      loading.className = "afrt-loading";
      loading.innerHTML = `<div class="afrt-spinner"></div> Connecting to AFRT gate…`;
      wrap.appendChild(loading);
    } else if (state.findings.length === 0) {
      const empty = document.createElement("div");
      empty.className = "afrt-empty";
      empty.textContent = "No AFRT findings yet — awaiting first CEL epoch with proposals.";
      wrap.appendChild(empty);
    } else {
      wrap.appendChild(buildFeed());
    }

    // Footer invariants
    wrap.appendChild(buildFooter());

    container.appendChild(wrap);
  }

  function buildHeader() {
    const header = document.createElement("div");
    header.className = "afrt-header";

    const dot = document.createElement("div");
    dot.className = "afrt-live-dot" + (state.wsConnected ? "" : " offline");

    const title = document.createElement("div");
    title.className = "afrt-header-title";
    title.innerHTML = `<h2>⚔ Adversarial Red Team</h2>`;
    title.prepend(dot);

    const badge = document.createElement("span");
    badge.className = "afrt-version-badge";
    badge.textContent = `INNOV-08 · AFRT ${AFRT_VERSION}`;

    header.appendChild(title);
    header.appendChild(badge);
    return header;
  }

  function buildStats() {
    const grid = document.createElement("div");
    grid.className = "afrt-stats";

    const passRate = state.totalEvaluated
      ? Math.round((state.totalPass / state.totalEvaluated) * 100)
      : 0;

    const stats = [
      { label: "Evaluated",   value: state.totalEvaluated, cls: "neutral" },
      { label: "PASS",        value: state.totalPass,      cls: "pass" },
      { label: "RETURNED",    value: state.totalReturned,  cls: "ret" },
      { label: "Pass Rate",   value: state.totalEvaluated ? passRate + "%" : "—", cls: passRate >= 70 ? "pass" : "ret" },
    ];

    stats.forEach(s => {
      const card = document.createElement("div");
      card.className = "afrt-stat-card";
      card.innerHTML = `
        <div class="afrt-stat-label">${s.label}</div>
        <div class="afrt-stat-value ${s.cls}">${s.value}</div>
      `;
      grid.appendChild(card);
    });

    return grid;
  }

  function buildFeed() {
    const feed = document.createElement("div");
    feed.className = "afrt-feed";

    // Most recent first
    [...state.findings].reverse().forEach(finding => {
      feed.appendChild(buildFindingCard(finding));
    });

    return feed;
  }

  function buildFindingCard(finding) {
    // AFRT-0: hard block on approval_emitted
    if (finding.approval_emitted === true) {
      state.violationDetected = true;
    }

    const verdict = finding.verdict || "UNKNOWN";
    const isPass     = verdict === "PASS";
    const isReturned = verdict === "RETURNED";
    const isViolation = finding.approval_emitted === true;

    const card = document.createElement("div");
    card.className = "afrt-finding" +
      (isViolation ? " violation" : isPass ? " pass" : " returned");

    // Top row
    const top = document.createElement("div");
    top.className = "afrt-finding-top";

    const propId = document.createElement("div");
    propId.className = "afrt-proposal-id";
    propId.textContent = "proposal:" + (finding.proposal_id || "unknown");

    const verdictBadge = document.createElement("div");
    verdictBadge.className = "afrt-verdict-badge " +
      (isViolation ? "violation" : isPass ? "pass" : "returned");
    verdictBadge.textContent = isViolation ? "⛔ AFRT-0 VIOLATION" : verdict;

    top.appendChild(propId);
    top.appendChild(verdictBadge);
    card.appendChild(top);

    // Meta row
    const meta = document.createElement("div");
    meta.className = "afrt-finding-meta";

    const cases     = finding.adversarial_cases || [];
    const failures  = finding.failure_cases || [];
    const paths     = finding.uncovered_paths || [];

    [
      ["epoch",    finding.epoch_id || "—"],
      ["cases",    cases.length + " / 5"],
      ["failures", failures.length],
      ["paths",    paths.length + " probed"],
      ["version",  finding.afrt_version || AFRT_VERSION],
    ].forEach(([label, val]) => {
      const item = document.createElement("div");
      item.className = "afrt-meta-item";
      item.innerHTML = `${label}: <span>${val}</span>`;
      meta.appendChild(item);
    });
    card.appendChild(meta);

    // Adversarial cases toggle
    if (cases.length > 0) {
      const togBtn = document.createElement("button");
      togBtn.className = "afrt-cases-toggle";
      const expanded = state.expandedCases.has(finding.proposal_id);
      togBtn.textContent = expanded
        ? `▾ Hide ${cases.length} adversarial case${cases.length > 1 ? "s" : ""}`
        : `▸ Show ${cases.length} adversarial case${cases.length > 1 ? "s" : ""}`;

      togBtn.addEventListener("click", () => {
        if (state.expandedCases.has(finding.proposal_id)) {
          state.expandedCases.delete(finding.proposal_id);
        } else {
          state.expandedCases.add(finding.proposal_id);
        }
        // Re-render this card in place
        const fresh = buildFindingCard(finding);
        card.replaceWith(fresh);
      });
      card.appendChild(togBtn);

      if (expanded) {
        const casesList = document.createElement("div");
        casesList.className = "afrt-cases-list";
        cases.forEach(ac => {
          const row = document.createElement("div");
          row.className = "afrt-case-row";
          const outcome = (ac.outcome || "SURVIVED").toUpperCase();
          row.innerHTML = `
            <div class="afrt-case-outcome ${outcome.toLowerCase()}">${outcome}</div>
            <div class="afrt-case-detail">
              <div class="afrt-case-path">${ac.target_path || ""}</div>
              <div class="afrt-case-desc">${ac.description || ""}</div>
              ${ac.failure_detail ? `<div class="afrt-case-desc" style="color:#ef4444">${ac.failure_detail}</div>` : ""}
              <div class="afrt-case-id">${ac.case_id || ""}</div>
            </div>
          `;
          casesList.appendChild(row);
        });
        card.appendChild(casesList);
      }
    }

    // Hash + ledger status
    if (finding.report_hash) {
      const hashRow = document.createElement("div");
      hashRow.className = "afrt-hash-row";
      hashRow.innerHTML = `
        <span class="afrt-hash-label">report_hash</span>
        <span class="afrt-hash-value">${finding.report_hash}</span>
        <span class="afrt-ledger-badge ${finding.trace_committed ? "committed" : "pending"}">
          ${finding.trace_committed ? "LEDGER ✓" : "PENDING"}
        </span>
      `;
      card.appendChild(hashRow);
    }

    return card;
  }

  function buildFooter() {
    const footer = document.createElement("div");
    footer.className = "afrt-footer";

    const invariants = [
      "AFRT-0", "AFRT-GATE-0", "AFRT-INTEL-0",
      "AFRT-LEDGER-0", "AFRT-CASES-0", "AFRT-DETERM-0",
    ];
    const invRow = document.createElement("div");
    invRow.style.display = "flex";
    invRow.style.gap = "12px";
    invRow.style.flexWrap = "wrap";
    invariants.forEach(inv => {
      const span = document.createElement("span");
      span.className = "afrt-footer-inv active";
      span.textContent = inv;
      invRow.appendChild(span);
    });

    const epoch = document.createElement("span");
    epoch.className = "afrt-footer-inv";
    epoch.textContent = `CEL Step 10 · Phase 92 · v${AFRT_VERSION}`;

    footer.appendChild(invRow);
    footer.appendChild(epoch);
    return footer;
  }

  /* ══════════════════════════════════════════════════════════════════════
     DATA LAYER
  ══════════════════════════════════════════════════════════════════════ */
  function ingestFinding(finding) {
    // AFRT-0: constitutional check
    if (finding.approval_emitted === true) {
      state.violationDetected = true;
      console.error("[AFRT-PANEL] AFRT-0 VIOLATION: approval_emitted=true received. HUMAN-0 alert required.");
    }

    // Deduplicate by report_hash
    if (finding.report_hash && state.findings.some(f => f.report_hash === finding.report_hash)) {
      return;
    }

    state.findings.push(finding);
    state.totalEvaluated++;
    if ((finding.verdict || "").toUpperCase() === "PASS") {
      state.totalPass++;
    } else {
      state.totalReturned++;
    }

    // Rolling window
    if (state.findings.length > MAX_FINDINGS_SHOWN) {
      state.findings.shift();
    }
  }

  async function fetchFindings(container) {
    try {
      const resp = await fetch(FINDINGS_ENDPOINT, {
        headers: { "Accept": "application/json" },
      });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const data = await resp.json();
      const findings = Array.isArray(data) ? data : (data.findings || []);
      state.findings = [];
      state.totalEvaluated = 0;
      state.totalPass = 0;
      state.totalReturned = 0;
      findings.forEach(ingestFinding);
      state.loading = false;
      render(container);
    } catch (err) {
      // Graceful degradation: endpoint may not exist in all environments
      state.loading = false;
      render(container);
    }
  }

  function connectWebSocket(container) {
    const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") +
                  location.host + "/ws/governance";
    try {
      const ws = new WebSocket(wsUrl);
      state.ws = ws;

      ws.addEventListener("open", () => {
        state.wsConnected = true;
        render(container);
      });

      ws.addEventListener("message", (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.event_type === WS_EVENT_TYPE && msg.payload) {
            ingestFinding(msg.payload);
            render(container);
          }
        } catch (_) {}
      });

      ws.addEventListener("close", () => {
        state.wsConnected = false;
        render(container);
        // Reconnect after 5s
        setTimeout(() => connectWebSocket(container), 5000);
      });

      ws.addEventListener("error", () => {
        state.wsConnected = false;
      });
    } catch (_) {
      // WebSocket unavailable — fall through to poll
      state.wsConnected = false;
    }
  }

  function startPoll(container) {
    state.pollTimer = setInterval(() => {
      if (!state.wsConnected) {
        fetchFindings(container);
      }
    }, POLL_INTERVAL_MS);
  }

  /* ══════════════════════════════════════════════════════════════════════
     PUBLIC MOUNT API
  ══════════════════════════════════════════════════════════════════════ */

  /**
   * Mount the AFRT panel into a DOM container.
   *
   * @param {HTMLElement|string} container — element or CSS selector
   * @returns {{ unmount: () => void }}
   */
  function mount(container) {
    if (typeof container === "string") {
      container = document.querySelector(container);
    }
    if (!container) {
      console.error("[AFRT-PANEL] mount(): container not found");
      return { unmount: () => {} };
    }

    // Initial render (loading state)
    render(container);

    // Fetch snapshot then connect live
    fetchFindings(container).then(() => {
      connectWebSocket(container);
      startPoll(container);
    });

    return {
      unmount() {
        if (state.ws) { state.ws.close(); state.ws = null; }
        if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
        container.innerHTML = "";
      },
    };
  }

  /* ══════════════════════════════════════════════════════════════════════
     EXPORT
  ══════════════════════════════════════════════════════════════════════ */
  const AFRTPanel = { mount, AFRT_VERSION };

  // Module exports
  if (typeof module !== "undefined" && module.exports) {
    module.exports = AFRTPanel;
  } else {
    global.AFRTPanel = AFRTPanel;
  }

}(typeof globalThis !== "undefined" ? globalThis : this));
