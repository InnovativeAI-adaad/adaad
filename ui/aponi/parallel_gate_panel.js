// SPDX-License-Identifier: Apache-2.0
// Aponi Parallel Governance Gate Visualizer — ADAAD v0.66
//
// Visualizes ParallelGovernanceGate evaluation in real time:
//   · Axis swimlane board — one lane per axis, animates while running
//   · Decision verdict banner — APPROVED / REJECTED with decision_id digest
//   · Timing waterfall — per-axis wall-clock duration bars
//   · Axis builder — add/remove axes from the probe library or custom
//   · Preset scenarios — standard approval, elevated review, mixed failure
//   · Human override toggle with governance annotation
//
// Calls:
//   GET  /api/governance/parallel-gate/probe-library  → available probes
//   POST /api/governance/parallel-gate/evaluate       → run evaluation

(function () {
  'use strict';

  const FETCH_TIMEOUT_MS = 12000;
  const SECTION_ID       = 'pg-gate-section';
  const PANEL_ID         = 'pg-gate-panel';

  // ── Preset scenarios ───────────────────────────────────────────────────────
  const PRESETS = {
    standard_approve: {
      label: 'Standard Approve',
      icon: '✓',
      trust_mode: 'standard',
      human_override: false,
      axes: [
        { axis: 'entropy',      rule_id: 'budget_ok'       },
        { axis: 'entropy',      rule_id: 'source_clean'    },
        { axis: 'constitution', rule_id: 'tier_ok'         },
        { axis: 'constitution', rule_id: 'hash_valid'      },
        { axis: 'lineage',      rule_id: 'chain_intact'    },
        { axis: 'sandbox',      rule_id: 'preflight_ok'    },
      ],
    },
    elevated_mixed: {
      label: 'Elevated Mixed',
      icon: '▲',
      trust_mode: 'elevated',
      human_override: false,
      axes: [
        { axis: 'entropy',      rule_id: 'budget_ok'       },
        { axis: 'entropy',      rule_id: 'nondeterministic'},
        { axis: 'constitution', rule_id: 'tier_ok'         },
        { axis: 'constitution', rule_id: 'hash_mismatch'   },
        { axis: 'founders_law', rule_id: 'invariant_ok'    },
        { axis: 'lineage',      rule_id: 'chain_intact'    },
        { axis: 'sandbox',      rule_id: 'preflight_ok'    },
        { axis: 'replay',       rule_id: 'determinism_ok'  },
      ],
    },
    full_rejection: {
      label: 'Full Rejection',
      icon: '✕',
      trust_mode: 'elevated',
      human_override: false,
      axes: [
        { axis: 'entropy',      rule_id: 'budget_exceeded' },
        { axis: 'entropy',      rule_id: 'nondeterministic'},
        { axis: 'constitution', rule_id: 'tier_violated'   },
        { axis: 'constitution', rule_id: 'hash_mismatch'   },
        { axis: 'founders_law', rule_id: 'invariant_violated'},
        { axis: 'lineage',      rule_id: 'chain_broken'    },
        { axis: 'sandbox',      rule_id: 'preflight_failed'},
        { axis: 'replay',       rule_id: 'baseline_mismatch'},
      ],
    },
    human_override: {
      label: 'Human Override',
      icon: '⊕',
      trust_mode: 'elevated',
      human_override: true,
      axes: [
        { axis: 'entropy',      rule_id: 'budget_ok'       },
        { axis: 'constitution', rule_id: 'tier_ok'         },
        { axis: 'founders_law', rule_id: 'invariant_ok'    },
        { axis: 'lineage',      rule_id: 'chain_intact'    },
        { axis: 'sandbox',      rule_id: 'isolation_ok'    },
        { axis: 'replay',       rule_id: 'baseline_match'  },
      ],
    },
    deep_audit: {
      label: 'Deep Audit',
      icon: '⊞',
      trust_mode: 'standard',
      human_override: false,
      axes: [
        { axis: 'entropy',      rule_id: 'budget_ok'       },
        { axis: 'entropy',      rule_id: 'source_clean'    },
        { axis: 'constitution', rule_id: 'tier_ok'         },
        { axis: 'constitution', rule_id: 'hash_valid'      },
        { axis: 'founders_law', rule_id: 'invariant_ok'    },
        { axis: 'lineage',      rule_id: 'chain_intact'    },
        { axis: 'lineage',      rule_id: 'digest_match'    },
        { axis: 'sandbox',      rule_id: 'preflight_ok'    },
        { axis: 'sandbox',      rule_id: 'isolation_ok'    },
        { axis: 'replay',       rule_id: 'baseline_match'  },
        { axis: 'replay',       rule_id: 'determinism_ok'  },
      ],
    },
  };

  // ── Axis colour palette (stable per axis name) ─────────────────────────────
  const AXIS_COLORS = {
    entropy:       '#60a5fa',
    constitution:  '#a78bfa',
    founders_law:  '#f59e0b',
    lineage:       '#34d399',
    sandbox:       '#fb923c',
    replay:        '#e879f9',
    _default:      '#94a3b8',
  };

  function axisColor(axis) {
    return AXIS_COLORS[axis] || AXIS_COLORS._default;
  }

  // ── Utilities ──────────────────────────────────────────────────────────────

  function safeText(v) {
    if (v == null) return '—';
    if (typeof v === 'object') { try { return JSON.stringify(v); } catch (_) { return '[obj]'; } }
    return String(v);
  }

  function mk(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls)  e.className   = cls;
    if (text != null) e.textContent = safeText(text);
    return e;
  }

  function setStatus(el, msg, kind) {
    if (!el) return;
    el.textContent = msg;
    el.className = 'pg-status pg-status--' + (kind || 'idle');
  }

  async function fetchJson(url, opts) {
    const ctrl = new AbortController();
    const tid  = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(url, { cache: 'no-store', signal: ctrl.signal, ...(opts || {}) });
      clearTimeout(tid);
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || 'HTTP ' + res.status);
      }
      return await res.json();
    } catch (e) { clearTimeout(tid); throw e; }
  }

  function shortDigest(d) {
    if (!d) return '—';
    const raw = d.replace(/^sha256:/, '');
    return raw.slice(0, 8) + '…' + raw.slice(-8);
  }

  // ── State ──────────────────────────────────────────────────────────────────
  let state = {
    probeLibrary: null,          // fetched from server
    currentAxes: [],             // [{axis, rule_id, timeout_seconds}]
    lastDecision: null,          // last full server response
    running: false,
    mutationCounter: 1,
  };

  // ── Style injection ────────────────────────────────────────────────────────

  function injectStyles() {
    if (document.getElementById('pg-styles')) return;
    const s = document.createElement('style');
    s.id = 'pg-styles';
    s.textContent = `
/* ── Parallel Gate Visualizer ─────────────────────────────────────────────── */
#pg-gate-section { margin-top: 2.5rem; }

.pg-section-head {
  display: flex; align-items: center; gap: .6rem;
  margin-bottom: 1.25rem; cursor: pointer; user-select: none;
}
.pg-section-label {
  font-family: var(--mono); font-size: .7rem; letter-spacing: .12em;
  text-transform: uppercase; color: var(--text3);
}
.pg-section-line { flex: 1; height: 1px; background: var(--border); }
.pg-toggle-btn {
  font-family: var(--mono); font-size: .65rem; color: var(--text3);
  padding: .15rem .45rem; border: 1px solid var(--border);
  border-radius: 4px; background: var(--bg3); cursor: pointer;
}
.pg-panel-body.pg-collapsed { display: none; }

/* Layout */
.pg-top-row {
  display: grid; grid-template-columns: 1fr 1.6fr;
  gap: 1rem; margin-bottom: 1rem;
}
@media (max-width: 720px) { .pg-top-row { grid-template-columns: 1fr; } }

/* Cards */
.pg-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.1rem;
  display: flex; flex-direction: column; gap: .75rem;
  transition: border-color .18s;
}
.pg-card:hover { border-color: var(--border2); }
.pg-card-full { grid-column: 1 / -1; }
.pg-card-title {
  font-family: var(--mono); font-size: .68rem; letter-spacing: .1em;
  text-transform: uppercase; color: var(--accent2);
  display: flex; align-items: center; justify-content: space-between; gap: .5rem;
}
.pg-card-title-left { display: flex; align-items: center; gap: .4rem; }
.pg-badge {
  font-size: .58rem; padding: .1rem .35rem; border-radius: 3px;
  background: var(--bg3); border: 1px solid var(--border); color: var(--text3);
}

/* Status */
.pg-status {
  font-family: var(--mono); font-size: .7rem; min-height: 1em;
  transition: color .18s;
}
.pg-status--idle { color: var(--text3); }
.pg-status--ok   { color: var(--ok); }
.pg-status--warn { color: var(--warn); }
.pg-status--err  { color: var(--danger); }
.pg-status--busy { color: var(--accent2); }

/* Form */
.pg-row   { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; }
.pg-field { display: flex; flex-direction: column; gap: .3rem; }
.pg-label { font-size: .7rem; color: var(--text2); font-weight: 500; letter-spacing: .03em; }
.pg-input, .pg-select {
  padding: .45rem .6rem; background: var(--bg2);
  border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-family: var(--sans); font-size: .8rem;
  outline: none; transition: border-color .18s;
}
.pg-input:focus, .pg-select:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-glow); }
.pg-input::placeholder { color: var(--text3); }
.pg-select { cursor: pointer; }

/* Buttons */
.pg-btn {
  display: inline-flex; align-items: center; gap: .4rem;
  padding: .45rem .9rem; border: none; border-radius: 6px;
  font-family: var(--mono); font-size: .68rem; letter-spacing: .06em;
  font-weight: 700; text-transform: uppercase; cursor: pointer;
  transition: all .18s; white-space: nowrap; background: var(--accent); color: #fff;
}
.pg-btn:hover { background: var(--accent2); box-shadow: 0 0 14px var(--accent-glow); }
.pg-btn:disabled { opacity: .45; cursor: not-allowed; box-shadow: none; }
.pg-btn-ghost {
  background: transparent; color: var(--text2);
  border: 1px solid var(--border2);
}
.pg-btn-ghost:hover { border-color: var(--accent); color: var(--accent2); background: var(--accent-glow); box-shadow: none; }
.pg-btn-danger {
  background: transparent; color: var(--danger);
  border: 1px solid rgba(239,68,68,.35);
}
.pg-btn-danger:hover { background: var(--danger-bg); box-shadow: none; }
.pg-btn-sm { padding: .3rem .6rem; font-size: .62rem; }

/* Preset buttons */
.pg-presets { display: flex; flex-wrap: wrap; gap: .35rem; }
.pg-preset-btn {
  padding: .3rem .7rem; border-radius: 99px; font-family: var(--mono);
  font-size: .64rem; letter-spacing: .05em; font-weight: 700; cursor: pointer;
  border: 1px solid var(--border2); background: var(--bg3); color: var(--text2);
  transition: all .18s; white-space: nowrap;
}
.pg-preset-btn:hover { border-color: var(--accent); color: var(--accent2); background: var(--accent-glow); }

/* Axis list */
.pg-axis-list { display: flex; flex-direction: column; gap: .35rem; max-height: 280px; overflow-y: auto; }
.pg-axis-item {
  display: flex; align-items: center; gap: .5rem;
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: 6px; padding: .4rem .65rem;
  transition: border-color .18s;
}
.pg-axis-item:hover { border-color: var(--border2); }
.pg-axis-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  transition: background .18s;
}
.pg-axis-name {
  font-family: var(--mono); font-size: .7rem; color: var(--text2); flex: 1;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pg-axis-rule { font-family: var(--mono); font-size: .62rem; color: var(--text3); }
.pg-axis-remove {
  font-family: var(--mono); font-size: .65rem; color: var(--danger);
  cursor: pointer; padding: .1rem .3rem; border-radius: 3px;
  border: 1px solid transparent; transition: all .15s; flex-shrink: 0;
}
.pg-axis-remove:hover { background: var(--danger-bg); border-color: rgba(239,68,68,.3); }

/* Add axis row */
.pg-add-row { display: flex; gap: .4rem; flex-wrap: wrap; align-items: flex-end; }

/* Swimlane board */
.pg-swimlane-board {
  display: flex; flex-direction: column; gap: .45rem;
  min-height: 60px;
}
.pg-swim-lane {
  display: flex; align-items: center; gap: .6rem;
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: 7px; padding: .45rem .75rem;
  transition: border-color .3s, background .3s;
}
.pg-swim-lane.running { border-color: rgba(59,130,246,.45); background: rgba(59,130,246,.04); }
.pg-swim-lane.pass    { border-color: rgba(34,197,94,.4);  background: rgba(34,197,94,.04); }
.pg-swim-lane.fail    { border-color: rgba(239,68,68,.4);  background: rgba(239,68,68,.04); }

.pg-swim-axis-tag {
  font-family: var(--mono); font-size: .62rem; font-weight: 700;
  padding: .15rem .45rem; border-radius: 4px; flex-shrink: 0;
  min-width: 80px; text-align: center; letter-spacing: .04em;
}
.pg-swim-rule {
  font-family: var(--mono); font-size: .65rem; color: var(--text3); flex: 1;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pg-swim-reason {
  font-family: var(--mono); font-size: .62rem; color: var(--text3);
  max-width: 200px; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pg-swim-icon {
  font-size: 1rem; flex-shrink: 0; width: 1.2rem; text-align: center; transition: all .2s;
}
.pg-swim-icon.spin { animation: pg-spin 0.7s linear infinite; }
@keyframes pg-spin { to { transform: rotate(360deg); } }

.pg-swim-duration {
  font-family: var(--mono); font-size: .6rem; color: var(--text3);
  min-width: 40px; text-align: right; flex-shrink: 0;
}

/* Timing waterfall */
.pg-waterfall { display: flex; flex-direction: column; gap: .3rem; }
.pg-waterfall-row { display: flex; align-items: center; gap: .5rem; }
.pg-waterfall-label {
  font-family: var(--mono); font-size: .62rem; color: var(--text3);
  width: 140px; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pg-waterfall-track {
  flex: 1; height: 10px; background: var(--bg3);
  border: 1px solid var(--border); border-radius: 99px; overflow: hidden;
}
.pg-waterfall-fill {
  height: 100%; border-radius: 99px; transition: width .5s ease;
}
.pg-waterfall-ms {
  font-family: var(--mono); font-size: .6rem; color: var(--text3);
  width: 44px; text-align: right; flex-shrink: 0;
}

/* Decision verdict banner */
.pg-verdict-banner {
  border-radius: var(--radius); padding: 1rem 1.25rem;
  display: flex; align-items: center; gap: 1rem;
  border: 1.5px solid; transition: all .3s; flex-wrap: wrap;
}
.pg-verdict-banner.approved {
  border-color: rgba(34,197,94,.5); background: rgba(34,197,94,.06);
}
.pg-verdict-banner.rejected {
  border-color: rgba(239,68,68,.5); background: rgba(239,68,68,.06);
}
.pg-verdict-banner.idle {
  border-color: var(--border); background: var(--bg3);
}
.pg-verdict-icon {
  font-size: 2rem; flex-shrink: 0; line-height: 1;
}
.pg-verdict-label {
  font-family: var(--mono); font-size: 1.15rem; font-weight: 700; letter-spacing: .1em;
}
.pg-verdict-banner.approved .pg-verdict-label { color: var(--ok); }
.pg-verdict-banner.rejected .pg-verdict-label { color: var(--danger); }
.pg-verdict-banner.idle .pg-verdict-label { color: var(--text3); }
.pg-verdict-meta { display: flex; flex-direction: column; gap: .2rem; flex: 1; min-width: 0; }
.pg-verdict-sub  { font-family: var(--mono); font-size: .65rem; color: var(--text3); }

/* Summary stats row */
.pg-summary-row {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: .4rem;
}
.pg-summary-cell {
  background: var(--bg3); border: 1px solid var(--border); border-radius: 7px;
  padding: .5rem .65rem; display: flex; flex-direction: column; gap: .15rem;
}
.pg-summary-val { font-family: var(--mono); font-size: 1rem; font-weight: 700; color: var(--accent2); }
.pg-summary-lbl { font-family: var(--mono); font-size: .58rem; color: var(--text3); text-transform: uppercase; }

/* Digest */
.pg-digest {
  font-family: var(--mono); font-size: .62rem; color: var(--text3);
  word-break: break-all; padding: .35rem .5rem;
  background: var(--bg2); border: 1px solid var(--border); border-radius: 5px;
}

/* Reason codes */
.pg-reason-chips { display: flex; flex-wrap: wrap; gap: .25rem; }
.pg-reason-chip {
  font-family: var(--mono); font-size: .62rem; padding: .12rem .45rem;
  border-radius: 4px; background: var(--bg3);
  border: 1px solid var(--border); color: var(--text2);
}
.pg-reason-chip.fail { border-color: rgba(239,68,68,.4); color: #f87171; }
.pg-reason-chip.pass { border-color: rgba(34,197,94,.4);  color: #4ade80; }

/* Override toggle */
.pg-override-row {
  display: flex; align-items: center; gap: .6rem;
  padding: .5rem .7rem; background: var(--warn-bg);
  border: 1px solid rgba(245,158,11,.3); border-radius: 6px;
}
.pg-override-label { font-family: var(--mono); font-size: .72rem; color: var(--warn); flex: 1; }
.pg-override-switch {
  position: relative; width: 36px; height: 20px; flex-shrink: 0;
}
.pg-override-switch input { opacity: 0; width: 0; height: 0; }
.pg-override-track {
  position: absolute; inset: 0; cursor: pointer;
  background: var(--bg3); border: 1px solid var(--border); border-radius: 99px;
  transition: background .2s;
}
.pg-override-track::after {
  content: ''; position: absolute; top: 2px; left: 2px;
  width: 14px; height: 14px; background: var(--text3);
  border-radius: 50%; transition: transform .2s, background .2s;
}
.pg-override-switch input:checked + .pg-override-track { background: var(--warn); border-color: var(--warn); }
.pg-override-switch input:checked + .pg-override-track::after { transform: translateX(16px); background: #fff; }

/* Empty swimlane */
.pg-swim-empty {
  font-family: var(--mono); font-size: .72rem; color: var(--text3);
  text-align: center; padding: 1.5rem; border: 1px dashed var(--border);
  border-radius: 7px;
}
`;
    document.head.appendChild(s);
  }

  // ── HTML template ──────────────────────────────────────────────────────────

  function buildHTML() {
    return `
<div id="pg-gate-section">
  <div class="pg-section-head" id="pg-section-head">
    <span class="pg-section-label">⫶ Parallel Governance Gate</span>
    <div class="pg-section-line"></div>
    <button class="pg-toggle-btn" id="pg-toggle-btn" type="button">hide</button>
  </div>

  <div id="pg-panel-body" class="pg-panel-body">

    <!-- Top row: controls (left) + verdict (right) -->
    <div class="pg-top-row">

      <!-- Left: mutation config + axis builder -->
      <div class="pg-card" style="gap:.85rem">
        <div class="pg-card-title">
          <div class="pg-card-title-left">Gate Configuration <span class="pg-badge">ParallelGovernanceGate</span></div>
        </div>

        <!-- Mutation ID + trust mode -->
        <div class="pg-row">
          <div class="pg-field">
            <div class="pg-label">Mutation ID</div>
            <input class="pg-input" id="pg-mutation-id" placeholder="mut_pgv_001" />
          </div>
          <div class="pg-field">
            <div class="pg-label">Trust Mode</div>
            <select class="pg-select" id="pg-trust-mode">
              <option value="standard">standard</option>
              <option value="elevated">elevated</option>
              <option value="strict">strict</option>
            </select>
          </div>
        </div>

        <!-- Human override -->
        <div class="pg-override-row">
          <div class="pg-override-label">⊕ Human Override — bypasses failed axes if founders-law passes</div>
          <label class="pg-override-switch">
            <input type="checkbox" id="pg-human-override" />
            <span class="pg-override-track"></span>
          </label>
        </div>

        <!-- Preset scenarios -->
        <div>
          <div class="pg-label" style="margin-bottom:.4rem">Preset Scenarios</div>
          <div class="pg-presets" id="pg-presets"></div>
        </div>

        <!-- Add axis -->
        <div>
          <div class="pg-label" style="margin-bottom:.4rem">Axis Builder</div>
          <div class="pg-add-row" id="pg-add-row">
            <div class="pg-field" style="flex:1;min-width:100px">
              <div class="pg-label">Axis</div>
              <select class="pg-select" id="pg-add-axis"></select>
            </div>
            <div class="pg-field" style="flex:1.4;min-width:130px">
              <div class="pg-label">Rule</div>
              <select class="pg-select" id="pg-add-rule"></select>
            </div>
            <button class="pg-btn pg-btn-sm" id="pg-add-btn" type="button" style="margin-top:1.4rem">+ Add</button>
          </div>
        </div>

        <!-- Current axis list -->
        <div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.4rem">
            <div class="pg-label">Axis Queue <span id="pg-axis-count" style="color:var(--accent2)">0</span></div>
            <button class="pg-btn pg-btn-ghost pg-btn-sm" id="pg-clear-axes" type="button">Clear All</button>
          </div>
          <div class="pg-axis-list" id="pg-axis-list">
            <div class="pg-swim-empty">No axes configured. Add or load a preset.</div>
          </div>
        </div>

        <!-- Run -->
        <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center">
          <button class="pg-btn" id="pg-run-btn" type="button">▶ Evaluate Gate</button>
          <div class="pg-status pg-status--idle" id="pg-run-status" style="flex:1"></div>
        </div>
      </div>

      <!-- Right: verdict + summary -->
      <div style="display:flex;flex-direction:column;gap:1rem">

        <!-- Verdict banner -->
        <div class="pg-verdict-banner idle" id="pg-verdict-banner">
          <div class="pg-verdict-icon" id="pg-verdict-icon">◌</div>
          <div class="pg-verdict-meta">
            <div class="pg-verdict-label" id="pg-verdict-label">AWAITING EVALUATION</div>
            <div class="pg-verdict-sub" id="pg-verdict-trust">trust_mode: —</div>
            <div class="pg-verdict-sub" id="pg-verdict-elapsed">wall_time: —</div>
          </div>
        </div>

        <!-- Summary stats -->
        <div class="pg-summary-row" id="pg-summary-row">
          <div class="pg-summary-cell"><div class="pg-summary-val" id="pg-s-total">—</div><div class="pg-summary-lbl">Total Axes</div></div>
          <div class="pg-summary-cell"><div class="pg-summary-val" id="pg-s-pass"  style="color:var(--ok)">—</div><div class="pg-summary-lbl">Passed</div></div>
          <div class="pg-summary-cell"><div class="pg-summary-val" id="pg-s-fail"  style="color:var(--danger)">—</div><div class="pg-summary-lbl">Failed</div></div>
          <div class="pg-summary-cell"><div class="pg-summary-val" id="pg-s-workers">—</div><div class="pg-summary-lbl">Workers</div></div>
        </div>

        <!-- Decision ID digest -->
        <div class="pg-card" style="gap:.5rem;padding:.8rem 1rem">
          <div class="pg-label">Decision Digest</div>
          <div class="pg-digest" id="pg-decision-digest">—</div>
        </div>

        <!-- Reason codes -->
        <div class="pg-card" style="gap:.5rem;padding:.8rem 1rem">
          <div class="pg-label">Reason Codes</div>
          <div class="pg-reason-chips" id="pg-reason-chips">
            <span class="pg-reason-chip">—</span>
          </div>
        </div>

      </div>
    </div>

    <!-- Swimlane board (full width) -->
    <div class="pg-card pg-card-full" style="gap:.75rem">
      <div class="pg-card-title">
        <div class="pg-card-title-left">Axis Swimlanes <span class="pg-badge" id="pg-swim-badge">0 axes</span></div>
        <div class="pg-status pg-status--idle" id="pg-swim-status"></div>
      </div>
      <div class="pg-swimlane-board" id="pg-swimlane-board">
        <div class="pg-swim-empty">Add axes and run the gate to see swimlane results.</div>
      </div>
    </div>

    <!-- Timing waterfall (full width) -->
    <div class="pg-card pg-card-full" id="pg-waterfall-card" style="gap:.75rem;display:none">
      <div class="pg-card-title">Timing Waterfall</div>
      <div class="pg-waterfall" id="pg-waterfall"></div>
      <div class="pg-status pg-status--idle" id="pg-waterfall-status"></div>
    </div>

  </div><!-- end pg-panel-body -->
</div>
`;
  }

  // ── Probe library loading ──────────────────────────────────────────────────

  async function loadProbeLibrary() {
    try {
      const data = await fetchJson('/api/governance/parallel-gate/probe-library');
      state.probeLibrary = data.axes || {};
      buildAxisSelectors();
      if (window.addFeed) window.addFeed('ok', 'Gate probe library loaded (' + data.total_probes + ' probes)', 'ParallelGate');
    } catch (err) {
      if (window.addFeed) window.addFeed('warn', 'Probe library unavailable: ' + err.message, 'ParallelGate');
      // Fallback: build from PRESETS knowledge
      const fallback = {};
      Object.values(PRESETS).forEach(p =>
        p.axes.forEach(a => {
          (fallback[a.axis] = fallback[a.axis] || []).push({ rule_id: a.rule_id, default_ok: true, default_reason: '' });
        })
      );
      state.probeLibrary = fallback;
      buildAxisSelectors();
    }
  }

  function buildAxisSelectors() {
    const axisEl = document.getElementById('pg-add-axis');
    const ruleEl = document.getElementById('pg-add-rule');
    if (!axisEl || !ruleEl || !state.probeLibrary) return;

    const axes = Object.keys(state.probeLibrary).sort();
    axisEl.innerHTML = axes.map(a => `<option value="${a}">${a}</option>`).join('');

    function refreshRules() {
      const axis = axisEl.value;
      const rules = state.probeLibrary[axis] || [];
      ruleEl.innerHTML = rules.map(r =>
        `<option value="${r.rule_id}">${r.rule_id}</option>`
      ).join('');
    }
    axisEl.addEventListener('change', refreshRules);
    refreshRules();
  }

  // ── Preset loading ─────────────────────────────────────────────────────────

  function buildPresets() {
    const wrap = document.getElementById('pg-presets');
    if (!wrap) return;
    wrap.innerHTML = '';
    Object.entries(PRESETS).forEach(([key, preset]) => {
      const btn = mk('button', 'pg-preset-btn', preset.icon + ' ' + preset.label);
      btn.title = `${preset.axes.length} axes · trust: ${preset.trust_mode}`;
      btn.addEventListener('click', () => loadPreset(key));
      wrap.appendChild(btn);
    });
  }

  function loadPreset(key) {
    const preset = PRESETS[key];
    if (!preset) return;

    const tm = document.getElementById('pg-trust-mode');
    const ho = document.getElementById('pg-human-override');
    if (tm) tm.value = preset.trust_mode;
    if (ho) ho.checked = !!preset.human_override;

    state.currentAxes = preset.axes.map(a => ({ ...a, timeout_seconds: 5.0 }));
    renderAxisList();
    updateSwimlanePlaceholders();
    if (window.addFeed) window.addFeed('ok', `Preset loaded: ${preset.label}`, 'ParallelGate');
  }

  // ── Axis list management ───────────────────────────────────────────────────

  function renderAxisList() {
    const list = document.getElementById('pg-axis-list');
    const count = document.getElementById('pg-axis-count');
    if (!list) return;
    if (count) count.textContent = state.currentAxes.length;

    if (!state.currentAxes.length) {
      list.innerHTML = '<div class="pg-swim-empty">No axes configured. Add or load a preset.</div>';
      return;
    }

    list.innerHTML = '';
    state.currentAxes.forEach((ax, i) => {
      const item = mk('div', 'pg-axis-item');

      const dot = mk('div', 'pg-axis-dot');
      dot.style.background = axisColor(ax.axis);
      item.appendChild(dot);

      const name = mk('span', 'pg-axis-name', ax.axis);
      item.appendChild(name);

      const rule = mk('span', 'pg-axis-rule', ax.rule_id);
      item.appendChild(rule);

      const rm = mk('span', 'pg-axis-remove', '✕');
      rm.title = 'Remove axis';
      rm.addEventListener('click', () => {
        state.currentAxes.splice(i, 1);
        renderAxisList();
        updateSwimlanePlaceholders();
      });
      item.appendChild(rm);

      list.appendChild(item);
    });
  }

  function addAxis() {
    const axisEl = document.getElementById('pg-add-axis');
    const ruleEl = document.getElementById('pg-add-rule');
    if (!axisEl || !ruleEl) return;
    const axis = axisEl.value.trim();
    const rule_id = ruleEl.value.trim();
    if (!axis || !rule_id) return;
    state.currentAxes.push({ axis, rule_id, timeout_seconds: 5.0 });
    renderAxisList();
    updateSwimlanePlaceholders();
  }

  function updateSwimlanePlaceholders() {
    const board = document.getElementById('pg-swimlane-board');
    const badge = document.getElementById('pg-swim-badge');
    if (!board) return;
    if (badge) badge.textContent = state.currentAxes.length + ' axes';

    if (!state.currentAxes.length) {
      board.innerHTML = '<div class="pg-swim-empty">Add axes and run the gate to see swimlane results.</div>';
      return;
    }
    // Show pending lanes
    board.innerHTML = '';
    state.currentAxes.forEach(ax => {
      board.appendChild(buildSwimLane(ax.axis, ax.rule_id, 'pending', null, null));
    });
  }

  function buildSwimLane(axis, rule_id, state_cls, reason, duration_ms) {
    const lane = mk('div', 'pg-swim-lane ' + (state_cls || 'pending'));

    const tag = mk('span', 'pg-swim-axis-tag', axis);
    tag.style.background = axisColor(axis) + '20';
    tag.style.color = axisColor(axis);
    tag.style.borderLeft = `3px solid ${axisColor(axis)}`;
    lane.appendChild(tag);

    lane.appendChild(mk('span', 'pg-swim-rule', rule_id));
    lane.appendChild(mk('span', 'pg-swim-reason', reason || '—'));

    let icon;
    if (state_cls === 'running') {
      icon = mk('span', 'pg-swim-icon spin', '◌');
    } else if (state_cls === 'pass') {
      icon = mk('span', 'pg-swim-icon', '✓');
      icon.style.color = 'var(--ok)';
    } else if (state_cls === 'fail') {
      icon = mk('span', 'pg-swim-icon', '✕');
      icon.style.color = 'var(--danger)';
    } else {
      icon = mk('span', 'pg-swim-icon', '·');
      icon.style.color = 'var(--text3)';
    }
    lane.appendChild(icon);

    const dur = mk('span', 'pg-swim-duration', duration_ms != null ? duration_ms + 'ms' : '—');
    lane.appendChild(dur);

    return lane;
  }

  // ── Evaluation run ─────────────────────────────────────────────────────────

  async function runGate() {
    if (state.running) return;
    const btn = document.getElementById('pg-run-btn');
    const runStatus = document.getElementById('pg-run-status');
    const swimStatus = document.getElementById('pg-swim-status');

    if (!state.currentAxes.length) {
      setStatus(runStatus, 'Add at least one axis first.', 'warn');
      return;
    }

    const mutationId = (document.getElementById('pg-mutation-id')?.value.trim()) ||
      ('mut_pg_' + String(state.mutationCounter++).padStart(3, '0'));
    const trustMode = document.getElementById('pg-trust-mode')?.value || 'standard';
    const humanOverride = !!document.getElementById('pg-human-override')?.checked;

    state.running = true;
    if (btn) btn.disabled = true;

    // Reset verdict
    resetVerdict();
    setStatus(runStatus, 'Submitting…', 'busy');
    setStatus(swimStatus, 'Evaluating axes concurrently…', 'busy');

    // Animate lanes as "running"
    const board = document.getElementById('pg-swimlane-board');
    if (board) {
      board.innerHTML = '';
      state.currentAxes.forEach(ax => {
        board.appendChild(buildSwimLane(ax.axis, ax.rule_id, 'running', null, null));
      });
    }

    try {
      const data = await fetchJson('/api/governance/parallel-gate/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mutation_id: mutationId,
          trust_mode: trustMode,
          human_override: humanOverride,
          axis_specs: state.currentAxes.map(a => ({
            axis: a.axis,
            rule_id: a.rule_id,
            timeout_seconds: a.timeout_seconds || 5.0,
          })),
          max_workers: 8,
        }),
      });

      state.lastDecision = data;
      renderDecision(data, mutationId, trustMode);
      setStatus(runStatus, 'Evaluation complete · ' + data.wall_elapsed_ms + 'ms', 'ok');
      setStatus(swimStatus, data.axis_count + ' axes evaluated · ' + data.gate_version, 'ok');

      if (window.addFeed) {
        const dec = data.decision || {};
        const icon = dec.approved ? '✓' : '✕';
        const kind = dec.approved ? 'ok' : 'warn';
        window.addFeed(kind,
          `${icon} Gate ${dec.approved ? 'APPROVED' : 'REJECTED'} · ${mutationId} · ${data.wall_elapsed_ms}ms`,
          'ParallelGate');
      }

    } catch (err) {
      setStatus(runStatus, 'Error: ' + err.message, 'err');
      setStatus(swimStatus, 'Evaluation failed.', 'err');
      if (board) board.innerHTML = '<div class="pg-swim-empty">Evaluation error. Check server connection.</div>';
      if (window.addFeed) window.addFeed('warn', 'Gate evaluation failed: ' + err.message, 'ParallelGate');
    } finally {
      state.running = false;
      if (btn) btn.disabled = false;
    }
  }

  // ── Render decision ────────────────────────────────────────────────────────

  function resetVerdict() {
    const banner = document.getElementById('pg-verdict-banner');
    if (banner) { banner.className = 'pg-verdict-banner idle'; }
    const vIcon  = document.getElementById('pg-verdict-icon');
    const vLabel = document.getElementById('pg-verdict-label');
    const vTrust = document.getElementById('pg-verdict-trust');
    const vElap  = document.getElementById('pg-verdict-elapsed');
    if (vIcon)  vIcon.textContent  = '◌';
    if (vLabel) vLabel.textContent = 'EVALUATING…';
    if (vTrust) vTrust.textContent = '';
    if (vElap)  vElap.textContent  = '';
    ['pg-s-total','pg-s-pass','pg-s-fail','pg-s-workers'].forEach(id => {
      const e = document.getElementById(id); if (e) e.textContent = '—';
    });
    const dc = document.getElementById('pg-decision-digest'); if (dc) dc.textContent = '—';
    const rc = document.getElementById('pg-reason-chips');
    if (rc) rc.innerHTML = '<span class="pg-reason-chip">—</span>';
  }

  function renderDecision(data, mutationId, trustMode) {
    const dec = data.decision || {};
    const axisResults = dec.axis_results || [];
    const approved = !!dec.approved;

    // Verdict banner
    const banner = document.getElementById('pg-verdict-banner');
    if (banner) banner.className = 'pg-verdict-banner ' + (approved ? 'approved' : 'rejected');
    const vIcon  = document.getElementById('pg-verdict-icon');
    const vLabel = document.getElementById('pg-verdict-label');
    const vTrust = document.getElementById('pg-verdict-trust');
    const vElap  = document.getElementById('pg-verdict-elapsed');
    if (vIcon)  vIcon.textContent  = approved ? '✓' : '✕';
    if (vLabel) vLabel.textContent = approved ? 'APPROVED' : 'REJECTED';
    if (vTrust) vTrust.textContent = 'trust_mode: ' + (dec.trust_mode || trustMode) +
      (dec.human_override ? ' · human_override: TRUE' : '');
    if (vElap)  vElap.textContent  = 'wall_time: ' + data.wall_elapsed_ms + 'ms · ' +
      data.axis_count + ' axes · ' + data.max_workers + ' workers';

    // Summary stats
    const passCount = axisResults.filter(r => r.ok).length;
    const failCount = axisResults.filter(r => !r.ok).length;
    const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    set('pg-s-total',   axisResults.length);
    set('pg-s-pass',    passCount);
    set('pg-s-fail',    failCount);
    set('pg-s-workers', data.max_workers);

    // Decision digest
    const dc = document.getElementById('pg-decision-digest');
    if (dc) dc.textContent = dec.decision_id || '—';

    // Reason codes
    const rc = document.getElementById('pg-reason-chips');
    if (rc) {
      const codes = dec.reason_codes || [];
      if (!codes.length) {
        rc.innerHTML = '<span class="pg-reason-chip pass">no_failures</span>';
      } else {
        rc.innerHTML = codes.map(c =>
          `<span class="pg-reason-chip fail">${c}</span>`
        ).join('');
      }
    }

    // Swimlanes
    const board = document.getElementById('pg-swimlane-board');
    if (board) {
      board.innerHTML = '';
      // Sort visually: failures first, then passes
      const sorted = [...axisResults].sort((a, b) => {
        if (a.ok !== b.ok) return a.ok ? 1 : -1;
        return (a.axis + a.rule_id).localeCompare(b.axis + b.rule_id);
      });
      sorted.forEach(ar => {
        board.appendChild(buildSwimLane(
          ar.axis, ar.rule_id,
          ar.ok ? 'pass' : 'fail',
          ar.reason,
          ar.duration_ms != null ? ar.duration_ms : null,
        ));
      });
    }

    // Timing waterfall
    renderWaterfall(axisResults, data.wall_elapsed_ms);
  }

  function renderWaterfall(axisResults, wallMs) {
    const card    = document.getElementById('pg-waterfall-card');
    const wf      = document.getElementById('pg-waterfall');
    const wfSt    = document.getElementById('pg-waterfall-status');
    if (!card || !wf) return;

    card.style.display = '';
    wf.innerHTML = '';

    const maxMs = Math.max(1, wallMs || 1);
    const sorted = [...axisResults].sort((a, b) => (b.duration_ms || 0) - (a.duration_ms || 0));

    sorted.forEach(ar => {
      const ms = ar.duration_ms || 0;
      const pct = Math.min(100, (ms / maxMs) * 100);

      const row = mk('div', 'pg-waterfall-row');
      const label = mk('span', 'pg-waterfall-label', ar.axis + ':' + ar.rule_id);
      label.title = ar.axis + ':' + ar.rule_id;
      row.appendChild(label);

      const track = mk('div', 'pg-waterfall-track');
      const fill  = mk('div', 'pg-waterfall-fill');
      fill.style.width = pct + '%';
      fill.style.background = ar.ok ? axisColor(ar.axis) : 'var(--danger)';
      track.appendChild(fill);
      row.appendChild(track);

      row.appendChild(mk('span', 'pg-waterfall-ms', ms.toFixed(2) + 'ms'));
      wf.appendChild(row);
    });

    if (wfSt) setStatus(wfSt, 'wall_elapsed: ' + wallMs + 'ms · axes evaluated in parallel', 'ok');
  }

  // ── Toggle ─────────────────────────────────────────────────────────────────

  function setupToggle() {
    const btn  = document.getElementById('pg-toggle-btn');
    const body = document.getElementById('pg-panel-body');
    if (!btn || !body) return;
    let collapsed = false;
    const toggle = (e) => {
      if (e && e.target === btn) e.stopPropagation();
      collapsed = !collapsed;
      body.classList.toggle('pg-collapsed', collapsed);
      btn.textContent = collapsed ? 'show' : 'hide';
    };
    btn.addEventListener('click', toggle);
    document.getElementById('pg-section-head')?.addEventListener('click', (e) => {
      if (e.target === btn) return;
      toggle(e);
    });
  }

  // ── Wire events ────────────────────────────────────────────────────────────

  function wireEvents() {
    document.getElementById('pg-run-btn')?.addEventListener('click', runGate);
    document.getElementById('pg-add-btn')?.addEventListener('click', addAxis);
    document.getElementById('pg-clear-axes')?.addEventListener('click', () => {
      state.currentAxes = [];
      renderAxisList();
      updateSwimlanePlaceholders();
    });
    // Enter on mutation-id triggers run
    document.getElementById('pg-mutation-id')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') runGate();
    });
  }

  // ── Mount ──────────────────────────────────────────────────────────────────

  function mount() {
    if (document.getElementById(SECTION_ID)) return;
    const layout = document.querySelector('.layout');
    if (!layout) return;

    const div = document.createElement('div');
    div.innerHTML = buildHTML();
    const inserted = div.firstElementChild;

    const scripts = layout.querySelectorAll('script');
    if (scripts.length) layout.insertBefore(inserted, scripts[0]);
    else layout.appendChild(inserted);

    setupToggle();
    wireEvents();
    buildPresets();
    loadProbeLibrary();

    // Set default mutation ID
    const midEl = document.getElementById('pg-mutation-id');
    if (midEl) midEl.placeholder = 'mut_pg_' + String(state.mutationCounter).padStart(3, '0');
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  function init() {
    injectStyles();
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
    else mount();
  }

  init();

})();
