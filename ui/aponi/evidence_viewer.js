// SPDX-License-Identifier: Apache-2.0
// Aponi Evidence Viewer — ADAAD-9 D4
// Fetches and renders evidence bundles from GET /evidence/{bundle_id}.
// Read-only; never initiates mutations or execution paths.
(function () {
  'use strict';

  const FETCH_TIMEOUT_MS = 8000;
  const EVIDENCE_SECTION_ID = 'evidence-viewer-section';
  const BUNDLE_INPUT_ID = 'evidence-bundle-id';
  const FETCH_BTN_ID = 'evidence-fetch-btn';
  const VIEWER_OUTPUT_ID = 'evidence-viewer-output';
  const STATUS_ID = 'evidence-viewer-status';

  function safeText(v) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'object') {
      try { return JSON.stringify(v, null, 2); } catch (_) { return '[object]'; }
    }
    return String(v);
  }

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (k === 'className') node.className = v;
      else if (k === 'textContent') node.textContent = safeText(v);
      else node.setAttribute(k, v);
    });
    (children || []).forEach((c) => {
      if (c instanceof Node) node.appendChild(c);
      else if (typeof c === 'string') node.appendChild(document.createTextNode(c));
    });
    return node;
  }

  function statusEl(message, kind) {
    const s = document.getElementById(STATUS_ID);
    if (!s) return;
    s.textContent = message;
    s.className = 'ev-status ev-status--' + (kind || 'idle');
  }

  function clearOutput() {
    const out = document.getElementById(VIEWER_OUTPUT_ID);
    if (out) out.innerHTML = '';
  }

  function provenanceRow(label, value, highlight) {
    return el('div', { className: 'ev-row' + (highlight ? ' ev-row--highlight' : '') }, [
      el('span', { className: 'ev-label', textContent: label }),
      el('span', { className: 'ev-value', textContent: value }),
    ]);
  }

  function sectionHead(title) {
    return el('div', { className: 'ev-section-head' }, [
      el('span', { className: 'ev-section-title', textContent: title }),
    ]);
  }

  function renderProvenancePanel(bundle) {
    return el('div', { className: 'ev-panel ev-panel--provenance' }, [
      sectionHead('Provenance'),
      provenanceRow('bundle_id', bundle.bundle_id, true),
      provenanceRow('constitution_version', bundle.constitution_version, true),
      provenanceRow('scoring_algorithm_version', bundle.scoring_algorithm_version, true),
      provenanceRow('governor_version', bundle.governor_version),
      provenanceRow('fitness_weights_hash', bundle.fitness_weights_hash),
      provenanceRow('goal_graph_hash', bundle.goal_graph_hash),
    ]);
  }

  function renderExportPanel(bundle) {
    const meta = bundle.export_metadata || {};
    const signer = meta.signer || {};
    return el('div', { className: 'ev-panel' }, [
      sectionHead('Export Metadata'),
      provenanceRow('digest', meta.digest),
      provenanceRow('immutable', String(meta.immutable)),
      provenanceRow('access_scope', meta.access_scope),
      provenanceRow('retention_days', meta.retention_days),
      provenanceRow('signer.key_id', signer.key_id),
      provenanceRow('signer.algorithm', signer.algorithm),
      provenanceRow('signed_digest', signer.signed_digest),
    ]);
  }

  function renderRiskPanel(bundle) {
    const r = bundle.risk_summaries || {};
    const high = (r.high_risk_bundle_count || 0);
    return el('div', { className: 'ev-panel' + (high > 0 ? ' ev-panel--warn' : '') }, [
      sectionHead('Risk Summaries'),
      provenanceRow('bundle_count', r.bundle_count),
      provenanceRow('sandbox_evidence_count', r.sandbox_evidence_count),
      provenanceRow('replay_proof_count', r.replay_proof_count),
      provenanceRow('high_risk_bundle_count', r.high_risk_bundle_count, high > 0),
    ]);
  }

  function renderSandboxPanel(bundle) {
    const s = bundle.sandbox_snapshot || {};
    return el('div', { className: 'ev-panel' }, [
      sectionHead('Sandbox Snapshot'),
      provenanceRow('seccomp_available', String(s.seccomp_available)),
      provenanceRow('namespace_isolation', String(s.namespace_isolation_available)),
      provenanceRow(
        'workspace_prefixes',
        Array.isArray(s.workspace_prefixes) ? s.workspace_prefixes.join(', ') : '—'
      ),
    ]);
  }

  function renderReplayProofs(bundle) {
    const proofs = Array.isArray(bundle.replay_proofs) ? bundle.replay_proofs : [];
    if (!proofs.length) return null;
    const rows = proofs.map((p) =>
      el('div', { className: 'ev-proof-row' }, [
        el('span', { className: 'ev-label', textContent: p.epoch_id }),
        el('span', { className: 'ev-value ev-mono', textContent: p.canonical_digest }),
        el('span', { className: 'ev-count', textContent: `${p.event_count} events` }),
      ])
    );
    return el('div', { className: 'ev-panel' }, [sectionHead('Replay Proofs'), ...rows]);
  }

  function renderBundle(bundle, outputEl) {
    outputEl.innerHTML = '';
    outputEl.appendChild(renderProvenancePanel(bundle));
    outputEl.appendChild(renderRiskPanel(bundle));
    outputEl.appendChild(renderExportPanel(bundle));
    outputEl.appendChild(renderSandboxPanel(bundle));
    const proofs = renderReplayProofs(bundle);
    if (proofs) outputEl.appendChild(proofs);
  }

  async function fetchBundle(bundleId) {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const resp = await fetch(`/evidence/${encodeURIComponent(bundleId)}`, {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
        signal: controller.signal,
      });
      clearTimeout(tid);
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(`HTTP ${resp.status}: ${body.detail || body.error || resp.statusText}`);
      }
      return await resp.json();
    } catch (err) {
      clearTimeout(tid);
      throw err;
    }
  }

  function init() {
    const fetchBtn = document.getElementById(FETCH_BTN_ID);
    const bundleInput = document.getElementById(BUNDLE_INPUT_ID);
    const outputEl = document.getElementById(VIEWER_OUTPUT_ID);

    if (!fetchBtn || !bundleInput || !outputEl) return;

    fetchBtn.addEventListener('click', async () => {
      const bundleId = (bundleInput.value || '').trim();
      if (!bundleId) {
        statusEl('Bundle ID required.', 'error');
        return;
      }
      statusEl('Fetching…', 'loading');
      clearOutput();
      try {
        const bundle = await fetchBundle(bundleId);
        renderBundle(bundle, outputEl);
        statusEl(`Loaded: ${bundleId}`, 'ok');
      } catch (err) {
        statusEl(`Error: ${err.message}`, 'error');
        outputEl.textContent = String(err);
      }
    });

    bundleInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') fetchBtn.click();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
