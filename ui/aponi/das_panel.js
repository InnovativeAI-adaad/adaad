/**
 * ADAAD Aponi — Deterministic Audit Sandbox Panel (Phase 121 / INNOV-36)
 * ────────────────────────────────────────────────────────────────────────
 * Interactive ledger explorer and chain verifier for DAS epoch records.
 *
 * Displays:
 *   • Live epoch runner — trigger a sandbox epoch from the UI
 *   • JSONL ledger viewer — per-record hash, status, timestamp, chain link
 *   • Chain integrity indicator — green all-clear or red broken-link alert
 *   • Replay verifier — re-derive all hashes and confirm match
 *   • Export — download ledger as JSONL
 *
 * Constitutional wire-in:
 *   • Connects to GET /governance/das/epoch (run epoch)
 *   • Connects to GET /governance/das/ledger (fetch records)
 *   • Connects to GET /governance/das/verify (chain verification)
 *   • DAS-VERIFY-0: broken chain displayed with ✗ + red highlight
 *   • DAS-GATE-0:   constitution violation shown as blocked banner
 *
 * Self-contained: injects CSS, owns state, graceful degradation.
 */
(function (global) {
  "use strict";

  const DAS_VERSION   = "121.0";
  const BASE_ENDPOINT = "/governance/das";

  /* ══════════════════════════════════════════════════════════════════════
     CSS
  ══════════════════════════════════════════════════════════════════════ */
  const DAS_CSS = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
      --das-bg:         #0b0c0f;
      --das-panel:      #16181d;
      --das-border:     #2b2f36;
      --das-text:       #f5f7fa;
      --das-muted:      #8c919b;
      --das-approved:   #22c55e;
      --das-blocked:    #ef4444;
      --das-shadow:     #14b8a6;
      --das-accent:     #3b82f6;
      --das-gold:       #eab308;
      --das-mono:       'JetBrains Mono', 'Courier New', monospace;
      --das-sans:       'Inter', Arial, sans-serif;
    }

    .das-wrap {
      background: var(--das-bg);
      color: var(--das-text);
      font-family: var(--das-sans);
      padding: 20px;
      border-radius: 10px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      animation: das-enter 0.4s cubic-bezier(.22,1,.36,1) both;
    }
    @keyframes das-enter {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .das-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--das-border);
    }
    .das-header h2 {
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.3px;
    }
    .das-version-badge {
      font-family: var(--das-mono);
      font-size: 10px;
      color: var(--das-muted);
      background: var(--das-panel);
      border: 1px solid var(--das-border);
      padding: 2px 8px;
      border-radius: 4px;
    }

    .das-controls {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: flex-end;
    }
    .das-field {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .das-field label {
      font-size: 10px;
      color: var(--das-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .das-field input, .das-field select {
      background: var(--das-panel);
      border: 1px solid var(--das-border);
      color: var(--das-text);
      font-family: var(--das-mono);
      font-size: 12px;
      padding: 6px 10px;
      border-radius: 5px;
      outline: none;
      width: 220px;
    }
    .das-field input:focus, .das-field select:focus {
      border-color: var(--das-accent);
    }

    .das-btn {
      background: var(--das-accent);
      color: #fff;
      border: none;
      padding: 7px 18px;
      border-radius: 5px;
      font-family: var(--das-sans);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s;
      align-self: flex-end;
    }
    .das-btn:hover { opacity: 0.85; }
    .das-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .das-btn.secondary {
      background: var(--das-panel);
      border: 1px solid var(--das-border);
      color: var(--das-text);
    }

    .das-status-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      padding: 8px 12px;
      background: var(--das-panel);
      border-radius: 6px;
      border: 1px solid var(--das-border);
      min-height: 36px;
    }
    .das-status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .das-status-dot.ok       { background: var(--das-approved); box-shadow: 0 0 6px var(--das-approved); }
    .das-status-dot.err      { background: var(--das-blocked);  box-shadow: 0 0 6px var(--das-blocked); }
    .das-status-dot.idle     { background: var(--das-muted); }
    .das-status-dot.running  { background: var(--das-gold); animation: das-pulse 1s infinite; }
    @keyframes das-pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.3; }
    }

    .das-chain-banner {
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .das-chain-banner.verified {
      background: rgba(34,197,94,0.1);
      border: 1px solid var(--das-approved);
      color: var(--das-approved);
    }
    .das-chain-banner.broken {
      background: rgba(239,68,68,0.1);
      border: 1px solid var(--das-blocked);
      color: var(--das-blocked);
    }
    .das-chain-banner.idle {
      background: var(--das-panel);
      border: 1px solid var(--das-border);
      color: var(--das-muted);
    }

    .das-table-wrap {
      overflow-x: auto;
      border-radius: 6px;
      border: 1px solid var(--das-border);
    }
    .das-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    .das-table th {
      background: var(--das-panel);
      color: var(--das-muted);
      font-weight: 600;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 8px 12px;
      text-align: left;
      border-bottom: 1px solid var(--das-border);
    }
    .das-table td {
      padding: 7px 12px;
      border-bottom: 1px solid var(--das-border);
      font-family: var(--das-mono);
      vertical-align: middle;
    }
    .das-table tr:last-child td { border-bottom: none; }
    .das-table tr:hover td { background: rgba(59,130,246,0.04); }

    .das-status-pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.3px;
    }
    .das-status-pill.approved      { background: rgba(34,197,94,0.15);  color: var(--das-approved); }
    .das-status-pill.blocked       { background: rgba(239,68,68,0.15);  color: var(--das-blocked); }
    .das-status-pill.shadow_diverged { background: rgba(20,184,166,0.15); color: var(--das-shadow); }

    .das-chain-ok  { color: var(--das-approved); }
    .das-chain-err { color: var(--das-blocked); }

    .das-hash {
      font-family: var(--das-mono);
      font-size: 11px;
      color: var(--das-muted);
    }

    .das-footer {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      padding-top: 8px;
      border-top: 1px solid var(--das-border);
    }

    .das-empty {
      text-align: center;
      color: var(--das-muted);
      padding: 32px;
      font-size: 13px;
    }
  `;

  /* ══════════════════════════════════════════════════════════════════════
     STATE
  ══════════════════════════════════════════════════════════════════════ */
  let _state = {
    records:      [],
    chainStatus:  "idle",      // "idle" | "verified" | "broken"
    chainMsg:     "Run an epoch to populate the ledger.",
    running:      false,
    statusMsg:    "Ready.",
    statusClass:  "idle",
  };

  /* ══════════════════════════════════════════════════════════════════════
     API HELPERS  (graceful mock fallback when server not present)
  ══════════════════════════════════════════════════════════════════════ */
  async function _api(path, opts = {}) {
    try {
      const r = await fetch(BASE_ENDPOINT + path, { ...opts, headers: { "Content-Type": "application/json" } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (_) {
      return null;  // server not available — UI degrades gracefully
    }
  }

  /* ── mock epoch generator (used when API unavailable) ─────────────── */
  function _mockEpoch(seed, epochId, n) {
    const records = [];
    const GENESIS = "0".repeat(64);
    let prev = GENESIS;
    const statuses = ["approved", "approved", "approved", "blocked", "approved", "approved", "approved", "shadow_diverged"];
    const ts0 = new Date("2026-04-04T00:00:00Z");
    for (let i = 0; i < n; i++) {
      const mutId = Array.from({ length: 16 }, (_, j) =>
        ((parseInt(seed.charCodeAt(j % seed.length) * 31 + i * 17 + j) & 0xff).toString(16).padStart(2, "0"))
      ).join("").slice(0, 16);
      const ts = new Date(ts0.getTime() + i * 1000).toISOString().replace(".000Z", "Z");
      const status = statuses[i % statuses.length];
      // simplified hash (not real HMAC — just for UI demo purposes)
      const hashInput = `${epochId}:${mutId}:${prev}`;
      const fakeHash = Array.from(hashInput).reduce((a, c, idx) => {
        return ((a << 5) - a + c.charCodeAt(0) + idx) | 0;
      }, 0).toString(16).padStart(8, "0").repeat(3).slice(0, 24);
      records.push({ epoch_id: epochId, seed, mutation_id: mutId, status, timestamp: ts, prev_digest: prev, record_hash: fakeHash });
      prev = fakeHash;
    }
    return records;
  }

  /* ══════════════════════════════════════════════════════════════════════
     ACTIONS
  ══════════════════════════════════════════════════════════════════════ */
  async function runEpoch(epochId, seed, mutations) {
    _state.running = true;
    _state.statusClass = "running";
    _state.statusMsg = `Running epoch ${epochId} …`;
    _state.chainStatus = "idle";
    render();

    const data = await _api(`/epoch?epoch_id=${encodeURIComponent(epochId)}&seed=${encodeURIComponent(seed)}&n_mutations=${mutations}`);
    if (data && data.records) {
      _state.records = data.records;
      _state.statusMsg = `Epoch complete — ${data.records.length} records written.`;
      _state.statusClass = "ok";
    } else {
      // fallback to local mock
      _state.records = _mockEpoch(seed, epochId, mutations);
      _state.statusMsg = `Epoch complete (mock) — ${_state.records.length} records. Server not connected.`;
      _state.statusClass = "ok";
    }

    _state.running = false;
    render();
  }

  async function verifyChain() {
    _state.statusClass = "running";
    _state.statusMsg = "Verifying chain integrity (DAS-VERIFY-0) …";
    render();

    const data = await _api("/verify");
    if (data) {
      _state.chainStatus = data.ok ? "verified" : "broken";
      _state.chainMsg = data.ok
        ? `Chain VERIFIED — ${data.records_checked} records, all links intact.`
        : `Chain BROKEN — ${data.error}`;
      _state.statusMsg = data.ok ? "Verification passed." : "Verification FAILED.";
      _state.statusClass = data.ok ? "ok" : "err";
    } else if (_state.records.length > 0) {
      // local verification on mock data
      let broken = false;
      let prev = "0".repeat(64);
      for (let i = 0; i < _state.records.length; i++) {
        const r = _state.records[i];
        if (r.prev_digest !== prev) { broken = true; break; }
        prev = r.record_hash;
      }
      _state.chainStatus  = broken ? "broken" : "verified";
      _state.chainMsg     = broken
        ? "Chain BROKEN — prev_digest mismatch detected."
        : `Chain VERIFIED (local) — ${_state.records.length} records intact.`;
      _state.statusMsg    = broken ? "Verification FAILED." : "Verification passed (local mock).";
      _state.statusClass  = broken ? "err" : "ok";
    }

    render();
  }

  function exportLedger() {
    if (!_state.records.length) return;
    const jsonl = _state.records.map(r => JSON.stringify(r)).join("\n");
    const blob = new Blob([jsonl], { type: "application/jsonl" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "das_epoch_ledger.jsonl"; a.click();
    URL.revokeObjectURL(url);
  }

  /* ══════════════════════════════════════════════════════════════════════
     RENDER
  ══════════════════════════════════════════════════════════════════════ */
  function _statusPill(status) {
    return `<span class="das-status-pill ${status}">${status.replace("_", " ")}</span>`;
  }

  function _chainIcon(status) {
    if (status === "idle") return "";
    return status === "verified"
      ? `<span class="das-chain-ok">✓</span>`
      : `<span class="das-chain-err">✗</span>`;
  }

  function render() {
    const wrap = document.getElementById("das-root");
    if (!wrap) return;

    const rows = _state.records.length
      ? _state.records.map((r, i) => `
          <tr>
            <td style="color:var(--das-muted)">${String(i + 1).padStart(2, "0")}</td>
            <td class="das-hash">${r.mutation_id}</td>
            <td>${_statusPill(r.status)}</td>
            <td class="das-hash">${r.record_hash}</td>
            <td class="das-hash">${r.prev_digest.slice(0, 12)}…</td>
            <td style="color:var(--das-muted);font-size:10px">${r.timestamp}</td>
          </tr>`).join("")
      : `<tr><td colspan="6"><div class="das-empty">No records — run an epoch to populate the ledger.</div></td></tr>`;

    wrap.innerHTML = `
      <div class="das-wrap">
        <div class="das-header">
          <h2>⬡ Deterministic Audit Sandbox</h2>
          <span class="das-version-badge">INNOV-36 · v${DAS_VERSION}</span>
        </div>

        <div class="das-controls" id="das-controls">
          <div class="das-field">
            <label>Epoch ID</label>
            <input id="das-epoch-id" value="EPOCH-DAS-DEMO-001" />
          </div>
          <div class="das-field">
            <label>Seed</label>
            <input id="das-seed" value="adaad-innov36-demo-seed-v1" />
          </div>
          <div class="das-field">
            <label>Mutations</label>
            <select id="das-mutations">
              <option value="4">4</option>
              <option value="8" selected>8</option>
              <option value="16">16</option>
            </select>
          </div>
          <button class="das-btn" id="das-run-btn" ${_state.running ? "disabled" : ""}>
            ${_state.running ? "Running …" : "▶ Run Epoch"}
          </button>
          <button class="das-btn secondary" id="das-verify-btn" ${!_state.records.length ? "disabled" : ""}>
            ⛓ Verify Chain
          </button>
        </div>

        <div class="das-status-bar">
          <div class="das-status-dot ${_state.statusClass}"></div>
          <span>${_state.statusMsg}</span>
        </div>

        <div class="das-chain-banner ${_state.chainStatus}">
          ${_chainIcon(_state.chainStatus)}
          ${_state.chainMsg}
        </div>

        <div class="das-table-wrap">
          <table class="das-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Mutation ID</th>
                <th>Status</th>
                <th>Record Hash (24c)</th>
                <th>Prev Digest</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>

        <div class="das-footer">
          <button class="das-btn secondary" id="das-export-btn" ${!_state.records.length ? "disabled" : ""}>
            ⬇ Export JSONL
          </button>
        </div>
      </div>
    `;

    document.getElementById("das-run-btn").onclick = () => {
      const epochId   = document.getElementById("das-epoch-id").value.trim();
      const seed      = document.getElementById("das-seed").value.trim();
      const mutations = parseInt(document.getElementById("das-mutations").value, 10);
      if (epochId && seed) runEpoch(epochId, seed, mutations);
    };
    document.getElementById("das-verify-btn").onclick = verifyChain;
    document.getElementById("das-export-btn").onclick = exportLedger;
  }

  /* ══════════════════════════════════════════════════════════════════════
     INIT
  ══════════════════════════════════════════════════════════════════════ */
  function init(containerId) {
    // Inject CSS
    if (!document.getElementById("das-css")) {
      const style = document.createElement("style");
      style.id = "das-css";
      style.textContent = DAS_CSS;
      document.head.appendChild(style);
    }

    const container = document.getElementById(containerId);
    if (!container) { console.error("DAS Panel: container not found:", containerId); return; }
    container.id = "das-root";
    render();
  }

  // Public API
  global.DASPanel = { init, version: DAS_VERSION };

}(typeof window !== "undefined" ? window : globalThis));
