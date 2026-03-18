# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path


def test_rate_gate_persists_across_reload_with_session_storage_key() -> None:
    html = Path('ui/developer/ADAADdev/whaledic.html').read_text(encoding='utf-8')
    assert "const RATE_KEY = 'whaledic_rate_timestamps';" in html
    assert 'requestTimestamps = readSession(RATE_KEY, []);' in html
    assert 'writeSession(RATE_KEY, requestTimestamps);' in html


def test_testmode_intercepts_anthropic_fetch_and_mock_data_bus_event_present() -> None:
    html = Path('ui/developer/ADAADdev/whaledic.html').read_text(encoding='utf-8')
    assert "document.body?.dataset?.testmode === 'true'" in html
    assert "busEvent('testmode', 'anthropic_intercepted');" in html
    assert "busEvent('mock_data', route);" in html
