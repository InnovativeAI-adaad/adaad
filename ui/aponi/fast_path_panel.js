// SPDX-License-Identifier: Apache-2.0
// Aponi Fast-Path Intelligence Panel — ADAAD v0.66
//
// Surfaces the four fast-path modules introduced in v0.66:
//   · MutationRouteOptimizer  — live tier routing preview
//   · EntropyFastGate         — entropy budget gate visualizer
//   · CheckpointChain         — chain integrity health widget
//   · FastPathScorer          — fast-path score inspector
//
// All interactions are read-only: no mutations, no ledger writes.
// Fetches from /api/fast-path/* endpoints added in server.py v0.66.

(function () {
  'use strict';

  // ── Constants ──────────────────────────────────────────────────────────────
  const FETCH_TIMEOUT_MS = 9000;
  const STATS_POLL_MS    = 45000;  // re-poll module stats every 45s

  const TIER_META = {
    TRIVIAL:  { label: 'TRIVIAL',  cls: 'fp-tier-trivial',   icon: '⚡', desc: 'Fast-path: heavy scoring skipped' },
    STANDARD: { label: 'STANDARD', cls: 'fp-tier-standard',  icon: '→',  desc: 'Standard evaluation pipeline' },
    ELEVATED: { label: 'ELEVATED', cls: 'fp-tier-elevated',  icon: '▲',  desc: 'Elevated: human review required' },
  };

  const VERDICT_META = {
    ALLOW: { cls: 'fp-verdict-allow', icon: '✓', label: 'ALLOW' },
    WARN:  { cls: 'fp-verdict-warn',  icon: '!', label: 'WARN'  },
    DENY:  { cls: 'fp-verdict-deny',  icon: '✕', label: 'DENY'  },
  };

  // ── DOM refs (set after DOMContentLoaded) ─────────────────────────────────
  let panelEl, routeForm, routeOutput, routeStatus,
      entropyForm, entropyOutput, entropyStatus,
      chainWidget, chainStatus,
      statsGrid, statsStatus,
      sectionToggle;

  // ── Utilities ──────────────────────────────────────────────────────────────

  function safeText(v) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'object') {
      try { return JSON.stringify(v, null, 2); } catch (_) { return '[object]'; }
    }
    return String(v);
  }

  function el(tag, cls, text, attrs) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = safeText(text);
    if (attrs) Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    return node;
  }

  function setStatus(node, msg, kind) {
    if (!node) return;
    node.textContent = msg;
    node.className = 'fp-status fp-status--' + (kind || 'idle');
  }

  async function fetchJson(url, opts) {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(url, {
        cache: 'no-store',
        signal: ctrl.signal,
        ...(opts || {}),
      });
      clearTimeout(tid);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || ('HTTP ' + res.status));
      }
      return await res.json();
    } catch (err) {
      clearTimeout(tid);
      throw err;
    }
  }

  // ── Styles injection ───────────────────────────────────────────────────────

  function injectStyles() {
    if (document.getElementById('fp-panel-styles')) return;
    const s = document.createElement('style');
    s.id = 'fp-panel-styles';
    s.textContent = `
/* ── Fast-Path Intelligence Panel ─────────────────────────────────────────── */
#fp-intelligence-section { margin-top: 2.5rem; }

.fp-section-head {
  display: flex; align-items: center; gap: .6rem;
  margin-bottom: 1.25rem; cursor: pointer; user-select: none;
}
.fp-section-head:hover .section-label { color: var(--accent2); }
.fp-section-label {
  font-family: var(--mono); font-size: .7rem; letter-spacing: .12em;
  text-transform: uppercase; color: var(--text3); transition: color .18s;
}
.fp-section-line { flex: 1; height: 1px; background: var(--border); }
.fp-toggle-btn {
  font-family: var(--mono); font-size: .65rem; color: var(--text3);
  padding: .15rem .45rem; border: 1px solid var(--border);
  border-radius: 4px; background: var(--bg3); cursor: pointer;
  transition: all .18s;
}
.fp-toggle-btn:hover { color: var(--accent2); border-color: var(--border2); }

.fp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}
@media (max-width: 680px) { .fp-grid { grid-template-columns: 1fr; } }

/* Cards */
.fp-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.1rem;
  display: flex; flex-direction: column; gap: .75rem;
  transition: border-color .18s;
}
.fp-card:hover { border-color: var(--border2); }
.fp-card-full { grid-column: 1 / -1; }
.fp-card-title {
  font-family: var(--mono); font-size: .68rem; letter-spacing: .1em;
  text-transform: uppercase; color: var(--accent2);
  display: flex; align-items: center; gap: .45rem;
}
.fp-card-title .fp-badge {
  font-size: .58rem; padding: .1rem .35rem; border-radius: 3px;
  background: var(--bg3); border: 1px solid var(--border); color: var(--text3);
}

/* Status line */
.fp-status {
  font-family: var(--mono); font-size: .7rem; min-height: 1.2em;
  transition: color .18s;
}
.fp-status--idle   { color: var(--text3); }
.fp-status--ok     { color: var(--ok); }
.fp-status--warn   { color: var(--warn); }
.fp-status--err    { color: var(--danger); }
.fp-status--busy   { color: var(--accent2); }

/* Form rows */
.fp-row   { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; }
.fp-field { display: flex; flex-direction: column; gap: .3rem; }
.fp-label {
  font-size: .7rem; color: var(--text2); letter-spacing: .03em; font-weight: 500;
}
.fp-input, .fp-select {
  padding: .45rem .6rem; background: var(--bg2);
  border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-family: var(--sans); font-size: .8rem;
  outline: none; transition: border-color .18s;
}
.fp-input:focus, .fp-select:focus {
  border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-glow);
}
.fp-input::placeholder { color: var(--text3); }
.fp-btn {
  align-self: flex-end; padding: .45rem .9rem;
  background: var(--accent); color: #fff;
  border: none; border-radius: 6px;
  font-family: var(--mono); font-size: .68rem; letter-spacing: .06em;
  font-weight: 700; text-transform: uppercase;
  cursor: pointer; transition: all .18s; white-space: nowrap;
}
.fp-btn:hover { background: var(--accent2); box-shadow: 0 0 14px var(--accent-glow); }
.fp-btn:disabled { opacity: .45; cursor: not-allowed; }
.fp-btn-ghost {
  background: transparent; color: var(--text2);
  border: 1px solid var(--border2);
}
.fp-btn-ghost:hover {
  border-color: var(--accent); color: var(--accent2); background: var(--accent-glow);
  box-shadow: none;
}

/* Tier badge */
.fp-tier-badge {
  display: inline-flex; align-items: center; gap: .4rem;
  padding: .35rem .75rem; border-radius: 99px;
  font-family: var(--mono); font-size: .75rem; font-weight: 700;
  letter-spacing: .08em; border: 1.5px solid currentColor;
}
.fp-tier-trivial  { color: #22c55e; background: rgba(34,197,94,.08); }
.fp-tier-standard { color: var(--accent2); background: var(--accent-glow); }
.fp-tier-elevated { color: #f59e0b; background: rgba(245,158,11,.08); }

/* Verdict badge */
.fp-verdict-badge {
  display: inline-flex; align-items: center; gap: .4rem;
  padding: .35rem .75rem; border-radius: 99px;
  font-family: var(--mono); font-size: .75rem; font-weight: 700;
  letter-spacing: .08em; border: 1.5px solid currentColor;
}
.fp-verdict-allow { color: var(--ok);   background: var(--ok-bg);   }
.fp-verdict-warn  { color: var(--warn); background: var(--warn-bg); }
.fp-verdict-deny  { color: var(--danger); background: var(--danger-bg); }

/* Reason chips */
.fp-reasons { display: flex; flex-wrap: wrap; gap: .3rem; }
.fp-reason-chip {
  font-family: var(--mono); font-size: .62rem; padding: .15rem .5rem;
  border-radius: 4px; background: var(--bg3);
  border: 1px solid var(--border); color: var(--text2);
}
.fp-reason-chip.elevated { border-color: rgba(245,158,11,.4); color: #f59e0b; }
.fp-reason-chip.trivial  { border-color: rgba(34,197,94,.4);  color: #22c55e; }

/* Detail rows */
.fp-detail-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: .3rem 0; border-bottom: 1px solid var(--border);
  font-size: .78rem;
}
.fp-detail-row:last-child { border-bottom: none; }
.fp-detail-key   { color: var(--text3); font-family: var(--mono); font-size: .7rem; }
.fp-detail-val   { color: var(--text);  font-family: var(--mono); font-size: .7rem; word-break: break-all; text-align: right; max-width: 60%; }
.fp-detail-val.ok { color: var(--ok); }
.fp-detail-val.warn { color: var(--warn); }
.fp-detail-val.err  { color: var(--danger); }

/* Chain links */
.fp-chain-list { display: flex; flex-direction: column; gap: .35rem; }
.fp-chain-link {
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: 6px; padding: .5rem .7rem;
  display: flex; flex-direction: column; gap: .2rem;
}
.fp-chain-link-head {
  display: flex; justify-content: space-between; align-items: center;
}
.fp-chain-epoch  { font-family: var(--mono); font-size: .7rem; color: var(--accent2); }
.fp-chain-digest { font-family: var(--mono); font-size: .6rem; color: var(--text3); word-break: break-all; }
.fp-chain-ok  { color: var(--ok); font-family: var(--mono); font-size: .65rem; }
.fp-chain-err { color: var(--danger); font-family: var(--mono); font-size: .65rem; }

/* Stats grid */
.fp-stats-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: .5rem;
}
.fp-stat-cell {
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: 7px; padding: .6rem .75rem;
  display: flex; flex-direction: column; gap: .2rem;
}
.fp-stat-val { font-family: var(--mono); font-size: 1.1rem; font-weight: 700; color: var(--accent2); }
.fp-stat-lbl { font-size: .62rem; color: var(--text3); text-transform: uppercase; letter-spacing: .04em; }

/* Tags list */
.fp-tag-list { display: flex; flex-wrap: wrap; gap: .25rem; }
.fp-tag {
  font-family: var(--mono); font-size: .58rem; padding: .1rem .4rem;
  border-radius: 3px; background: var(--bg3);
  border: 1px solid var(--border); color: var(--text3);
}
.fp-tag.elevated-path { border-color: rgba(239,68,68,.35); color: #f87171; }
.fp-tag.intent-kw     { border-color: rgba(245,158,11,.35); color: #fbbf24; }
.fp-tag.trivial-op    { border-color: rgba(34,197,94,.35);  color: #4ade80; }

/* Digest display */
.fp-digest {
  font-family: var(--mono); font-size: .62rem; color: var(--text3);
  word-break: break-all; padding: .35rem .5rem;
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: 5px; line-height: 1.4;
}

/* Collapsed state */
#fp-panel-body.fp-collapsed { display: none; }
`;
    document.head.appendChild(s);
  }

  // ── Panel HTML ─────────────────────────────────────────────────────────────

  function buildPanelHTML() {
    return `
<div id="fp-intelligence-section">
  <div class="fp-section-head" id="fp-section-head">
    <span class="fp-section-label">⚡ Fast-Path Intelligence</span>
    <div class="fp-section-line"></div>
    <button class="fp-toggle-btn" id="fp-toggle-btn" type="button">hide</button>
  </div>

  <div id="fp-panel-body">

    <!-- Row 1: Stats + Chain -->
    <div class="fp-grid">

      <!-- Module Stats -->
      <div class="fp-card">
        <div class="fp-card-title">
          Module Versions &amp; Config
          <span class="fp-badge" id="fp-stats-badge">—</span>
        </div>
        <div class="fp-stats-grid" id="fp-stats-grid">
          <div class="fp-stat-cell"><div class="fp-stat-val" id="fps-route-ver">—</div><div class="fp-stat-lbl">Route Optimizer</div></div>
          <div class="fp-stat-cell"><div class="fp-stat-val" id="fps-gate-ver">—</div><div class="fp-stat-lbl">Entropy Gate</div></div>
          <div class="fp-stat-cell"><div class="fp-stat-val" id="fps-scorer-ver">—</div><div class="fp-stat-lbl">Fast Scorer</div></div>
          <div class="fp-stat-cell"><div class="fp-stat-val" id="fps-chain-ver">—</div><div class="fp-stat-lbl">Checkpoint Chain</div></div>
          <div class="fp-stat-cell"><div class="fp-stat-val" id="fps-warn-bits">—</div><div class="fp-stat-lbl">Warn Bits</div></div>
          <div class="fp-stat-cell"><div class="fp-stat-val" id="fps-deny-bits">—</div><div class="fp-stat-lbl">Deny Bits</div></div>
        </div>
        <div>
          <div class="fp-label" style="margin-bottom:.4rem">Elevated Path Prefixes</div>
          <div class="fp-tag-list" id="fp-elevated-paths"></div>
        </div>
        <div>
          <div class="fp-label" style="margin-bottom:.4rem">Elevated Intent Keywords</div>
          <div class="fp-tag-list" id="fp-intent-keywords"></div>
        </div>
        <div>
          <div class="fp-label" style="margin-bottom:.4rem">Trivial Op Types</div>
          <div class="fp-tag-list" id="fp-trivial-ops"></div>
        </div>
        <div class="fp-status fp-status--idle" id="fp-stats-status">Loading module stats…</div>
        <button class="fp-btn fp-btn-ghost" id="fp-stats-reload" type="button">↺ Reload Stats</button>
      </div>

      <!-- Checkpoint Chain Health -->
      <div class="fp-card">
        <div class="fp-card-title">Checkpoint Chain Health</div>
        <div class="fp-status fp-status--idle" id="fp-chain-status">Not loaded.</div>
        <div id="fp-chain-integrity-badge"></div>
        <div class="fp-chain-list" id="fp-chain-list"></div>
        <button class="fp-btn fp-btn-ghost" id="fp-chain-verify-btn" type="button">↺ Verify Chain</button>
      </div>

    </div>

    <!-- Row 2: Route Preview (full width) -->
    <div class="fp-card fp-card-full">
      <div class="fp-card-title">
        Route Preview
        <span class="fp-badge">MutationRouteOptimizer</span>
      </div>
      <div class="fp-row">
        <div class="fp-field">
          <div class="fp-label">Mutation ID</div>
          <input class="fp-input" id="fp-route-mutation-id" placeholder="mut_preview_001" />
        </div>
        <div class="fp-field">
          <div class="fp-label">Intent</div>
          <input class="fp-input" id="fp-route-intent" placeholder="refactor" />
        </div>
      </div>
      <div class="fp-row">
        <div class="fp-field">
          <div class="fp-label">Files Touched (comma-separated)</div>
          <input class="fp-input" id="fp-route-files" placeholder="app/main.py, runtime/governance/gate.py" />
        </div>
        <div class="fp-field">
          <div class="fp-label">Risk Tags (comma-separated)</div>
          <input class="fp-input" id="fp-route-risk-tags" placeholder="HIGH, SECURITY" />
        </div>
      </div>
      <div class="fp-row">
        <div class="fp-field">
          <div class="fp-label">LOC Added</div>
          <input class="fp-input" id="fp-route-loc-added" type="number" min="0" value="0" />
        </div>
        <div class="fp-field">
          <div class="fp-label">LOC Deleted</div>
          <input class="fp-input" id="fp-route-loc-deleted" type="number" min="0" value="0" />
        </div>
      </div>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;">
        <button class="fp-btn" id="fp-route-submit" type="button">▶ Route</button>
        <button class="fp-btn fp-btn-ghost" id="fp-route-clear" type="button">Clear</button>
        <div class="fp-status fp-status--idle" id="fp-route-status" style="flex:1"></div>
      </div>
      <div id="fp-route-output"></div>
    </div>

    <!-- Row 3: Entropy Gate (full width) -->
    <div class="fp-card fp-card-full">
      <div class="fp-card-title">
        Entropy Gate Evaluator
        <span class="fp-badge">EntropyFastGate</span>
      </div>
      <div class="fp-row">
        <div class="fp-field">
          <div class="fp-label">Mutation ID</div>
          <input class="fp-input" id="fp-eg-mutation-id" placeholder="mut_entropy_001" />
        </div>
        <div class="fp-field">
          <div class="fp-label">Estimated Entropy Bits</div>
          <input class="fp-input" id="fp-eg-bits" type="number" min="0" value="8" />
        </div>
      </div>
      <div class="fp-row">
        <div class="fp-field">
          <div class="fp-label">Sources (comma-separated)</div>
          <input class="fp-input" id="fp-eg-sources" placeholder="prng, mutation_ops, clock" />
        </div>
        <div class="fp-field">
          <div class="fp-label">Strict Mode</div>
          <select class="fp-select" id="fp-eg-strict">
            <option value="true">Strict (fail-closed)</option>
            <option value="false">Permissive (warn on nondeterminism)</option>
          </select>
        </div>
      </div>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;">
        <button class="fp-btn" id="fp-eg-submit" type="button">▶ Evaluate Gate</button>
        <button class="fp-btn fp-btn-ghost" id="fp-eg-clear" type="button">Clear</button>
        <div class="fp-status fp-status--idle" id="fp-eg-status" style="flex:1"></div>
      </div>
      <div id="fp-eg-output"></div>
    </div>

  </div><!-- end fp-panel-body -->
</div><!-- end fp-intelligence-section -->
`;
  }

  // ── Render helpers ─────────────────────────────────────────────────────────

  function renderTierBadge(tier) {
    const meta = TIER_META[tier] || TIER_META.STANDARD;
    const badge = el('span', 'fp-tier-badge ' + meta.cls);
    badge.textContent = meta.icon + ' ' + meta.label;
    badge.title = meta.desc;
    return badge;
  }

  function renderVerdictBadge(verdict) {
    const meta = VERDICT_META[verdict] || VERDICT_META.WARN;
    const badge = el('span', 'fp-verdict-badge ' + meta.cls);
    badge.textContent = meta.icon + ' ' + meta.label;
    return badge;
  }

  function detailRow(key, val, valCls) {
    const row = el('div', 'fp-detail-row');
    row.appendChild(el('span', 'fp-detail-key', key));
    const vEl = el('span', 'fp-detail-val' + (valCls ? ' ' + valCls : ''), val);
    row.appendChild(vEl);
    return row;
  }

  function renderReasonChips(reasons, tier) {
    const wrap = el('div', 'fp-reasons');
    (reasons || []).forEach(r => {
      const chip = el('span', 'fp-reason-chip' + (tier === 'ELEVATED' ? ' elevated' : tier === 'TRIVIAL' ? ' trivial' : ''), r);
      wrap.appendChild(chip);
    });
    return wrap;
  }

  // ── Route Preview ──────────────────────────────────────────────────────────

  function parseCSV(val) {
    return (val || '').split(',').map(s => s.trim()).filter(Boolean);
  }

  async function runRoutePreview() {
    const btn = document.getElementById('fp-route-submit');
    const statusEl = document.getElementById('fp-route-status');
    const outputEl = document.getElementById('fp-route-output');
    if (!btn || !outputEl) return;

    const mutationId = (document.getElementById('fp-route-mutation-id')?.value || '').trim() || 'mut_preview';
    const intent = (document.getElementById('fp-route-intent')?.value || '').trim() || 'refactor';
    const files = parseCSV(document.getElementById('fp-route-files')?.value);
    const riskTags = parseCSV(document.getElementById('fp-route-risk-tags')?.value);
    const locAdded = parseInt(document.getElementById('fp-route-loc-added')?.value || '0', 10) || 0;
    const locDeleted = parseInt(document.getElementById('fp-route-loc-deleted')?.value || '0', 10) || 0;

    btn.disabled = true;
    setStatus(statusEl, 'Routing…', 'busy');
    outputEl.innerHTML = '';

    try {
      const data = await fetchJson('/api/fast-path/route-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mutation_id: mutationId,
          intent,
          files_touched: files,
          loc_added: locAdded,
          loc_deleted: locDeleted,
          risk_tags: riskTags,
          ops: [],
        }),
      });

      const dec = data.decision || {};
      const sum = data.summary || {};
      const tier = sum.tier || 'STANDARD';

      // Result container
      const wrap = el('div', 'fp-route-result');
      wrap.style.cssText = 'display:flex;flex-direction:column;gap:.6rem;margin-top:.6rem';

      // Tier badge row
      const tierRow = el('div', '');
      tierRow.style.cssText = 'display:flex;align-items:center;gap:.75rem;flex-wrap:wrap';
      tierRow.appendChild(renderTierBadge(tier));

      const flagWrap = el('span', '');
      flagWrap.style.cssText = 'display:flex;gap:.4rem;flex-wrap:wrap';
      if (sum.skip_heavy_scoring) {
        const f = el('span', 'fp-reason-chip trivial', '⚡ skip_heavy_scoring');
        flagWrap.appendChild(f);
      }
      if (sum.require_human_review) {
        const f = el('span', 'fp-reason-chip elevated', '▲ require_human_review');
        flagWrap.appendChild(f);
      }
      tierRow.appendChild(flagWrap);
      wrap.appendChild(tierRow);

      // Reasons
      const reasonsLabel = el('div', 'fp-label', 'Routing Reasons');
      wrap.appendChild(reasonsLabel);
      wrap.appendChild(renderReasonChips(sum.reasons, tier));

      // Detail rows
      const details = el('div', '');
      details.style.cssText = 'display:flex;flex-direction:column;gap:0;margin-top:.4rem';
      details.appendChild(detailRow('mutation_id', dec.mutation_id || mutationId));
      details.appendChild(detailRow('route_version', dec.route_version || '—'));
      wrap.appendChild(details);

      // Decision digest
      if (dec.decision_digest) {
        const dLabel = el('div', 'fp-label', 'Decision Digest');
        const dVal = el('div', 'fp-digest', dec.decision_digest);
        wrap.appendChild(dLabel);
        wrap.appendChild(dVal);
      }

      outputEl.appendChild(wrap);
      setStatus(statusEl, 'Route decision: ' + tier, tier === 'ELEVATED' ? 'warn' : tier === 'TRIVIAL' ? 'ok' : 'ok');

      // Push to feed if available
      if (window.addFeed) {
        const icon = TIER_META[tier]?.icon || '→';
        window.addFeed(tier === 'ELEVATED' ? 'warn' : 'ok',
          `${icon} ${mutationId} routed → ${tier}`, 'Fast-Path');
      }

    } catch (err) {
      setStatus(statusEl, 'Error: ' + err.message, 'err');
      outputEl.innerHTML = '';
      if (window.addFeed) window.addFeed('warn', 'Route preview failed: ' + err.message, 'Fast-Path');
    } finally {
      btn.disabled = false;
    }
  }

  // ── Entropy Gate ───────────────────────────────────────────────────────────

  async function runEntropyGate() {
    const btn = document.getElementById('fp-eg-submit');
    const statusEl = document.getElementById('fp-eg-status');
    const outputEl = document.getElementById('fp-eg-output');
    if (!btn || !outputEl) return;

    const mutationId = (document.getElementById('fp-eg-mutation-id')?.value || '').trim() || 'mut_entropy';
    const bits = parseInt(document.getElementById('fp-eg-bits')?.value || '8', 10) || 0;
    const sources = parseCSV(document.getElementById('fp-eg-sources')?.value);
    const strict = document.getElementById('fp-eg-strict')?.value !== 'false';

    btn.disabled = true;
    setStatus(statusEl, 'Evaluating…', 'busy');
    outputEl.innerHTML = '';

    try {
      const data = await fetchJson('/api/fast-path/entropy-gate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mutation_id: mutationId, estimated_bits: bits, sources, strict }),
      });

      const result = data.result || {};
      const verdict = result.verdict || 'WARN';

      const wrap = el('div', '');
      wrap.style.cssText = 'display:flex;flex-direction:column;gap:.6rem;margin-top:.6rem';

      // Verdict badge
      const vRow = el('div', '');
      vRow.style.cssText = 'display:flex;align-items:center;gap:.75rem;flex-wrap:wrap';
      vRow.appendChild(renderVerdictBadge(verdict));
      if (data.denied) {
        vRow.appendChild(el('span', 'fp-reason-chip elevated', '✕ denied'));
      }
      wrap.appendChild(vRow);

      // Reason
      const reasonLabel = el('div', 'fp-label', 'Gate Reason');
      const reasonVal = el('div', 'fp-reason-chip' + (verdict === 'DENY' ? ' elevated' : verdict === 'ALLOW' ? ' trivial' : ''), result.reason || '—');
      wrap.appendChild(reasonLabel);
      wrap.appendChild(reasonVal);

      // Detail rows
      const details = el('div', '');
      details.style.cssText = 'display:flex;flex-direction:column';
      details.appendChild(detailRow('estimated_bits', result.estimated_bits));
      details.appendChild(detailRow('budget_bits', result.budget_bits));
      details.appendChild(detailRow('active_sources', (result.active_sources || []).join(', ') || 'none'));
      details.appendChild(detailRow('gate_version', result.gate_version || '—'));
      wrap.appendChild(details);

      // Gate digest
      if (result.gate_digest) {
        wrap.appendChild(el('div', 'fp-label', 'Gate Digest'));
        wrap.appendChild(el('div', 'fp-digest', result.gate_digest));
      }

      outputEl.appendChild(wrap);
      const statusKind = verdict === 'ALLOW' ? 'ok' : verdict === 'DENY' ? 'err' : 'warn';
      setStatus(statusEl, 'Gate verdict: ' + verdict, statusKind);

      if (window.addFeed) {
        const icon = VERDICT_META[verdict]?.icon || '?';
        window.addFeed(statusKind, `${icon} Entropy gate ${verdict} — ${bits} bits`, 'Fast-Path');
      }

    } catch (err) {
      setStatus(statusEl, 'Error: ' + err.message, 'err');
      outputEl.innerHTML = '';
    } finally {
      btn.disabled = false;
    }
  }

  // ── Checkpoint Chain ───────────────────────────────────────────────────────

  async function verifyCheckpointChain() {
    const statusEl = document.getElementById('fp-chain-status');
    const listEl = document.getElementById('fp-chain-list');
    const badgeEl = document.getElementById('fp-chain-integrity-badge');
    if (!listEl) return;

    setStatus(statusEl, 'Verifying chain…', 'busy');
    listEl.innerHTML = '';
    if (badgeEl) badgeEl.innerHTML = '';

    try {
      const data = await fetchJson('/api/fast-path/checkpoint-chain/verify');

      const ok = data.integrity === true;
      if (badgeEl) {
        const badge = el('span', ok ? 'fp-chain-ok' : 'fp-chain-err');
        badge.textContent = ok ? '✓ Chain intact — ' + data.chain_length + ' links' : '✕ Chain integrity FAILED';
        badgeEl.appendChild(badge);
      }

      setStatus(statusEl, ok
        ? `Verified · ${data.chain_length} links · head: ${(data.head_digest || '').slice(0, 18)}…`
        : 'Integrity check failed', ok ? 'ok' : 'err');

      (data.links || []).forEach((link, i) => {
        const item = el('div', 'fp-chain-link');

        const head = el('div', 'fp-chain-link-head');
        head.appendChild(el('span', 'fp-chain-epoch', `#${i} · ${link.epoch_id}`));
        head.appendChild(el('span', ok ? 'fp-chain-ok' : 'fp-chain-err', ok ? '✓' : '✕'));
        item.appendChild(head);

        item.appendChild(el('div', 'fp-chain-digest', 'chain: ' + (link.chain_digest || '—')));
        if (i > 0) {
          item.appendChild(el('div', 'fp-chain-digest', '  pre: ' + (link.predecessor_digest || '—')));
        }
        listEl.appendChild(item);
      });

      if (window.addFeed) {
        window.addFeed(ok ? 'ok' : 'warn',
          ok ? `Chain verified · ${data.chain_length} links` : 'Chain integrity failure',
          'Fast-Path');
      }

    } catch (err) {
      setStatus(statusEl, 'Error: ' + err.message, 'err');
      if (window.addFeed) window.addFeed('warn', 'Chain verify failed: ' + err.message, 'Fast-Path');
    }
  }

  // ── Module Stats ───────────────────────────────────────────────────────────

  function tagList(containerId, items, cls) {
    const el2 = document.getElementById(containerId);
    if (!el2) return;
    el2.innerHTML = '';
    (items || []).forEach(item => {
      const t = el('span', 'fp-tag ' + (cls || ''), item);
      el2.appendChild(t);
    });
  }

  async function loadStats() {
    const statusEl = document.getElementById('fp-stats-status');
    const badgeEl = document.getElementById('fp-stats-badge');
    setStatus(statusEl, 'Loading…', 'busy');

    try {
      const data = await fetchJson('/api/fast-path/stats');
      const v = data.versions || {};
      const et = data.entropy_thresholds || {};
      const rc = data.route_config || {};

      const set = (id, val) => {
        const e = document.getElementById(id);
        if (e) e.textContent = safeText(val);
      };
      set('fps-route-ver', v.route_optimizer || '—');
      set('fps-gate-ver',   v.entropy_gate || '—');
      set('fps-scorer-ver', v.fast_path_scorer || '—');
      set('fps-chain-ver',  v.checkpoint_chain || '—');
      set('fps-warn-bits',  et.warn_bits != null ? et.warn_bits + ' b' : '—');
      set('fps-deny-bits',  et.deny_bits != null ? et.deny_bits + ' b' : '—');

      tagList('fp-elevated-paths',    rc.elevated_path_prefixes, 'elevated-path');
      tagList('fp-intent-keywords',   rc.elevated_intent_keywords, 'intent-kw');
      tagList('fp-trivial-ops',       rc.trivial_op_types, 'trivial-op');

      if (badgeEl) badgeEl.textContent = 'loaded';
      setStatus(statusEl, 'Stats loaded · ' + Object.keys(v).length + ' modules', 'ok');
      if (window.addFeed) window.addFeed('ok', 'Fast-path stats loaded', 'Fast-Path');

    } catch (err) {
      setStatus(statusEl, 'Stats unavailable: ' + err.message, 'err');
      const b = document.getElementById('fp-stats-badge');
      if (b) b.textContent = 'unavailable';
    }
  }

  // ── Section toggle ─────────────────────────────────────────────────────────

  function setupToggle() {
    const btn = document.getElementById('fp-toggle-btn');
    const body = document.getElementById('fp-panel-body');
    if (!btn || !body) return;
    let collapsed = false;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      collapsed = !collapsed;
      body.classList.toggle('fp-collapsed', collapsed);
      btn.textContent = collapsed ? 'show' : 'hide';
    });
    document.getElementById('fp-section-head')?.addEventListener('click', (e) => {
      if (e.target === btn) return;
      collapsed = !collapsed;
      body.classList.toggle('fp-collapsed', collapsed);
      btn.textContent = collapsed ? 'show' : 'hide';
    });
  }

  // ── Event wiring ───────────────────────────────────────────────────────────

  function wireEvents() {
    document.getElementById('fp-route-submit')?.addEventListener('click', runRoutePreview);
    document.getElementById('fp-eg-submit')?.addEventListener('click', runEntropyGate);
    document.getElementById('fp-chain-verify-btn')?.addEventListener('click', verifyCheckpointChain);
    document.getElementById('fp-stats-reload')?.addEventListener('click', loadStats);

    document.getElementById('fp-route-clear')?.addEventListener('click', () => {
      ['fp-route-mutation-id','fp-route-intent','fp-route-files','fp-route-risk-tags'].forEach(id => {
        const e = document.getElementById(id); if (e) e.value = '';
      });
      ['fp-route-loc-added','fp-route-loc-deleted'].forEach(id => {
        const e = document.getElementById(id); if (e) e.value = '0';
      });
      const out = document.getElementById('fp-route-output'); if (out) out.innerHTML = '';
      setStatus(document.getElementById('fp-route-status'), 'Cleared.', 'idle');
    });

    document.getElementById('fp-eg-clear')?.addEventListener('click', () => {
      ['fp-eg-mutation-id','fp-eg-sources'].forEach(id => {
        const e = document.getElementById(id); if (e) e.value = '';
      });
      const b = document.getElementById('fp-eg-bits'); if (b) b.value = '8';
      const out = document.getElementById('fp-eg-output'); if (out) out.innerHTML = '';
      setStatus(document.getElementById('fp-eg-status'), 'Cleared.', 'idle');
    });

    // Keyboard shortcuts: Enter on route / entropy inputs triggers run
    ['fp-route-mutation-id','fp-route-intent','fp-route-files','fp-route-risk-tags',
     'fp-route-loc-added','fp-route-loc-deleted'].forEach(id => {
      document.getElementById(id)?.addEventListener('keydown', e => {
        if (e.key === 'Enter') runRoutePreview();
      });
    });
    ['fp-eg-mutation-id','fp-eg-bits','fp-eg-sources'].forEach(id => {
      document.getElementById(id)?.addEventListener('keydown', e => {
        if (e.key === 'Enter') runEntropyGate();
      });
    });
  }

  // ── Mount ──────────────────────────────────────────────────────────────────

  function mount() {
    // Find a good anchor: after the last main section card in the layout
    const layout = document.querySelector('.layout');
    if (!layout) return;

    // Insert before the last child (usually the cockpit) or at end
    const anchor = layout.querySelector('#fp-intelligence-section');
    if (anchor) return; // already mounted

    const div = document.createElement('div');
    div.innerHTML = buildPanelHTML();
    const inserted = div.firstElementChild;

    // Insert before script tags / near end of layout
    const scripts = layout.querySelectorAll('script');
    if (scripts.length) {
      layout.insertBefore(inserted, scripts[0]);
    } else {
      layout.appendChild(inserted);
    }

    setupToggle();
    wireEvents();

    // Initial data loads
    loadStats();
    verifyCheckpointChain();
    setInterval(loadStats, STATS_POLL_MS);
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  function init() {
    injectStyles();
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', mount);
    } else {
      mount();
    }
  }

  init();

})();
