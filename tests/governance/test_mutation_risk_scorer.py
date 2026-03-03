# SPDX-License-Identifier: Apache-2.0
"""
tests.governance.test_mutation_risk_scorer
==========================================
PR9 -- MutationRiskScorer enhanced QA test suite.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from runtime.governance.mutation_risk_scorer import (
    FileRiskScore,
    MutationRiskReport,
    MutationRiskScorer,
)

_FIXED_TS = "2026-01-01T00:00:00Z"

_YAML_STRICT = "\n".join(
    [
        "promotion_block_threshold: 0.70",
        "weights:",
        "  .py: 0.60",
        "  .md: 0.10",
        "  default: 0.30",
        "sensitive_prefixes:",
        "  - security/",
        "  - runtime/governance/",
    ]
) + "\n"


@pytest.fixture()
def ledger_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def _fake_write_entry(agent_id: str, action: str, payload: dict[str, Any] | None = None) -> None:
        calls.append({"method": "write_entry", "agent_id": agent_id, "action": action, "payload": payload or {}})

    def _fake_append_tx(tx_type: str, payload: dict[str, Any], tx_id: str | None = None) -> dict[str, Any]:
        entry = {"tx": tx_id or "TX-mock", "type": tx_type, "payload": payload}
        calls.append({"method": "append_tx", "type": tx_type, "payload": payload})
        return entry

    monkeypatch.setattr("runtime.governance.mutation_risk_scorer.journal.write_entry", _fake_write_entry)
    monkeypatch.setattr("runtime.governance.mutation_risk_scorer.journal.append_tx", _fake_append_tx)
    return calls


@pytest.fixture()
def scorer(tmp_path: Path) -> MutationRiskScorer:
    thresholds = tmp_path / "risk_thresholds.yaml"
    thresholds.write_text(_YAML_STRICT, encoding="utf-8")
    return MutationRiskScorer(
        thresholds_path=thresholds,
        schema_path=Path("schemas/mutation_risk_report.v1.json"),
        output_dir=tmp_path / "reports" / "risk",
    )


def test_score_returns_mutation_risk_report(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-001",
        changed_files=[{"path": "app/main.py", "changed_lines": 5, "ast_relevant_change": True}],
        generated_at=_FIXED_TS,
    )
    assert isinstance(result, MutationRiskReport)
    assert result.mutation_id == "mut-001"
    assert result.schema_version == "1.0"
    assert 0.0 <= result.score <= 1.0
    assert isinstance(result.threshold, float)
    assert isinstance(result.threshold_exceeded, bool)
    assert isinstance(result.file_scores, tuple)
    assert all(isinstance(item, FileRiskScore) for item in result.file_scores)
    assert len(result.report_sha256) == 64
    assert result.generated_at == _FIXED_TS


def test_deterministic_reproducibility_same_payload(scorer: MutationRiskScorer) -> None:
    files = [
        {"path": "runtime/governance/policy_validator.py", "changed_lines": 10, "ast_relevant_change": True},
        {"path": "security/ledger/journal.py", "changed_lines": 3, "ast_relevant_change": True},
    ]
    first = scorer.score(mutation_id="mut-det", changed_files=files, generated_at=_FIXED_TS)
    second = scorer.score(mutation_id="mut-det", changed_files=files, generated_at=_FIXED_TS)
    assert first.to_payload() == second.to_payload()
    assert first.report_sha256 == second.report_sha256


def test_deterministic_reversed_file_order(scorer: MutationRiskScorer) -> None:
    files = [
        {"path": "runtime/governance/policy_validator.py", "changed_lines": 10, "ast_relevant_change": True},
        {"path": "security/ledger/journal.py", "changed_lines": 3, "ast_relevant_change": True},
    ]
    first = scorer.score(mutation_id="mut-ord", changed_files=files, generated_at=_FIXED_TS)
    second = scorer.score(mutation_id="mut-ord", changed_files=list(reversed(files)), generated_at=_FIXED_TS)
    assert first.to_payload() == second.to_payload()


def test_promotion_blocked_on_high_security_risk(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-blocked",
        changed_files=[{"path": "security/ledger/journal.py", "changed_lines": 300, "ast_relevant_change": True}],
        generated_at=_FIXED_TS,
    )
    assert result.threshold_exceeded is True
    assert result.score > result.threshold


def test_schema_output_validates_against_json_schema(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-schema",
        changed_files=[{"path": "app/main.py", "changed_lines": 2, "ast_relevant_change": True}],
        base_risk_score=0.1,
        generated_at=_FIXED_TS,
    )
    payload = json.loads((scorer.output_dir / "mut-schema.json").read_text(encoding="utf-8"))

    required = [
        "schema_version",
        "mutation_id",
        "generated_at",
        "score",
        "threshold",
        "threshold_exceeded",
        "report_sha256",
        "file_scores",
    ]
    for key in required:
        assert key in payload

    assert payload["schema_version"] == "1.0"
    assert payload["mutation_id"] == "mut-schema"
    assert 0.0 <= payload["score"] <= 1.0
    assert isinstance(payload["threshold_exceeded"], bool)
    assert re.fullmatch(r"[0-9a-f]{64}", payload["report_sha256"])
    assert payload["report_sha256"] == result.report_sha256


def test_fixture_based_scoring_accuracy(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-fixture",
        changed_files=[
            {"path": "security/keys/rotation.py", "changed_lines": 5, "ast_relevant_change": True},
            {"path": "docs/README.md", "changed_lines": 8, "ast_relevant_change": False},
        ],
        generated_at=_FIXED_TS,
    )
    by_path = {item.path: item.score for item in result.file_scores}
    assert by_path["security/keys/rotation.py"] == pytest.approx(0.90, abs=1e-5)
    assert by_path["docs/README.md"] == pytest.approx(0.10, abs=1e-5)
    assert result.score == pytest.approx(0.50, abs=1e-5)


def test_base_risk_score_overrides_low_aggregate(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-base",
        changed_files=[{"path": "docs/README.md", "changed_lines": 1, "ast_relevant_change": False}],
        base_risk_score=0.99,
        generated_at=_FIXED_TS,
    )
    assert result.score == pytest.approx(0.99, abs=1e-5)


def test_empty_changed_files_uses_base_risk_score(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-empty",
        changed_files=[],
        base_risk_score=0.0,
        generated_at=_FIXED_TS,
    )
    assert result.score == pytest.approx(0.0, abs=1e-5)
    assert result.file_scores == ()

    result_2 = scorer.score(
        mutation_id="mut-empty-base",
        changed_files=[],
        base_risk_score=0.55,
        generated_at=_FIXED_TS,
    )
    assert result_2.score == pytest.approx(0.55, abs=1e-5)


def test_single_file_no_sensitive_no_large_change(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-single",
        changed_files=[{"path": "app/utils.py", "changed_lines": 5, "ast_relevant_change": True}],
        generated_at=_FIXED_TS,
    )
    assert len(result.file_scores) == 1
    file_score = result.file_scores[0]
    assert file_score.score == pytest.approx(0.70, abs=1e-5)
    assert "ast_relevant_change" in file_score.reasons
    assert "sensitive_path" not in file_score.reasons
    assert "large_change" not in file_score.reasons


def test_sensitive_path_adds_penalty(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-sens",
        changed_files=[{"path": "runtime/governance/gate.py", "changed_lines": 2, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    file_score = result.file_scores[0]
    assert file_score.score == pytest.approx(0.80, abs=1e-5)
    assert "sensitive_path" in file_score.reasons


def test_large_change_score_caps_at_one(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-large",
        changed_files=[{"path": "security/critical.py", "changed_lines": 99999, "ast_relevant_change": True}],
        generated_at=_FIXED_TS,
    )
    file_score = result.file_scores[0]
    assert file_score.score <= 1.0
    assert "large_change" in file_score.reasons


def test_extension_weight_applied_for_unknown_suffix(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-toml",
        changed_files=[{"path": "config/settings.toml", "changed_lines": 3, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    file_score = result.file_scores[0]
    assert file_score.score == pytest.approx(0.30, abs=1e-5)
    assert "extension:.toml" in file_score.reasons


def test_report_sha256_is_64_hex_chars(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-sha",
        changed_files=[{"path": "app/x.py", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    assert re.fullmatch(r"[0-9a-f]{64}", result.report_sha256)


def test_report_sha256_changes_on_different_inputs(scorer: MutationRiskScorer) -> None:
    first = scorer.score(
        mutation_id="mut-sha-a",
        changed_files=[{"path": "app/a.py", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    second = scorer.score(
        mutation_id="mut-sha-b",
        changed_files=[{"path": "security/b.py", "changed_lines": 1, "ast_relevant_change": True}],
        generated_at=_FIXED_TS,
    )
    assert first.report_sha256 != second.report_sha256


def test_report_written_to_disk_at_expected_path(scorer: MutationRiskScorer) -> None:
    scorer.score(
        mutation_id="mut-disk",
        changed_files=[{"path": "app/main.py", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    path = scorer.output_dir / "mut-disk.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["mutation_id"] == "mut-disk"
    assert payload["schema_version"] == "1.0"


def test_report_json_is_utf8_sorted_keys(scorer: MutationRiskScorer) -> None:
    scorer.score(
        mutation_id="mut-sort",
        changed_files=[{"path": "app/main.py", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    raw = (scorer.output_dir / "mut-sort.json").read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    keys = list(payload.keys())
    assert keys == sorted(keys)


def test_threshold_exceeded_false_below_threshold(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-below",
        changed_files=[{"path": "docs/README.md", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    assert result.threshold_exceeded is False
    assert result.score <= result.threshold


def test_threshold_exceeded_true_above_threshold(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-above",
        changed_files=[{"path": "security/hot.py", "changed_lines": 200, "ast_relevant_change": True}],
        generated_at=_FIXED_TS,
    )
    assert result.threshold_exceeded is True
    assert result.score > result.threshold


def test_threshold_equal_is_not_exceeded(scorer: MutationRiskScorer) -> None:
    result = scorer.score(
        mutation_id="mut-equal",
        changed_files=[],
        base_risk_score=0.70,
        generated_at=_FIXED_TS,
    )
    assert result.score == pytest.approx(0.70, abs=1e-5)
    assert result.threshold == pytest.approx(0.70, abs=1e-5)
    assert result.threshold_exceeded is False


def test_ledger_event_emitted_on_score(scorer: MutationRiskScorer, ledger_calls: list[dict[str, Any]]) -> None:
    scorer.score(
        mutation_id="mut-ledger",
        changed_files=[{"path": "app/main.py", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    writes = [item for item in ledger_calls if item["method"] == "write_entry"]
    txs = [item for item in ledger_calls if item["method"] == "append_tx"]
    assert len(writes) == 1
    assert len(txs) == 1
    assert writes[0]["action"] == "mutation_risk_report_generated.v1"
    assert txs[0]["type"] == "mutation_risk_report_generated.v1"


def test_ledger_event_payload_fields(scorer: MutationRiskScorer, ledger_calls: list[dict[str, Any]]) -> None:
    result = scorer.score(
        mutation_id="mut-ledger-fields",
        changed_files=[{"path": "app/main.py", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    tx_payload = next(item["payload"] for item in ledger_calls if item["method"] == "append_tx")
    assert tx_payload["mutation_id"] == "mut-ledger-fields"
    assert tx_payload["schema_version"] == "1.0"
    assert tx_payload["report_sha256"] == result.report_sha256
    assert "report_path" in tx_payload
    assert "score" in tx_payload
    assert "threshold" in tx_payload
    assert "threshold_exceeded" in tx_payload


def test_schema_validation_rejects_out_of_range_score(scorer: MutationRiskScorer, monkeypatch: pytest.MonkeyPatch) -> None:
    original_score_file = MutationRiskScorer._score_file

    def _bad_score(self: MutationRiskScorer, change: dict[str, Any]) -> FileRiskScore:
        score = original_score_file(self, change)
        return FileRiskScore(
            path=score.path,
            score=1.5,
            changed_lines=score.changed_lines,
            ast_relevant_change=score.ast_relevant_change,
            reasons=score.reasons,
        )

    monkeypatch.setattr(MutationRiskScorer, "_score_file", _bad_score)
    with pytest.raises(ValueError, match="invalid_mutation_risk_report"):
        scorer.score(
            mutation_id="mut-bad-score",
            changed_files=[{"path": "app/main.py", "changed_lines": 1, "ast_relevant_change": False}],
            generated_at=_FIXED_TS,
        )


def test_custom_thresholds_loaded_from_yaml(tmp_path: Path) -> None:
    thresholds = tmp_path / "custom.yaml"
    thresholds.write_text(
        "promotion_block_threshold: 0.20\nweights:\n  .py: 0.50\n  default: 0.30\n",
        encoding="utf-8",
    )
    scorer = MutationRiskScorer(
        thresholds_path=thresholds,
        schema_path=Path("schemas/mutation_risk_report.v1.json"),
        output_dir=tmp_path / "out",
    )
    result = scorer.score(
        mutation_id="custom-thresh",
        changed_files=[{"path": "app/main.py", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    assert result.threshold == pytest.approx(0.20, abs=1e-5)
    assert result.threshold_exceeded is True


def test_missing_thresholds_file_uses_defaults(tmp_path: Path) -> None:
    scorer = MutationRiskScorer(
        thresholds_path=tmp_path / "nonexistent.yaml",
        schema_path=Path("schemas/mutation_risk_report.v1.json"),
        output_dir=tmp_path / "out",
    )
    result = scorer.score(
        mutation_id="defaults",
        changed_files=[{"path": "app/main.py", "changed_lines": 1, "ast_relevant_change": False}],
        generated_at=_FIXED_TS,
    )
    assert result.threshold == pytest.approx(0.80, abs=1e-5)


def test_file_scores_sorted_deterministically(scorer: MutationRiskScorer) -> None:
    files = [
        {"path": "z_last.py", "changed_lines": 1, "ast_relevant_change": False},
        {"path": "a_first.py", "changed_lines": 1, "ast_relevant_change": False},
        {"path": "m_middle.py", "changed_lines": 1, "ast_relevant_change": False},
    ]
    result = scorer.score(mutation_id="mut-sort-paths", changed_files=files, generated_at=_FIXED_TS)
    paths = [item.path for item in result.file_scores]
    assert paths == sorted(paths)
