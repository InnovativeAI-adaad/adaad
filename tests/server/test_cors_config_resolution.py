# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from server import _resolve_cors_settings


def test_cors_explicit_allowlist_only_disables_regex_fallback() -> None:
    origins, regex = _resolve_cors_settings(
        {
            "ADAAD_CORS_ORIGINS": "https://example.com, https://admin.example.com",
        }
    )

    assert origins == ["https://example.com", "https://admin.example.com"]
    assert regex is None


def test_cors_regex_enabled_mode_with_explicit_regex() -> None:
    origins, regex = _resolve_cors_settings(
        {
            "ADAAD_CORS_ORIGINS": "https://example.com",
            "ADAAD_CORS_ORIGIN_REGEX": r"https://.*\\.example\\.com",
        }
    )

    assert origins == ["https://example.com"]
    assert regex == r"https://.*\\.example\\.com"


def test_cors_default_dev_mode_when_no_env_vars_set() -> None:
    origins, regex = _resolve_cors_settings({})

    assert origins == ["http://localhost", "http://127.0.0.1"]
    assert regex == r"http://(localhost|127\.0\.0\.1)(:\d+)?"
