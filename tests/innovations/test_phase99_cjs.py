# SPDX-License-Identifier: Apache-2.0
"""T99-CJS-01..30 — Phase 99 INNOV-14 Constitutional Jury System acceptance tests.

Invariants under test:
  CJS-0         deliberate() is the sole authority for HIGH_STAKES_PATHS evaluation
  CJS-QUORUM-0  Majority requires >= MAJORITY_REQUIRED (2-of-3); ties default to reject
  CJS-DETERM-0  decision_digest deterministic; seeds derived from mutation_id only
  CJS-DISSENT-0 Dissenting verdicts written to dissent ledger before deliberate() returns
  CJS-PERSIST-0 _persist() and _record_dissent() use Path.open — never builtins.open
"""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import patch, mock_open, call
import pytest

from runtime.innovations30.constitutional_jury import (
    ConstitutionalJury, JuryDecision, JurorVerdict,
    ConstitutionalJuryConfigError,
    is_high_stakes, JURY_SIZE, MAJORITY_REQUIRED, HIGH_STAKES_PATHS,
    _compute_decision_digest, _make_seed,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_verdict(juror_id: str, mutation_id: str, verdict: str,
                  seed: str = "test-seed") -> JurorVerdict:
    return JurorVerdict(
        juror_id=juror_id, mutation_id=mutation_id, verdict=verdict,
        confidence=0.9, reasoning="test", rules_fired=["R1"], random_seed=seed,
    )

def _unanimous_approve_fn(mutation_id: str, seed: str) -> JurorVerdict:
    return _make_verdict(seed, mutation_id, "approve", seed)

def _unanimous_reject_fn(mutation_id: str, seed: str) -> JurorVerdict:
    return _make_verdict(seed, mutation_id, "reject", seed)

def _split_fn(mutation_id: str, seed: str) -> JurorVerdict:
    """2 approve, 1 reject — majority approve, dissent present."""
    verdict = "reject" if seed.endswith("-2") else "approve"
    return _make_verdict(seed, mutation_id, verdict, seed)

def _minority_approve_fn(mutation_id: str, seed: str) -> JurorVerdict:
    """1 approve, 2 reject — majority reject."""
    verdict = "approve" if seed.endswith("-0") else "reject"
    return _make_verdict(seed, mutation_id, verdict, seed)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def jury(tmp_path):
    return ConstitutionalJury(ledger_path=tmp_path / "jury.jsonl")

@pytest.fixture()
def mutation_id():
    return "mut-abc12345"

# ─────────────────────────────────────────────────────────────────────────────
# CJS-0 — High-stakes gate (T99-CJS-01..05)
# ─────────────────────────────────────────────────────────────────────────────

def test_cjs_01_high_stakes_runtime_path():
    """CJS-0: files under runtime/ are high-stakes."""
    assert is_high_stakes(["runtime/evolution/loop.py"]) is True

def test_cjs_02_high_stakes_security_path():
    """CJS-0: files under security/ are high-stakes."""
    assert is_high_stakes(["security/auth.py"]) is True

def test_cjs_03_high_stakes_app_main():
    """CJS-0: app/main.py is high-stakes."""
    assert is_high_stakes(["app/main.py"]) is True

def test_cjs_04_not_high_stakes_tests():
    """CJS-0: tests/ files are not high-stakes."""
    assert is_high_stakes(["tests/test_foo.py", "docs/README.md"]) is False

def test_cjs_05_high_stakes_mixed_files():
    """CJS-0: mixed list is high-stakes if any file matches."""
    assert is_high_stakes(["docs/README.md", "runtime/core.py"]) is True

# ─────────────────────────────────────────────────────────────────────────────
# CJS-QUORUM-0 — Quorum enforcement (T99-CJS-06..11)
# ─────────────────────────────────────────────────────────────────────────────

def test_cjs_06_quorum_config_error_on_small_jury(tmp_path):
    """CJS-QUORUM-0: jury_size < JURY_SIZE raises ConstitutionalJuryConfigError."""
    with pytest.raises(ConstitutionalJuryConfigError, match="CJS-QUORUM-0"):
        ConstitutionalJury(ledger_path=tmp_path / "j.jsonl", jury_size=2)

def test_cjs_07_quorum_config_error_size_one(tmp_path):
    """CJS-QUORUM-0: jury_size=1 raises."""
    with pytest.raises(ConstitutionalJuryConfigError):
        ConstitutionalJury(ledger_path=tmp_path / "j.jsonl", jury_size=1)

def test_cjs_08_unanimous_approve_decision(jury, mutation_id):
    """CJS-QUORUM-0: 3/3 approve → majority_verdict == 'approve', unanimous=True."""
    d = jury.deliberate(mutation_id, ["runtime/foo.py"], _unanimous_approve_fn)
    assert d.majority_verdict == "approve"
    assert d.unanimous is True
    assert d.approve_count == 3
    assert d.reject_count == 0

def test_cjs_09_unanimous_reject_decision(jury, mutation_id):
    """CJS-QUORUM-0: 0/3 approve → majority_verdict == 'reject', unanimous=True."""
    d = jury.deliberate(mutation_id, ["runtime/foo.py"], _unanimous_reject_fn)
    assert d.majority_verdict == "reject"
    assert d.unanimous is True

def test_cjs_10_majority_approve_with_dissent(jury, mutation_id):
    """CJS-QUORUM-0: 2/3 approve → majority_verdict == 'approve', unanimous=False."""
    d = jury.deliberate(mutation_id, ["runtime/foo.py"], _split_fn)
    assert d.majority_verdict == "approve"
    assert d.unanimous is False
    assert d.approve_count == 2
    assert d.reject_count == 1

def test_cjs_11_minority_approve_rejects(jury, mutation_id):
    """CJS-QUORUM-0: 1/3 approve → majority_verdict == 'reject'."""
    d = jury.deliberate(mutation_id, ["runtime/foo.py"], _minority_approve_fn)
    assert d.majority_verdict == "reject"
    assert d.approve_count == 1

# ─────────────────────────────────────────────────────────────────────────────
# CJS-DETERM-0 — Determinism (T99-CJS-12..18)
# ─────────────────────────────────────────────────────────────────────────────

def test_cjs_12_decision_digest_is_deterministic(jury, mutation_id):
    """CJS-DETERM-0: same inputs produce same decision_digest."""
    d1 = jury.deliberate(mutation_id, [], _unanimous_approve_fn)
    d2 = jury.deliberate(mutation_id, [], _unanimous_approve_fn)
    assert d1.decision_digest == d2.decision_digest

def test_cjs_13_digest_changes_on_mutation_id_change(jury):
    """CJS-DETERM-0: different mutation_id → different digest."""
    d1 = jury.deliberate("mut-AAAA", [], _unanimous_approve_fn)
    d2 = jury.deliberate("mut-BBBB", [], _unanimous_approve_fn)
    assert d1.decision_digest != d2.decision_digest

def test_cjs_14_digest_prefix_sha256(jury, mutation_id):
    """CJS-DETERM-0: decision_digest begins with 'sha256:'."""
    d = jury.deliberate(mutation_id, [], _unanimous_approve_fn)
    assert d.decision_digest.startswith("sha256:")

def test_cjs_15_compute_digest_helper_deterministic():
    """CJS-DETERM-0: _compute_decision_digest is idempotent."""
    h1 = _compute_decision_digest("mut-X", "approve", 2, 3)
    h2 = _compute_decision_digest("mut-X", "approve", 2, 3)
    assert h1 == h2

def test_cjs_16_seed_derivation_deterministic():
    """CJS-DETERM-0: _make_seed produces consistent output from mutation_id + index."""
    assert _make_seed("mut-abc12345", 0) == _make_seed("mut-abc12345", 0)
    assert _make_seed("mut-abc12345", 0) != _make_seed("mut-abc12345", 1)

def test_cjs_17_jury_size_included_in_digest():
    """CJS-DETERM-0: jury_size is part of digest payload."""
    h3 = _compute_decision_digest("mut-X", "approve", 2, 3)
    h4 = _compute_decision_digest("mut-X", "approve", 2, 4)
    assert h3 != h4

def test_cjs_18_decision_stores_jury_size(jury, mutation_id):
    """CJS-DETERM-0: JuryDecision.jury_size == ConstitutionalJury.jury_size."""
    d = jury.deliberate(mutation_id, [], _unanimous_approve_fn)
    assert d.jury_size == JURY_SIZE

# ─────────────────────────────────────────────────────────────────────────────
# CJS-DISSENT-0 — Dissent recording (T99-CJS-19..24)
# ─────────────────────────────────────────────────────────────────────────────

def test_cjs_19_dissent_recorded_flag_on_split(jury, mutation_id):
    """CJS-DISSENT-0: split verdict sets dissent_recorded=True."""
    d = jury.deliberate(mutation_id, [], _split_fn)
    assert d.dissent_recorded is True

def test_cjs_20_no_dissent_on_unanimous(jury, mutation_id):
    """CJS-DISSENT-0: unanimous verdict sets dissent_recorded=False."""
    d = jury.deliberate(mutation_id, [], _unanimous_approve_fn)
    assert d.dissent_recorded is False

def test_cjs_21_dissent_ledger_written_on_split(jury, mutation_id):
    """CJS-DISSENT-0: dissent ledger file exists after split verdict."""
    jury.deliberate(mutation_id, [], _split_fn)
    dissent_path = jury.ledger_path.with_suffix(".dissent.jsonl")
    assert dissent_path.exists()

def test_cjs_22_dissent_records_contain_invariant(jury, mutation_id):
    """CJS-DISSENT-0: each dissent record lists CJS-DISSENT-0 in invariants."""
    jury.deliberate(mutation_id, [], _split_fn)
    records = jury.dissent_records()
    assert any("CJS-DISSENT-0" in r.get("invariants", []) for r in records)

def test_cjs_23_dissent_records_fail_open_on_corrupt(jury, tmp_path):
    """CJS-DISSENT-0: corrupt lines in dissent ledger silently skipped."""
    dissent_path = jury.ledger_path.with_suffix(".dissent.jsonl")
    dissent_path.parent.mkdir(parents=True, exist_ok=True)
    dissent_path.write_text("NOT_JSON\n{\"ok\": true}\n")
    records = jury.dissent_records()
    assert len(records) == 1

def test_cjs_24_dissent_records_missing_file_returns_empty(tmp_path):
    """CJS-DISSENT-0: missing dissent ledger returns empty list (fail-open)."""
    j = ConstitutionalJury(ledger_path=tmp_path / "jury.jsonl")
    assert j.dissent_records() == []

# ─────────────────────────────────────────────────────────────────────────────
# CJS-PERSIST-0 — Path.open enforcement (T99-CJS-25..27)
# ─────────────────────────────────────────────────────────────────────────────

def test_cjs_25_persist_uses_path_open(jury, mutation_id):
    """CJS-PERSIST-0: _persist uses Path.open not builtins.open."""
    with patch("runtime.innovations30.constitutional_jury.Path.open",
               mock_open()) as mocked:
        d = JuryDecision(mutation_id=mutation_id, unanimous=True,
                         majority_verdict="approve", approve_count=3,
                         reject_count=0, jury_size=3, individual_verdicts=[],
                         dissent_recorded=False)
        jury._persist(d)
        mocked.assert_called()

def test_cjs_26_record_dissent_uses_path_open(jury, mutation_id):
    """CJS-PERSIST-0: _record_dissent uses Path.open not builtins.open."""
    verdicts = [_make_verdict(f"j-{i}", mutation_id, "reject" if i == 2 else "approve")
                for i in range(3)]
    with patch("runtime.innovations30.constitutional_jury.Path.open",
               mock_open()) as mocked:
        jury._record_dissent(mutation_id, verdicts, "approve")
        mocked.assert_called()

def test_cjs_27_ledger_entries_append_not_overwrite(jury, mutation_id):
    """CJS-PERSIST-0: multiple deliberations append; ledger is not overwritten."""
    jury.deliberate(mutation_id, [], _unanimous_approve_fn)
    jury.deliberate(mutation_id + "-2", [], _unanimous_approve_fn)
    records = jury.verdict_ledger()
    assert len(records) >= 2

# ─────────────────────────────────────────────────────────────────────────────
# Integration (T99-CJS-28..30)
# ─────────────────────────────────────────────────────────────────────────────

def test_cjs_28_full_deliberation_roundtrip(jury, mutation_id):
    """Integration: deliberate() returns complete JuryDecision with digest."""
    d = jury.deliberate(mutation_id, ["runtime/core.py"], _split_fn)
    assert isinstance(d, JuryDecision)
    assert d.decision_digest.startswith("sha256:")
    assert d.majority_verdict in ("approve", "reject")
    assert d.approve_count + d.reject_count == JURY_SIZE

def test_cjs_29_verdict_ledger_contains_invariant_list(jury, mutation_id):
    """Integration: persisted record includes all five CJS invariant codes."""
    jury.deliberate(mutation_id, [], _unanimous_approve_fn)
    records = jury.verdict_ledger()
    inv = records[-1].get("invariants", [])
    for code in ["CJS-0", "CJS-QUORUM-0", "CJS-DETERM-0", "CJS-DISSENT-0", "CJS-PERSIST-0"]:
        assert code in inv

def test_cjs_30_verdict_ledger_fail_open_on_corrupt(jury):
    """Integration (CJS-LOAD-0): corrupt ledger lines silently skipped."""
    jury.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    jury.ledger_path.write_text("BAD_JSON\n{\"majority_verdict\": \"approve\"}\n")
    records = jury.verdict_ledger()
    assert len(records) == 1
    assert records[0]["majority_verdict"] == "approve"
