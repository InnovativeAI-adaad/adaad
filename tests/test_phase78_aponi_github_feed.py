# SPDX-License-Identifier: Apache-2.0
"""Phase 78 — Aponi GitHub Feed panel tests.

Verifies the HTML structure, nav registration, and JS function presence
for the GitHub Feed panel injected in Phase 78.
"""
from __future__ import annotations
import re
from pathlib import Path

DASHBOARD = Path("ui/aponi_dashboard.py").read_text()


class TestAponiGithubFeedPanel:
    def test_nav_button_present(self):
        assert 'data-view="github"' in DASHBOARD

    def test_view_div_present(self):
        assert 'id="view-github"' in DASHBOARD

    def test_feed_section_present(self):
        assert 'id="card-github-feed"' in DASHBOARD

    def test_feed_list_div_present(self):
        assert 'id="githubFeedList"' in DASHBOARD

    def test_feed_refresh_button_present(self):
        assert 'id="githubFeedRefresh"' in DASHBOARD

    def test_github_feed_css_present(self):
        assert '.github-feed-list' in DASHBOARD
        assert '.feed-event-card' in DASHBOARD

    def test_load_github_feed_function_present(self):
        assert 'async function loadGithubFeed' in DASHBOARD

    def test_render_feed_card_function_present(self):
        assert 'function renderGithubFeedCard' in DASHBOARD

    def test_setup_github_feed_panel_called(self):
        assert 'setupGithubFeedPanel()' in DASHBOARD

    def test_event_type_classifiers_present(self):
        assert 'classifyFeedEvent' in DASHBOARD
        assert "'push'" in DASHBOARD
        assert "'pr'" in DASHBOARD
        assert "'ci'" in DASHBOARD

    def test_governance_bridge_fallback_present(self):
        assert 'external-events' in DASHBOARD

    def test_aria_roles_present(self):
        assert 'role="tabpanel"' in DASHBOARD
        assert 'role="list"' in DASHBOARD
        assert 'aria-live="polite"' in DASHBOARD


class TestDocSyncScript:
    def test_verify_script_exists(self):
        assert Path("scripts/verify_doc_sync.py").exists()

    def test_verify_passes_on_clean_repo(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "scripts/verify_doc_sync.py"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_workflow_file_exists(self):
        assert Path(".github/workflows/docs-autosync.yml").exists()

    def test_workflow_has_version_update_step(self):
        wf = Path(".github/workflows/docs-autosync.yml").read_text()
        assert "infobox" in wf.lower() or "README" in wf
        assert "verify_doc_sync" in wf
        assert "[skip ci]" in wf
