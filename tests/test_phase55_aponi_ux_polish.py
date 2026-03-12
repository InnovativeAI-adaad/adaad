# SPDX-License-Identifier: Apache-2.0
"""
Phase 55 tests — Aponi UX Polish

Verifies:
- Toast system markup + CSS present
- Countdown bar markup present
- Keyboard help overlay + shortcut table present
- Log filter input present in HTML
- Freshness helpers in script
- All new functions present (toast, startCountdown, freshTag, bindKeyboard)
- 6-tab navigation (incl. governance, memory) wired in keyboard handler
- Help button present in header

Test IDs: T55-P01..P10
"""

from __future__ import annotations
import pytest


@pytest.fixture(scope="module")
def html():
    with open("ui/aponi/index.html", encoding="utf-8") as f:
        return f.read()


class TestAponiUXPolishT55P:

    def test_T55_P01_toast_stack_div_present(self, html):
        """T55-P01: #toastStack div is in HTML."""
        assert 'id="toastStack"' in html

    def test_T55_P02_toast_css_present(self, html):
        """T55-P02: .toast CSS class defined."""
        assert ".toast{" in html or ".toast {" in html

    def test_T55_P03_toast_function_defined(self, html):
        """T55-P03: toast() JS function defined."""
        assert "function toast(" in html

    def test_T55_P04_countdown_bar_present(self, html):
        """T55-P04: #countdownBar and #countdownFill present."""
        assert 'id="countdownBar"' in html
        assert 'id="countdownFill"' in html

    def test_T55_P05_countdown_function_defined(self, html):
        """T55-P05: startCountdown() JS function defined."""
        assert "function startCountdown(" in html

    def test_T55_P06_keyboard_help_overlay_present(self, html):
        """T55-P06: #kbdHelp overlay and help button present."""
        assert 'id="kbdHelp"' in html
        assert 'id="btnKbdHelp"' in html
        assert "Keyboard Shortcuts" in html

    def test_T55_P07_keyboard_shortcuts_all_six_tabs(self, html):
        """T55-P07: bindKeyboard references all 6 tab names."""
        tabs = ["overview", "agents", "protocol", "governance", "memory", "logs"]
        for tab in tabs:
            assert f'"{tab}"' in html or f"'{tab}'" in html, f"Tab '{tab}' missing"

    def test_T55_P08_log_filter_input_present(self, html):
        """T55-P08: log-filter CSS class and input present."""
        assert "log-filter" in html
        assert "logFilter" in html

    def test_T55_P09_freshness_helper_defined(self, html):
        """T55-P09: freshTag() function defined."""
        assert "function freshTag(" in html

    def test_T55_P10_bind_keyboard_called_at_boot(self, html):
        """T55-P10: bindKeyboard() is called in boot sequence."""
        assert "bindKeyboard();" in html
