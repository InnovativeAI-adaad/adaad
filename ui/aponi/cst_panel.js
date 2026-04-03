/**
 * ADAAD Aponi — Constitutional Stress Testing Panel (Phase 105 / INNOV-20)
 * ──────────────────────────────────────────────────────────────────────────
 * Scenario catalogue browser + constitutional gap explorer.
 *
 * Displays:
 *   • Epoch ID input → run full stress-test suite
 *   • Scenario catalogue table (case_id, target_rule, margin, status)
 *   • Gap summary badge (gaps_found / cases_tested)
 *   • SHA-256 report_digest with copy-to-clipboard
 *   • Gap detail cards — rule bypassed, pattern, risk, recommended rule
 *   • InvariantDiscovery feed preview for emitted gap records
 *
 * Constitutional wire-in:
 *   • Connects to GET /governance/stress-test/{epoch_id}
 *   • CST-0:         all results deterministic; no spinner-only states
 *   • CST-GAP-0:     gap cards rendered for every gaps[] entry in response
 *   • CST-PERSIST-0: report_digest confirms ledger write succeeded
 *   • CST-FEED-0:    feed preview shown when gaps_found > 0
 *
 * Self-contained: injects CSS, owns state, graceful degradation.
 */
(function (global) {
  "use strict";

  const CST_VERSION   = "105.0";
  const BASE_ENDPOINT = "/governance/stress-test";

  /* ══════════════════════════════════════════════════════════════════════
     CSS
  ══════════════════════════════════════════════════════════════════════ */
  const CST_CSS = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
      --cst-bg:       #0b0c0f;
      --cst-panel:    #16181d;
      --cst-border:   #2b2f36;
      --cst-text:     #f5f7fa;
      --cst-muted:    #8c919b;
      --cst-gap:      #f59e0b;
      --cst-clear:    #22c55e;
      --cst-error:    #ef4444;
      --cst-blue:     #3b82f6;
      --cst-purple:   #a855f7;
      --cst-mono:     'JetBrains Mono', monospace;
      --cst-sans:     'Inter', system-ui, sans-serif;
    }

    #cst-panel * { box-sizing: border-box; margin: 0; padding: 0; }

    #cst-panel {
      background: var(--cst-bg);
      border: 1px solid var(--cst-border);
      border-radius: 12px;
      color: var(--cst-text);
      font-family: var(--cst-sans);
      max-width: 900px;
      overflow: hidden;
    }

    .cst-header {
      background: linear-gradient(135deg, #1a1b21 0%, #12131a 100%);
      border-bottom: 1px solid var(--cst-border);
      padding: 20px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .cst-header-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .cst-icon {
      width: 36px; height: 36px;
      background: linear-gradient(135deg, var(--cst-gap) 0%, var(--cst-purple) 100%);
      border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      font-size: 18px;
    }

    .cst-title { font-size: 15px; font-weight: 700; color: var(--cst-text); }
    .cst-subtitle { font-size: 11px; color: var(--cst-muted); margin-top: 2px; }

    .cst-version-badge {
      font-family: var(--cst-mono);
      font-size: 10px;
      color: var(--cst-muted);
      background: #1e2028;
      border: 1px solid var(--cst-border);
      border-radius: 4px;
      padding: 3px 7px;
    }

    .cst-body { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }

    .cst-run-row {
      display: flex;
      gap: 10px;
      align-items: center;
    }

    .cst-input {
      flex: 1;
      background: #1e2028;
      border: 1px solid var(--cst-border);
      border-radius: 7px;
      color: var(--cst-text);
      font-family: var(--cst-mono);
      font-size: 13px;
      padding: 9px 13px;
      outline: none;
      transition: border-color 0.15s;
    }
    .cst-input:focus { border-color: var(--cst-blue); }
    .cst-input::placeholder { color: var(--cst-muted); }

    .cst-run-btn {
      background: linear-gradient(135deg, var(--cst-gap) 0%, var(--cst-purple) 100%);
      border: none;
      border-radius: 7px;
      color: #fff;
      cursor: pointer;
      font-family: var(--cst-sans);
      font-size: 13px;
      font-weight: 600;
      padding: 9px 18px;
      transition: opacity 0.15s;
      white-space: nowrap;
    }
    .cst-run-btn:hover { opacity: 0.88; }
    .cst-run-btn:disabled { opacity: 0.45; cursor: not-allowed; }

    /* ── Summary bar ── */
    .cst-summary {
      background: #1e2028;
      border: 1px solid var(--cst-border);
      border-radius: 8px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1px;
      overflow: hidden;
    }

    .cst-stat {
      padding: 12px 16px;
      background: var(--cst-panel);
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .cst-stat-label { font-size: 10px; color: var(--cst-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .cst-stat-value { font-family: var(--cst-mono); font-size: 18px; font-weight: 600; }
    .cst-stat-value.gap  { color: var(--cst-gap); }
    .cst-stat-value.ok   { color: var(--cst-clear); }
    .cst-stat-value.mono { color: var(--cst-blue); font-size: 11px; word-break: break-all; }

    /* ── Scenario table ── */
    .cst-section-label {
      font-size: 11px;
      color: var(--cst-muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-weight: 600;
      margin-bottom: 6px;
    }

    .cst-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }

    .cst-table th {
      text-align: left;
      color: var(--cst-muted);
      font-weight: 600;
      padding: 6px 10px;
      border-bottom: 1px solid var(--cst-border);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .cst-table td {
      padding: 7px 10px;
      border-bottom: 1px solid #1e2028;
      font-family: var(--cst-mono);
      font-size: 11px;
    }

    .cst-table tr:last-child td { border-bottom: none; }

    .cst-table tr.has-gap td { background: rgba(245,158,11,0.06); }

    .margin-thin  { color: var(--cst-gap); }
    .margin-wide  { color: var(--cst-clear); }
    .margin-mid   { color: var(--cst-blue); }

    .status-gap   { color: var(--cst-gap); font-weight: 600; }
    .status-clear { color: var(--cst-clear); }
    .status-pending { color: var(--cst-muted); }

    /* ── Gap cards ── */
    .cst-gap-card {
      background: rgba(245,158,11,0.07);
      border: 1px solid rgba(245,158,11,0.35);
      border-radius: 8px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .cst-gap-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .cst-gap-id {
      font-family: var(--cst-mono);
      font-size: 12px;
      font-weight: 600;
      color: var(--cst-gap);
    }

    .cst-gap-digest {
      font-family: var(--cst-mono);
      font-size: 10px;
      color: var(--cst-muted);
    }

    .cst-gap-row {
      display: grid;
      grid-template-columns: 130px 1fr;
      gap: 6px;
      font-size: 11px;
    }

    .cst-gap-key { color: var(--cst-muted); }
    .cst-gap-val { color: var(--cst-text); font-family: var(--cst-mono); }

    .cst-recommended {
      background: rgba(59,130,246,0.08);
      border: 1px solid rgba(59,130,246,0.2);
      border-radius: 5px;
      padding: 7px 10px;
      font-size: 11px;
      color: var(--cst-blue);
      font-family: var(--cst-mono);
    }

    /* ── Digest row ── */
    .cst-digest-row {
      display: flex;
      align-items: center;
      gap: 8px;
      background: #1e2028;
      border: 1px solid var(--cst-border);
      border-radius: 7px;
      padding: 9px 13px;
    }

    .cst-digest-label { font-size: 11px; color: var(--cst-muted); white-space: nowrap; }
    .cst-digest-value { font-family: var(--cst-mono); font-size: 11px; color: var(--cst-clear); flex: 1; word-break: break-all; }
    .cst-copy-btn {
      background: #2a2d35;
      border: 1px solid var(--cst-border);
      border-radius: 5px;
      color: var(--cst-muted);
      cursor: pointer;
      font-size: 11px;
      padding: 4px 9px;
      white-space: nowrap;
    }
    .cst-copy-btn:hover { color: var(--cst-text); }

    .cst-empty { color: var(--cst-muted); font-size: 13px; text-align: center; padding: 20px; }
    .cst-error-msg { color: var(--cst-error); font-size: 12px; font-family: var(--cst-mono); }
  `;

  /* ══════════════════════════════════════════════════════════════════════
     State
  ══════════════════════════════════════════════════════════════════════ */
  let _state = {
    loading:    false,
    epochId:    "",
    report:     null,
    catalogue:  [],
    error:      null,
  };

  let _root = null;

  /* ══════════════════════════════════════════════════════════════════════
     Helpers
  ══════════════════════════════════════════════════════════════════════ */
  function _marginClass(m) {
    if (m <= 0.03) return "margin-thin";
    if (m <= 0.07) return "margin-mid";
    return "margin-wide";
  }

  function _scenarioStatus(caseId, report) {
    if (!report) return { cls: "status-pending", label: "—" };
    const isGap = report.gaps.some(g => g.gap_id.includes(caseId));
    const ran   = report.patterns_run && report.patterns_run.includes(caseId);
    if (!ran)  return { cls: "status-pending", label: "—" };
    if (isGap) return { cls: "status-gap",   label: "⚠ GAP" };
    return       { cls: "status-clear", label: "✓ clear" };
  }

  /* ══════════════════════════════════════════════════════════════════════
     Fetch
  ══════════════════════════════════════════════════════════════════════ */
  function _runStressTest(epochId) {
    if (!epochId.trim()) return;
    _state.loading = true;
    _state.error   = null;
    _render();

    fetch(`${BASE_ENDPOINT}/${encodeURIComponent(epochId)}`, {
      headers: { "X-Audit-Token": "aponi-panel", "Accept": "application/json" },
    })
      .then(r => r.json())
      .then(data => {
        if (!data.ok) {
          _state.error = data.error || "Server error";
        } else {
          _state.report    = data;
          _state.catalogue = data.catalogue || [];
        }
        _state.loading = false;
        _render();
      })
      .catch(err => {
        _state.error   = String(err);
        _state.loading = false;
        _render();
      });
  }

  /* ══════════════════════════════════════════════════════════════════════
     Render
  ══════════════════════════════════════════════════════════════════════ */
  function _render() {
    if (!_root) return;

    const R = _state.report;
    const cat = _state.catalogue.length ? _state.catalogue
                : (R && R.catalogue ? R.catalogue : []);

    /* ── summary ── */
    const gapsFound  = R ? R.gaps_found  : "—";
    const casesTested = R ? R.cases_tested : "—";
    const digest     = R ? R.report_digest : "awaiting run";
    const gapsCls    = (R && R.gaps_found > 0) ? "gap" : (R ? "ok" : "mono");

    /* ── catalogue rows ── */
    const catRows = cat.map(s => {
      const st = _scenarioStatus(s.case_id, R);
      return `<tr class="${st.cls === 'status-gap' ? 'has-gap' : ''}">
        <td>${s.case_id}</td>
        <td>${s.target_rule}</td>
        <td class="${_marginClass(s.expected_threshold_margin)}">${s.expected_threshold_margin.toFixed(3)}</td>
        <td title="${s.description}">${s.mutation_pattern}</td>
        <td class="${st.cls}">${st.label}</td>
      </tr>`;
    }).join("");

    /* ── gap cards ── */
    const gapCards = (R && R.gaps && R.gaps.length)
      ? R.gaps.map(g => `
          <div class="cst-gap-card">
            <div class="cst-gap-card-header">
              <span class="cst-gap-id">${g.gap_id}</span>
              <span class="cst-gap-digest">${g.gap_digest}</span>
            </div>
            <div class="cst-gap-row">
              <span class="cst-gap-key">rules_bypassed</span>
              <span class="cst-gap-val">${g.rules_bypassed.join(", ")}</span>
            </div>
            <div class="cst-gap-row">
              <span class="cst-gap-key">pattern</span>
              <span class="cst-gap-val">${g.mutation_pattern}</span>
            </div>
            <div class="cst-gap-row">
              <span class="cst-gap-key">risk</span>
              <span class="cst-gap-val">${g.risk_assessment}</span>
            </div>
            <div class="cst-recommended">⟶ ${g.recommended_new_rule}</div>
          </div>`).join("")
      : (R ? '<div class="cst-empty">✓ No constitutional gaps detected in this run</div>' : "");

    _root.innerHTML = `
      <div class="cst-header">
        <div class="cst-header-title">
          <div class="cst-icon">🔬</div>
          <div>
            <div class="cst-title">Constitutional Stress Testing</div>
            <div class="cst-subtitle">INNOV-20 · CST-0 · CST-GAP-0 · CST-FEED-0</div>
          </div>
        </div>
        <span class="cst-version-badge">v${CST_VERSION}</span>
      </div>

      <div class="cst-body">
        <div class="cst-run-row">
          <input class="cst-input" id="cst-epoch-input"
                 placeholder="epoch-id (e.g. epoch-2026-04-03-001)"
                 value="${_escHtml(_state.epochId)}" />
          <button class="cst-run-btn" id="cst-run-btn"
                  ${_state.loading ? "disabled" : ""}>
            ${_state.loading ? "Running…" : "▶ Run Stress Test"}
          </button>
        </div>

        ${_state.error ? `<div class="cst-error-msg">⚠ ${_escHtml(_state.error)}</div>` : ""}

        <div class="cst-summary">
          <div class="cst-stat">
            <span class="cst-stat-label">Gaps Found</span>
            <span class="cst-stat-value ${gapsCls}">${gapsFound}</span>
          </div>
          <div class="cst-stat">
            <span class="cst-stat-label">Cases Tested</span>
            <span class="cst-stat-value ok">${casesTested}</span>
          </div>
          <div class="cst-stat">
            <span class="cst-stat-label">Catalogue Size</span>
            <span class="cst-stat-value ok">${cat.length || "—"}</span>
          </div>
        </div>

        ${R ? `
        <div class="cst-digest-row">
          <span class="cst-digest-label">report_digest</span>
          <span class="cst-digest-value" id="cst-digest-val">${_escHtml(digest)}</span>
          <button class="cst-copy-btn" id="cst-copy-btn">copy</button>
        </div>` : ""}

        ${cat.length ? `
        <div>
          <div class="cst-section-label">Scenario Catalogue (${cat.length} patterns · CST-SCENARIO-0)</div>
          <table class="cst-table">
            <thead><tr>
              <th>case_id</th><th>target_rule</th><th>margin</th>
              <th>pattern</th><th>status</th>
            </tr></thead>
            <tbody>${catRows}</tbody>
          </table>
        </div>` : ""}

        ${(R && R.gaps_found >= 0) ? `
        <div>
          <div class="cst-section-label">
            Constitutional Gaps — ${R.gaps_found} found
            ${R.gaps_found > 0 ? " · InvariantDiscovery feed emitted (CST-FEED-0)" : ""}
          </div>
          ${gapCards}
        </div>` : ""}
      </div>
    `;

    /* ── wire events ── */
    const btn   = _root.querySelector("#cst-run-btn");
    const input = _root.querySelector("#cst-epoch-input");
    const copy  = _root.querySelector("#cst-copy-btn");

    if (input) input.addEventListener("input", e => { _state.epochId = e.target.value; });
    if (btn)   btn.addEventListener("click", () => _runStressTest(_state.epochId));
    if (input) input.addEventListener("keydown", e => {
      if (e.key === "Enter") _runStressTest(_state.epochId);
    });
    if (copy) copy.addEventListener("click", () => {
      const v = _root.querySelector("#cst-digest-val");
      if (v) navigator.clipboard.writeText(v.textContent).then(() => {
        copy.textContent = "✓ copied";
        setTimeout(() => { copy.textContent = "copy"; }, 1500);
      });
    });
  }

  function _escHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* ══════════════════════════════════════════════════════════════════════
     Mount
  ══════════════════════════════════════════════════════════════════════ */
  function mount(selector) {
    const container = document.querySelector(selector);
    if (!container) { console.warn("[CSTPanel] selector not found:", selector); return; }

    if (!document.getElementById("cst-panel-styles")) {
      const style = document.createElement("style");
      style.id = "cst-panel-styles";
      style.textContent = CST_CSS;
      document.head.appendChild(style);
    }

    _root = document.createElement("div");
    _root.id = "cst-panel";
    container.appendChild(_root);
    _render();
  }

  /* ── public API ── */
  global.CSTPanel = { mount, version: CST_VERSION };

}(typeof window !== "undefined" ? window : global));
