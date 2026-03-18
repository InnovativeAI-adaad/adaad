# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path


def test_dork_system_prompt_contains_live_runtime_state_section() -> None:
    html = Path('ui/developer/ADAADdev/whaledic.html').read_text(encoding='utf-8')
    assert 'function constructDorkPrompt(basePrompt, liveState)' in html
    assert '## LIVE RUNTIME STATE' in html
    assert 'const liveState = await fetchRuntimeState();' in html
    assert 'activeSystemPrompt = constructDorkPrompt(BASE_SYSTEM_PROMPT, liveState);' in html
