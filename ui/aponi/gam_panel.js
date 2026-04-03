/**
 * ADAAD Aponi — Governance Archaeology Panel (Phase 104 / INNOV-19)
 * ──────────────────────────────────────────────────────────────────
 * Cryptographically-verified mutation decision timeline explorer.
 *
 * Displays:
 *   • Mutation ID search / lookup field
 *   • Final outcome badge (approved / rejected / promoted / rolled_back / unknown)
 *   • SHA-256 timeline digest with chain-verified indicator
 *   • Full chronological DecisionEvent list — type, timestamp, actor, outcome
 *   • Export JSON download of the full timeline
 *
 * Constitutional wire-in:
 *   • Connects to GET /governance/archaeology/{mutation_id}
 *   • GAM-0:     missing mutation → empty timeline rendered, no crash
 *   • GAM-CHAIN-0: digest displayed with sha256: prefix and tamper indicator
 *   • GAM-OUTCOME-0: outcome badge uses resolved final_outcome field
 *
 * Self-contained: injects CSS, owns state, graceful degradation.
 */
(function (global) {
  "use strict";

  const GAM_VERSION     = "104.0";
  const BASE_ENDPOINT   = "/governance/archaeology";

  /* ══════════════════════════════════════════════════════════════════════
     CSS
  ══════════════════════════════════════════════════════════════════════ */
  const GAM_CSS = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
      --gam-bg:        #0b0c0f;
      --gam-panel:     #16181d;
      --gam-border:    #2b2f36;
      --gam-text:      #f5f7fa;
      --gam-muted:     #8c919b;
      --gam-approved:  #22c55e;
      --gam-rejected:  #ef4444;
      --gam-promoted:  #3b82f6;
      --gam-rollback:  #eab308;
      --gam-unknown:   #8c919b;
      --gam-dream:     #8b5cf6;
      --gam-mono:      'JetBrains Mono', 'Courier New', monospace;
      --gam-sans:      'Inter', Arial, sans-serif;
    }

    .gam-wrap {
      background: var(--gam-bg);
      color: var(--gam-text);
      font-family: var(--gam-sans);
      padding: 20px;
      border-radius: 10px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      animation: gam-enter 0.4s cubic-bezier(.22,1,.36,1) both;
    }
    @keyframes gam-enter {
      from { opacity: 0; transform: translateY(12px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    /* Header */
    .gam-header {
      display: flex; align-items: center; justify-content: space-between;
      border-bottom: 1px solid var(--gam-border); padding-bottom: 12px;
    }
    .gam-title  { font-size: 15px; font-weight: 700; letter-spacing: .04em; color: var(--gam-dream); }
    .gam-sub    { font-size: 11px; color: var(--gam-muted); margin-top: 2px; }
    .gam-ver    { font-family: var(--gam-mono); font-size: 10px; color: var(--gam-muted);
                  background: var(--gam-panel); border: 1px solid var(--gam-border);
                  border-radius: 4px; padding: 2px 8px; }

    /* Search */
    .gam-search-row {
      display: flex; gap: 10px; align-items: center;
    }
    .gam-input {
      flex: 1; background: var(--gam-panel); border: 1px solid var(--gam-border);
      border-radius: 6px; padding: 8px 12px; color: var(--gam-text);
      font-family: var(--gam-mono); font-size: 12px; outline: none;
      transition: border-color 0.15s;
    }
    .gam-input:focus { border-color: var(--gam-dream); }
    .gam-btn {
      background: transparent; border: 1px solid var(--gam-dream); color: var(--gam-dream);
      border-radius: 6px; padding: 8px 18px; font-size: 12px; font-weight: 700;
      cursor: pointer; transition: background 0.15s;
    }
    .gam-btn:hover { background: rgba(139,92,246,0.12); }
    .gam-btn:disabled { opacity: 0.4; cursor: default; }

    /* Outcome banner */
    .gam-outcome-banner {
      display: flex; align-items: center; gap: 14px;
      background: var(--gam-panel); border: 1px solid var(--gam-border);
      border-radius: 8px; padding: 14px 18px;
    }
    .gam-outcome-badge {
      font-size: 11px; font-weight: 700; letter-spacing: .08em;
      text-transform: uppercase; padding: 4px 14px; border-radius: 20px; border: 1px solid;
    }
    .gam-outcome-approved  { color: var(--gam-approved); border-color: var(--gam-approved); background: rgba(34,197,94,.10); }
    .gam-outcome-rejected  { color: var(--gam-rejected); border-color: var(--gam-rejected); background: rgba(239,68,68,.10); }
    .gam-outcome-promoted  { color: var(--gam-promoted); border-color: var(--gam-promoted); background: rgba(59,130,246,.10); }
    .gam-outcome-rolled_back { color: var(--gam-rollback); border-color: var(--gam-rollback); background: rgba(234,179,8,.10); }
    .gam-outcome-unknown   { color: var(--gam-unknown);  border-color: var(--gam-border);   background: transparent; }

    .gam-digest-row { font-family: var(--gam-mono); font-size: 10px; color: var(--gam-muted); flex: 1; }
    .gam-digest-val { color: var(--gam-dream); word-break: break-all; }
    .gam-chain-ok   { color: var(--gam-approved); font-weight: 700; }
    .gam-chain-fail { color: var(--gam-rejected); font-weight: 700; }

    /* Event timeline */
    .gam-section-title {
      font-size: 11px; font-weight: 700; letter-spacing: .10em;
      text-transform: uppercase; color: var(--gam-muted); margin-bottom: 8px;
    }
    .gam-timeline { display: flex; flex-direction: column; gap: 6px; }
    .gam-event-card {
      background: var(--gam-panel); border: 1px solid var(--gam-border);
      border-radius: 7px; padding: 10px 14px;
      display: grid; grid-template-columns: 160px 1fr 1fr 1fr;
      gap: 8px; align-items: center; font-size: 11px;
    }
    .gam-event-card:hover { border-color: rgba(139,92,246,0.3); }
    .gam-ev-type { font-family: var(--gam-mono); color: var(--gam-text); font-weight: 600; }
    .gam-ev-ts   { font-family: var(--gam-mono); color: var(--gam-muted); font-size: 10px; }
    .gam-ev-actor { color: var(--gam-muted); }
    .gam-ev-outcome { font-weight: 600; }

    /* Empty / error */
    .gam-empty { color: var(--gam-muted); font-size: 12px; padding: 20px; text-align: center; }
    .gam-error { background: rgba(239,68,68,0.08); border: 1px solid var(--gam-rejected);
                 border-radius: 8px; padding: 10px 14px; font-size: 12px; color: var(--gam-rejected); }

    /* Footer */
    .gam-footer {
      display: flex; align-items: center; justify-content: space-between;
      border-top: 1px solid var(--gam-border); padding-top: 10px;
      font-size: 10px; color: var(--gam-muted);
    }
    .gam-export-btn {
      background: transparent; border: 1px solid var(--gam-muted); color: var(--gam-muted);
      border-radius: 5px; padding: 4px 12px; font-size: 10px; cursor: pointer;
      transition: border-color 0.15s, color 0.15s;
    }
    .gam-export-btn:hover { border-color: var(--gam-dream); color: var(--gam-dream); }
    .gam-export-btn:disabled { opacity: 0.3; cursor: default; }
  `;

  function injectCSS() {
    if (document.getElementById("gam-styles")) return;
    const s = document.createElement("style");
    s.id = "gam-styles";
    s.textContent = GAM_CSS;
    document.head.appendChild(s);
  }

  /* ══════════════════════════════════════════════════════════════════════
     STATE
  ══════════════════════════════════════════════════════════════════════ */
  let _state = {
    mutation_id: "",
    loading: false,
    searched: false,
    data: null,
    error: null,
  };

  /* ══════════════════════════════════════════════════════════════════════
     FETCH
  ══════════════════════════════════════════════════════════════════════ */
  async function fetchTimeline(mutationId) {
    if (!mutationId.trim()) return;
    _state.loading = true;
    _state.searched = true;
    _state.error = null;
    render();
    try {
      const res = await fetch(`${BASE_ENDPOINT}/${encodeURIComponent(mutationId.trim())}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      _state.data = await res.json();
    } catch (err) {
      _state.error = err.message;
      _state.data = null;
    }
    _state.loading = false;
    render();
  }

  /* ══════════════════════════════════════════════════════════════════════
     HELPERS
  ══════════════════════════════════════════════════════════════════════ */
  const OUTCOME_COLORS = {
    approved: "gam-approved", rejected: "gam-rejected",
    promoted: "gam-promoted", rolled_back: "gam-rollback",
  };

  function outcomeBadge(outcome) {
    const cls = `gam-outcome-badge gam-outcome-${outcome || "unknown"}`;
    return `<span class="${cls}">${outcome || "unknown"}</span>`;
  }

  function eventColor(outcome) {
    return OUTCOME_COLORS[outcome] ? `var(--${OUTCOME_COLORS[outcome].replace("gam-", "gam-")})` : "var(--gam-muted)";
  }

  function fmtTs(ts) {
    return ts ? ts.replace("T", " ").replace(/\.\d+Z?$/, "") : "—";
  }

  function exportJSON(data) {
    if (!data?.export) return;
    const blob = new Blob([JSON.stringify(data.export, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gam-timeline-${data.mutation_id || "export"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /* ══════════════════════════════════════════════════════════════════════
     RENDER
  ══════════════════════════════════════════════════════════════════════ */
  function render() {
    const host = document.getElementById("gam-panel-root");
    if (!host) return;

    const { loading, searched, data, error } = _state;

    /* Outcome banner */
    let outcomeSection = "";
    if (data) {
      const chainEl = data.chain_verified
        ? `<span class="gam-chain-ok">⬡ CHAIN OK</span>`
        : `<span class="gam-chain-fail">✗ CHAIN FAIL</span>`;
      outcomeSection = `
        <div class="gam-outcome-banner">
          ${outcomeBadge(data.final_outcome)}
          <div class="gam-digest-row">
            ${chainEl} &nbsp;·&nbsp; ${data.event_count} event${data.event_count !== 1 ? "s" : ""}
            <div class="gam-digest-val">${data.timeline_digest || "—"}</div>
          </div>
        </div>`;
    }

    /* Event timeline */
    let timelineSection = "";
    if (data?.timeline?.length) {
      const rows = data.timeline.map(ev => `
        <div class="gam-event-card">
          <div class="gam-ev-type">${ev.event_type}</div>
          <div class="gam-ev-ts">${fmtTs(ev.timestamp)}</div>
          <div class="gam-ev-actor">${ev.actor || "system"}</div>
          <div class="gam-ev-outcome" style="color:${eventColor(ev.outcome)}">${ev.outcome || "—"}</div>
        </div>`).join("");
      timelineSection = `
        <div>
          <div class="gam-section-title">Decision Timeline
            <span style="font-weight:400;color:var(--gam-dream);margin-left:8px">
              sorted ascending · ${data.event_count} events
            </span>
          </div>
          <div class="gam-timeline">${rows}</div>
        </div>`;
    } else if (searched && !loading && !error) {
      timelineSection = `<div class="gam-empty">No events found for this mutation_id in the ledger.</div>`;
    }

    host.innerHTML = `
      <div class="gam-wrap">

        <div class="gam-header">
          <div>
            <div class="gam-title">⬡ Governance Archaeology</div>
            <div class="gam-sub">INNOV-19 · Phase 104 · Cryptographic mutation timeline explorer</div>
          </div>
          <span class="gam-ver">v${GAM_VERSION}</span>
        </div>

        <div class="gam-search-row">
          <input class="gam-input" id="gam-input" type="text"
            placeholder="Enter mutation_id to excavate…" value="${_state.mutation_id}"
            ${loading ? "disabled" : ""}/>
          <button class="gam-btn" id="gam-search-btn" ${loading ? "disabled" : ""}>
            ${loading ? "⏳ Scanning…" : "⬡ Excavate"}
          </button>
        </div>

        ${error ? `<div class="gam-error">⚠ ${error}</div>` : ""}
        ${outcomeSection}
        ${timelineSection}

        <div class="gam-footer">
          <div>INNOV-19 · GAM-CHAIN-0 · GAM-DETERM-0 · GAM-FAIL-OPEN-0</div>
          <button class="gam-export-btn" id="gam-export-btn" ${!data ? "disabled" : ""}>
            ↓ Export JSON
          </button>
        </div>

      </div>`;

    /* Wire events */
    const inp  = document.getElementById("gam-input");
    const btn  = document.getElementById("gam-search-btn");
    const expB = document.getElementById("gam-export-btn");

    if (inp) {
      inp.addEventListener("input", e => { _state.mutation_id = e.target.value; });
      inp.addEventListener("keydown", e => { if (e.key === "Enter") fetchTimeline(_state.mutation_id); });
    }
    if (btn) btn.addEventListener("click", () => fetchTimeline(_state.mutation_id));
    if (expB) expB.addEventListener("click", () => exportJSON(data));
  }

  /* ══════════════════════════════════════════════════════════════════════
     INIT
  ══════════════════════════════════════════════════════════════════════ */
  function init(containerId, opts = {}) {
    injectCSS();
    const host = document.getElementById(containerId);
    if (!host) { console.warn("[GAM] Host element not found:", containerId); return; }
    const root = document.createElement("div");
    root.id = "gam-panel-root";
    host.appendChild(root);
    if (opts.mutation_id) {
      _state.mutation_id = opts.mutation_id;
      fetchTimeline(opts.mutation_id);
    } else {
      render();
    }
  }

  global.GAMPanel = { init, fetchTimeline, version: GAM_VERSION };

}(typeof window !== "undefined" ? window : global));
