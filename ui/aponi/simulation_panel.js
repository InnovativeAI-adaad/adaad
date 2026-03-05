// SPDX-License-Identifier: Apache-2.0
// Aponi Simulation Panel — ADAAD-9 D3 (Phase 5)
// Wires POST /simulation/run and GET /simulation/results/{run_id}
// into the proposal editor workflow as an inline "Simulate against history" panel.
// Epic 2 (ADAAD-8) endpoints consumed here; panel is read-only from authority perspective.
(function () {
  'use strict';

  const PANEL_ID = 'proposalSimulationPanel';
  const RUN_BTN_ID = 'simulationRunBtn';
  const DSL_INPUT_ID = 'simulationDslInput';
  const EPOCH_RANGE_ID = 'simulationEpochRange';
  const RUN_OUTPUT_ID = 'simulationRun';
  const RESULTS_OUTPUT_ID = 'simulationResults';
  const STATUS_ID = 'simulationStatus';
  const CONTEXT_URL = '/simulation/context';
  const RUN_URL = '/simulation/run';
  const FETCH_TIMEOUT_MS = 12000;

  function safeText(v) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'object') {
      try { return JSON.stringify(v, null, 2); } catch (_) { return '[object]'; }
    }
    return String(v);
  }

  function setStatus(message, kind) {
    const s = document.getElementById(STATUS_ID);
    if (!s) return;
    s.textContent = message;
    s.className = 'sim-status sim-status--' + (kind || 'idle');
  }

  function setOutput(id, content) {
    const el = document.getElementById(id);
    if (!el) return;
    if (typeof content === 'string') {
      el.textContent = content;
    } else {
      el.textContent = JSON.stringify(content, null, 2);
    }
  }

  async function fetchWithTimeout(url, options) {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const resp = await fetch(url, { ...options, signal: controller.signal, cache: 'no-store' });
      clearTimeout(tid);
      return resp;
    } catch (err) {
      clearTimeout(tid);
      throw err;
    }
  }

  async function loadSimulationContext() {
    try {
      const resp = await fetchWithTimeout(CONTEXT_URL, {});
      if (!resp.ok) return null;
      return await resp.json();
    } catch (_) {
      return null;
    }
  }

  async function runSimulation(dslText, epochRange) {
    const resp = await fetchWithTimeout(RUN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dsl_text: dslText,
        constraints: [],
        epoch_range: epochRange,
      }),
    });
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(`${resp.status}: ${body.error || body.detail || resp.statusText}`);
    }
    return body;
  }

  async function fetchResults(runId) {
    const resp = await fetchWithTimeout(`/simulation/results/${encodeURIComponent(runId)}`, {});
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(`${resp.status}: ${body.error || body.detail || resp.statusText}`);
    }
    return body;
  }

  function renderComparativeOutcomes(outcomes) {
    if (!outcomes || typeof outcomes !== 'object') return '(no comparative outcomes)';
    const lines = ['Comparative outcomes:'];
    const actual = outcomes.actual || {};
    const simulated = outcomes.simulated || {};
    const delta = outcomes.delta || {};
    const keys = new Set([...Object.keys(actual), ...Object.keys(simulated)]);
    keys.forEach((k) => {
      const a = safeText(actual[k]);
      const s = safeText(simulated[k]);
      const d = delta[k] !== undefined ? ` (Δ ${safeText(delta[k])})` : '';
      lines.push(`  ${k}: actual=${a} → simulated=${s}${d}`);
    });
    return lines.join('\n');
  }

  async function init() {
    const panel = document.getElementById(PANEL_ID);
    const runBtn = document.getElementById(RUN_BTN_ID);
    const dslInput = document.getElementById(DSL_INPUT_ID);
    const epochRangeEl = document.getElementById(EPOCH_RANGE_ID);

    if (!panel || !runBtn || !dslInput) return;

    // Pre-populate default epoch range from simulation context
    const ctx = await loadSimulationContext();
    const maxRange = (ctx && ctx.max_epoch_range) || 10;
    const defaultConstraints = (ctx && ctx.default_constraints) || [];
    if (epochRangeEl && !epochRangeEl.value) {
      epochRangeEl.value = String(Math.min(10, maxRange));
    }
    if (dslInput && !dslInput.value && defaultConstraints.length) {
      // Render default constraints as DSL hint
      dslInput.placeholder = defaultConstraints.map((c) => `${c.type}(…)`).join('; ');
    }
    setStatus(`Ready · max epoch range: ${maxRange}`, 'idle');

    runBtn.addEventListener('click', async () => {
      const dslText = (dslInput.value || '').trim();
      const epochCount = Math.max(1, Math.min(maxRange, parseInt(epochRangeEl?.value || '10', 10) || 10));
      setStatus('Running simulation…', 'loading');
      setOutput(RUN_OUTPUT_ID, '…');
      setOutput(RESULTS_OUTPUT_ID, '');

      try {
        const runResult = await runSimulation(dslText, { start: 1, end: epochCount });
        setOutput(RUN_OUTPUT_ID, renderComparativeOutcomes(runResult.comparative_outcomes));
        setStatus(`Run complete · run_id: ${runResult.run_id}`, 'ok');

        if (runResult.run_id) {
          const results = await fetchResults(runResult.run_id);
          const provenance = results.provenance || {};
          setOutput(
            RESULTS_OUTPUT_ID,
            `Provenance: deterministic=${provenance.deterministic} replay_seed=${safeText(provenance.replay_seed)}\n` +
            renderComparativeOutcomes(results.comparative_outcomes)
          );
        }
      } catch (err) {
        setStatus(`Error: ${err.message}`, 'error');
        setOutput(RUN_OUTPUT_ID, String(err));
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
