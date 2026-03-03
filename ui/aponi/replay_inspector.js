(function () {
  'use strict';

  const DIFF_TIMEOUT_MS = 5000;

  function safeText(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'object') {
      try { return JSON.stringify(value); } catch (_) { return '[unserializable object]'; }
    }
    return String(value);
  }

  function clear(node) {
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function make(tag, options) {
    const el = document.createElement(tag);
    const opts = options || {};
    if (opts.className) el.className = opts.className;
    if (opts.text !== undefined) el.textContent = safeText(opts.text);
    if (opts.attrs && typeof opts.attrs === 'object') {
      Object.entries(opts.attrs).forEach(([k, v]) => el.setAttribute(k, safeText(v)));
    }
    if (Array.isArray(opts.children)) {
      opts.children.forEach((child) => {
        if (child instanceof Node) el.appendChild(child);
      });
    }
    return el;
  }

  async function fetchJsonWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, { cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return await response.json();
    } finally {
      clearTimeout(timeoutId);
    }
  }

  function summarizeEpochs(divergencePayload) {
    const epochs = [];
    const seen = new Set();
    const latestEvents = Array.isArray(divergencePayload && divergencePayload.latest_events) ? divergencePayload.latest_events : [];
    latestEvents.forEach((entry) => {
      const payload = entry && typeof entry.payload === 'object' ? entry.payload : {};
      const candidate = String(payload.epoch_id || entry.epoch_id || entry.epoch || '').trim();
      if (!candidate || seen.has(candidate)) return;
      seen.add(candidate);
      epochs.push(candidate);
    });
    const proofStatus = divergencePayload && typeof divergencePayload.proof_status === 'object' ? divergencePayload.proof_status : {};
    Object.keys(proofStatus).forEach((epochId) => {
      const normalized = String(epochId || '').trim();
      if (!normalized || seen.has(normalized)) return;
      seen.add(normalized);
      epochs.push(normalized);
    });
    return epochs.slice(-10).reverse();
  }

  function renderDrift(container, diffPayload) {
    const semantic = diffPayload && typeof diffPayload.semantic_drift === 'object' ? diffPayload.semantic_drift : {};
    const classCounts = semantic.class_counts && typeof semantic.class_counts === 'object' ? semantic.class_counts : {};
    const perKey = semantic.per_key && typeof semantic.per_key === 'object' ? semantic.per_key : {};

    const labels = Object.entries(classCounts)
      .filter(([, count]) => Number(count || 0) > 0)
      .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0));
    if (!labels.length) {
      container.appendChild(make('div', { className: 'replay-note', text: 'No semantic divergence detected for this epoch.' }));
      return;
    }

    const chips = make('div', { className: 'replay-chip-row' });
    labels.forEach(([name, count]) => {
      chips.appendChild(make('span', { className: 'replay-chip replay-chip-alert', text: name + ': ' + count }));
    });
    container.appendChild(chips);

    const firstKeys = Object.entries(perKey).slice(0, 10);
    if (firstKeys.length) {
      const details = make('details');
      details.appendChild(make('summary', { text: 'Divergence keys' }));
      const list = make('div', { className: 'replay-note' });
      firstKeys.forEach(([key, klass]) => {
        list.appendChild(make('div', { text: key + ' → ' + klass }));
      });
      details.appendChild(list);
      container.appendChild(details);
    }
  }

  function renderMutationDrilldown(container, diffPayload) {
    const lineage = diffPayload && typeof diffPayload.lineage_chain === 'object' ? diffPayload.lineage_chain : {};
    const mutations = Array.isArray(lineage.mutations) ? lineage.mutations : [];
    if (!mutations.length) {
      container.appendChild(make('div', { className: 'replay-note', text: 'No lineage mutation chain available.' }));
      return;
    }

    const title = make('div', { className: 'replay-note', text: 'Mutation lineage drill-down (tap mutation id):' });
    container.appendChild(title);

    const chain = make('div', { className: 'replay-chip-row' });
    const detail = make('pre', { className: 'replay-detail', text: 'Select a mutation to inspect certified ancestry.' });
    const selectMutation = (mutation) => {
      const ancestry = Array.isArray(mutation.ancestor_chain) ? mutation.ancestor_chain : [];
      detail.textContent = JSON.stringify({
        mutation_id: mutation.mutation_id || '',
        parent_mutation_id: mutation.parent_mutation_id || '',
        ancestor_chain: ancestry,
        certified_signature: mutation.certified_signature || '',
      }, null, 2);
    };

    mutations.forEach((mutation, index) => {
      const button = make('button', {
        className: 'replay-chip replay-chip-link',
        text: mutation.mutation_id || ('mutation-' + index),
        attrs: { type: 'button' },
      });
      button.addEventListener('click', () => selectMutation(mutation));
      chain.appendChild(button);
      if (index === mutations.length - 1) button.classList.add('replay-chip-selected');
    });
    container.appendChild(chain);

    selectMutation(mutations[mutations.length - 1]);
    container.appendChild(detail);
  }

  function renderDiff(host, diffPayload) {
    const body = host.querySelector('[data-replay-body]');
    if (!body) return;
    clear(body);

    if (!diffPayload || diffPayload.ok !== true) {
      body.appendChild(make('div', { className: 'replay-error', text: 'Unable to load replay diff for selected epoch.' }));
      return;
    }

    const fp = make('div', { className: 'replay-note', text: 'Fingerprints: ' + safeText(diffPayload.initial_fingerprint) + ' → ' + safeText(diffPayload.final_fingerprint) });
    body.appendChild(fp);
    renderDrift(body, diffPayload);
    renderMutationDrilldown(body, diffPayload);
  }

  function renderEpochNav(host, epochs, selectedEpochId, onSelect) {
    const nav = host.querySelector('[data-replay-nav]');
    if (!nav) return;
    clear(nav);
    if (!epochs.length) {
      nav.appendChild(make('div', { className: 'replay-note', text: 'No recent epochs with replay evidence.' }));
      return;
    }
    epochs.forEach((epochId) => {
      const btn = make('button', {
        className: 'replay-chip replay-chip-link' + (epochId === selectedEpochId ? ' replay-chip-selected' : ''),
        text: epochId,
        attrs: { type: 'button' },
      });
      btn.addEventListener('click', () => onSelect(epochId));
      nav.appendChild(btn);
    });
  }

  function setStatus(host, message, kind) {
    const status = host.querySelector('[data-replay-status]');
    if (!status) return;
    status.className = 'replay-status ' + (kind || '');
    status.textContent = message;
  }

  function createInspector(hostId) {
    const host = document.getElementById(hostId);
    if (!host) return null;

    const state = { epochs: [], selectedEpochId: '' };

    async function loadDiff(epochId) {
      setStatus(host, 'Loading replay diff…', 'loading');
      try {
        const diff = await fetchJsonWithTimeout('/replay/diff?epoch_id=' + encodeURIComponent(epochId), DIFF_TIMEOUT_MS);
        renderDiff(host, diff);
        setStatus(host, 'Loaded replay diff for ' + epochId + '.', 'ok');
      } catch (err) {
        renderDiff(host, null);
        setStatus(host, 'Replay diff load failed: ' + err, 'error');
      }
    }

    async function refresh(divergencePayload) {
      setStatus(host, 'Loading replay inspector…', 'loading');
      const payload = divergencePayload || await fetchJsonWithTimeout('/replay/divergence', DIFF_TIMEOUT_MS);
      state.epochs = summarizeEpochs(payload);
      if (!state.selectedEpochId || !state.epochs.includes(state.selectedEpochId)) {
        state.selectedEpochId = state.epochs[0] || '';
      }
      const handleSelectEpoch = async (nextEpochId) => {
        state.selectedEpochId = nextEpochId;
        renderEpochNav(host, state.epochs, state.selectedEpochId, handleSelectEpoch);
        await loadDiff(nextEpochId);
      };
      renderEpochNav(host, state.epochs, state.selectedEpochId, handleSelectEpoch);
      if (!state.selectedEpochId) {
        renderDiff(host, null);
        setStatus(host, 'No replay epoch available in divergence window.', 'error');
        return;
      }
      await loadDiff(state.selectedEpochId);
    }

    return { refresh };
  }

  window.AponiReplayInspector = { createInspector };
})();
