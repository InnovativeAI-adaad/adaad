const form = document.querySelector('#proposal-form');
const responseElement = document.querySelector('#response');
const metadataInput = document.querySelector('#metadata');
const agentInput = document.querySelector('#agent_id');
const targetInput = document.querySelector('#target_path');
const pythonInput = document.querySelector('#python_content');

let lintTimer = null;

function showResponse(payload) {
  responseElement.textContent = JSON.stringify(payload, null, 2);
}

function parseMetadata(rawText) {
  try {
    const parsed = JSON.parse(rawText || '{}');
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      return {
        ok: false,
        error: 'invalid_metadata_json',
        detail: 'Metadata must be a JSON object (for example: {"change_reason":"safety hardening"}).',
      };
    }
    return { ok: true, value: parsed };
  } catch (error) {
    return {
      ok: false,
      error: 'invalid_metadata_json',
      detail: `Metadata JSON parse failed: ${String(error)}`,
    };
  }
}

function buildProposalPayload(formData) {
  const agentId = (formData.get('agent_id') || '').toString().trim();
  const targetPath = (formData.get('target_path') || '').toString().trim();
  const pythonContent = (formData.get('python_content') || '').toString();
  const metadataResult = parseMetadata((formData.get('metadata') || '').toString());
  if (!metadataResult.ok) {
    return metadataResult;
  }
  const signature = (formData.get('signature') || 'unsigned-local-draft').toString().trim() || 'unsigned-local-draft';
  const nonce = (formData.get('nonce') || 'draft-nonce').toString().trim() || 'draft-nonce';

  const op = {
    op: 'replace_file_content',
    language: 'python',
    content: pythonContent,
    metadata: metadataResult.value,
  };

  return {
    ok: true,
    value: {
      agent_id: agentId,
      generation_ts: new Date().toISOString(),
      intent: 'governed_mutation_proposal_authoring',
      ops: [op],
      targets: [
        {
          agent_id: agentId,
          path: targetPath,
          target_type: 'python_module',
          ops: [op],
        },
      ],
      signature,
      nonce,
    },
  };
}

async function postToGovernedEndpoint(payload) {
  const endpoints = ['/api/mutations/proposals', '/mutation/propose'];
  let lastError = null;

  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const body = await response.json().catch(() => ({}));
      if (response.ok) {
        return { endpoint, status: response.status, body };
      }
      lastError = { endpoint, status: response.status, body };
    } catch (error) {
      lastError = { endpoint, error: String(error) };
    }
  }

  throw new Error(JSON.stringify(lastError, null, 2));
}

async function fetchLintPreview() {
  const metadataText = (metadataInput?.value || '').trim() || '{}';
  const metadataResult = parseMetadata(metadataText);
  if (!metadataResult.ok) {
    showResponse({ phase: 'lint_preview_invalid', metadata: metadataResult });
    return;
  }

  const params = new URLSearchParams({
    agent_id: (agentInput?.value || '').trim(),
    target_path: (targetInput?.value || '').trim(),
    python_content: pythonInput?.value || '',
    metadata: JSON.stringify(metadataResult.value),
  });

  try {
    const response = await fetch(`/api/lint/preview?${params.toString()}`);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      showResponse({ phase: 'lint_preview_error', status: response.status, body });
      return;
    }
    showResponse({ phase: 'lint_preview', preview: body });
  } catch (error) {
    showResponse({ phase: 'lint_preview_error', error: String(error) });
  }
}

function scheduleLintPreview() {
  if (lintTimer) {
    window.clearTimeout(lintTimer);
  }
  lintTimer = window.setTimeout(() => {
    fetchLintPreview();
  }, 800);
}

for (const field of [metadataInput, agentInput, targetInput, pythonInput]) {
  field?.addEventListener('input', scheduleLintPreview);
}

form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(form);

  try {
    const payloadResult = buildProposalPayload(formData);
    if (!payloadResult.ok) {
      showResponse({ phase: 'validation_error', ...payloadResult });
      return;
    }

    showResponse({ phase: 'submitting', payload: payloadResult.value });
    const result = await postToGovernedEndpoint(payloadResult.value);
    showResponse({ phase: 'submitted', result });
  } catch (error) {
    showResponse({ phase: 'error', message: String(error) });
  }
});
