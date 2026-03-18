# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path


def test_whaledic_nav_link() -> None:
    html = Path('ui/aponi/index.html').read_text(encoding='utf-8')
    assert '/ui/developer/ADAADdev/whaledic.html' in html
    assert 'Whale.Dic' in html
    assert 'ADAADinside™' in html
