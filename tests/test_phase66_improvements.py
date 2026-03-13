# SPDX-License-Identifier: Apache-2.0
"""
Module: test_phase66_improvements
Purpose: Validate Phase 66 hardening improvements:
  - C-04: LineageLedgerV2 O(n) append fix — no full re-scan per write
  - H-02: assert_governance_signing_key_boot fail-closed in non-dev envs
  - H-03: _validate_write_allowlist rejects non-absolute and traversal paths
  - H-06: ProposalRateLimiter token-bucket enforcement
Author: ADAAD / InnovativeAI-adaad
Integration points:
  - Imports from: runtime.evolution.lineage_v2, security.cryovant,
                  runtime.sandbox.preflight, runtime.governance.rate_limiter
  - Consumed by: pytest
  - Governance impact: low — test-only; no mutation authority
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# C-04: LineageLedgerV2 — O(n) append fix
# ---------------------------------------------------------------------------

class TestLineageLedgerAppendPerformance:
    """Verify append_event does NOT call verify_integrity() on each write
    once the tail hash is already cached."""

    def test_append_does_not_full_rescan_when_tail_hash_cached(self, tmp_path: Path) -> None:
        from runtime.evolution.lineage_v2 import LineageLedgerV2

        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_test.jsonl")
        verify_calls: list[int] = []
        original_verify = ledger.verify_integrity

        def counting_verify(*args, **kwargs):
            verify_calls.append(1)
            return original_verify(*args, **kwargs)

        ledger.verify_integrity = counting_verify  # type: ignore[method-assign]

        # Bootstrap — first _last_hash() call triggers one verify_integrity
        ledger.append_event("TestEvent", {"seq": 0})
        initial_calls = len(verify_calls)

        # Subsequent appends must NOT trigger additional full scans
        for i in range(1, 10):
            ledger.append_event("TestEvent", {"seq": i})

        extra_calls = len(verify_calls) - initial_calls
        assert extra_calls == 0, (
            f"append_event triggered {extra_calls} extra verify_integrity() calls "
            f"after the tail hash was cached — O(n²) regression detected."
        )

    def test_tail_hash_advances_correctly_across_appends(self, tmp_path: Path) -> None:
        from runtime.evolution.lineage_v2 import LineageLedgerV2

        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_chain.jsonl")
        for i in range(5):
            ledger.append_event("ChainEvent", {"i": i})

        # After all appends, integrity verification must pass cleanly
        ledger._verified_tail_hash = None  # force full re-verification
        ledger.verify_integrity()           # raises on any chain break
        assert ledger._verified_tail_hash is not None

    def test_fresh_ledger_cache_set_after_first_append(self, tmp_path: Path) -> None:
        from runtime.evolution.lineage_v2 import LineageLedgerV2

        ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_cache.jsonl")
        ledger.append_event("Seed", {"x": 1})
        cached = ledger._verified_tail_hash
        assert cached is not None
        assert len(cached) == 64  # SHA-256 hex digest length


# ---------------------------------------------------------------------------
# H-02: assert_governance_signing_key_boot
# ---------------------------------------------------------------------------

class TestGovernanceSigningKeyBootAssertion:
    """Verify fail-closed boot assertion for governance signing keys."""

    def test_dev_env_exempt_no_key_needed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ADAAD_ENV", "dev")
        monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
        from security import cryovant
        cryovant.assert_governance_signing_key_boot()  # must not raise

    def test_staging_without_key_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ADAAD_ENV", "staging")
        monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
        for key in list(os.environ):
            if key.startswith("ADAAD_GOVERNANCE_SESSION_KEY_"):
                monkeypatch.delenv(key, raising=False)
        from security import cryovant
        with pytest.raises(RuntimeError, match="missing_governance_signing_key:critical"):
            cryovant.assert_governance_signing_key_boot()

    def test_production_without_key_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ADAAD_ENV", "production")
        monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
        for key in list(os.environ):
            if key.startswith("ADAAD_GOVERNANCE_SESSION_KEY_"):
                monkeypatch.delenv(key, raising=False)
        from security import cryovant
        with pytest.raises(RuntimeError, match="missing_governance_signing_key:critical"):
            cryovant.assert_governance_signing_key_boot()

    def test_staging_with_signing_key_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ADAAD_ENV", "staging")
        monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", "test-key-material-abc123")
        from security import cryovant
        cryovant.assert_governance_signing_key_boot()  # must not raise

    def test_production_with_key_id_pattern_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ADAAD_ENV", "production")
        monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
        monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_KEY_primary", "ed25519-key-data")
        from security import cryovant
        cryovant.assert_governance_signing_key_boot()  # must not raise

    def test_error_message_includes_env_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ADAAD_ENV", "staging")
        monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
        for key in list(os.environ):
            if key.startswith("ADAAD_GOVERNANCE_SESSION_KEY_"):
                monkeypatch.delenv(key, raising=False)
        from security import cryovant
        with pytest.raises(RuntimeError) as exc_info:
            cryovant.assert_governance_signing_key_boot()
        assert "staging" in str(exc_info.value)


# ---------------------------------------------------------------------------
# H-03: _validate_write_allowlist
# ---------------------------------------------------------------------------

class TestWriteAllowlistValidation:
    """Verify H-03: non-absolute and traversal paths are rejected."""

    def _validate(self, paths):
        from runtime.sandbox.preflight import _validate_write_allowlist
        return _validate_write_allowlist(paths)

    def test_absolute_path_accepted(self) -> None:
        assert self._validate(["/sandbox/output"]) == ()

    def test_relative_path_rejected(self) -> None:
        violations = self._validate(["sandbox/output"])
        assert any("non_absolute" in v for v in violations)

    def test_traversal_path_rejected(self) -> None:
        violations = self._validate(["/sandbox/../etc"])
        assert any("traversal" in v for v in violations)

    def test_mixed_entries_all_violations_reported(self) -> None:
        violations = self._validate(["/ok/path", "relative/path", "/sandbox/../escape"])
        assert len(violations) == 2

    def test_empty_allowlist_no_violations(self) -> None:
        assert self._validate([]) == ()

    def test_none_allowlist_no_violations(self) -> None:
        assert self._validate(None) == ()

    def test_traversal_violation_shows_path(self) -> None:
        violations = self._validate(["/sandbox/../etc"])
        assert "/sandbox/../etc" in violations[0]

    def test_full_analyze_plan_rejects_bad_allowlist(self) -> None:
        from runtime.sandbox.preflight import analyze_execution_plan
        from runtime.sandbox.manifest import SandboxManifest
        from runtime.sandbox.policy import SandboxPolicy

        manifest = SandboxManifest(command=["python", "script.py"], env=[], mounts=[])
        policy = SandboxPolicy(write_path_allowlist=["../escape"])

        result = analyze_execution_plan(manifest=manifest, policy=policy)
        assert not result["ok"]
        assert any("non_absolute" in v or "traversal" in v for v in result["violations"])


# ---------------------------------------------------------------------------
# H-06: ProposalRateLimiter
# ---------------------------------------------------------------------------

class TestProposalRateLimiter:
    """Verify token-bucket rate limiter enforces per-IP limits."""

    def _fresh_limiter(self):
        from runtime.governance.rate_limiter import ProposalRateLimiter
        return ProposalRateLimiter()

    def test_requests_within_limit_allowed(self) -> None:
        with patch.dict(os.environ, {"ADAAD_PROPOSAL_RATE_LIMIT": "10"}):
            limiter = self._fresh_limiter()
            for _ in range(10):
                allowed, _ = limiter.check("192.168.1.1")
                assert allowed

    def test_request_over_limit_rejected(self) -> None:
        with patch.dict(os.environ, {"ADAAD_PROPOSAL_RATE_LIMIT": "3"}):
            limiter = self._fresh_limiter()
            for _ in range(3):
                allowed, _ = limiter.check("10.0.0.1")
                assert allowed
            allowed, info = limiter.check("10.0.0.1")
            assert not allowed
            assert "retry_after_seconds" in info

    def test_different_ips_independent_buckets(self) -> None:
        with patch.dict(os.environ, {"ADAAD_PROPOSAL_RATE_LIMIT": "2"}):
            limiter = self._fresh_limiter()
            limiter.check("1.1.1.1")
            limiter.check("1.1.1.1")
            blocked_a, _ = limiter.check("1.1.1.1")
            assert not blocked_a
            allowed_b, _ = limiter.check("2.2.2.2")
            assert allowed_b

    def test_reset_clears_bucket(self) -> None:
        with patch.dict(os.environ, {"ADAAD_PROPOSAL_RATE_LIMIT": "1"}):
            limiter = self._fresh_limiter()
            limiter.check("5.5.5.5")
            blocked, _ = limiter.check("5.5.5.5")
            assert not blocked
            limiter.reset("5.5.5.5")
            allowed, _ = limiter.check("5.5.5.5")
            assert allowed

    def test_rate_info_carries_diagnostic_fields(self) -> None:
        with patch.dict(os.environ, {"ADAAD_PROPOSAL_RATE_LIMIT": "1"}):
            limiter = self._fresh_limiter()
            limiter.check("6.6.6.6")
            _, info = limiter.check("6.6.6.6")
            assert "source_key" in info
            assert "count_in_window" in info
            assert "limit" in info

    def test_get_limiter_returns_singleton(self) -> None:
        from runtime.governance.rate_limiter import get_limiter
        a = get_limiter()
        b = get_limiter()
        assert a is b
