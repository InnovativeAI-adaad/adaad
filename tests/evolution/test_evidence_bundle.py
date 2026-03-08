# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib
import json
from pathlib import Path

from runtime.evolution.evidence_bundle import EvidenceBundleBuilder, EvidenceBundleError
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.constitution import CONSTITUTION_VERSION
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def test_export_bundle_conforms_to_schema_and_is_immutable(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {"config": 1}})
    ledger.append_bundle_with_digest(
        "epoch-1",
        {
            "bundle_id": "bundle-1",
            "impact": 0.3,
            "risk_tier": "high",
            "certificate": {"bundle_id": "bundle-1", "strategy_snapshot_hash": "sha256:snap"},
            "strategy_set": ["safe"],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": "epoch-1", "state": {"config": 2}})

    sandbox_path = tmp_path / "sandbox_evidence.jsonl"
    _write_jsonl(
        sandbox_path,
        [
            {
                "payload": {
                    "evidence_hash": "sha256:evidence1",
                    "manifest_hash": "sha256:manifest1",
                    "policy_hash": "sha256:policy1",
                    "manifest": {"epoch_id": "epoch-1", "bundle_id": "bundle-1"},
                },
                "prev_hash": "sha256:0",
                "hash": "sha256:entry1",
            }
        ],
    )

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=sandbox_path,
        export_dir=tmp_path / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    bundle = builder.build_bundle(epoch_start="epoch-1", persist=True)

    assert builder.validate_bundle(bundle) == []
    export_path = tmp_path / "exports" / f"{bundle['bundle_id']}.json"
    assert export_path.exists()
    assert json.loads(export_path.read_text(encoding="utf-8")) == bundle
    assert bundle["scoring_algorithm_version"]
    assert bundle["constitution_version"]
    assert bundle["governor_version"]
    assert bundle["fitness_weights_hash"]
    assert bundle["goal_graph_hash"]
    assert bundle["governor_version"]
    assert bundle["fitness_weights_hash"].startswith("sha256:")
    assert bundle["goal_graph_hash"].startswith("sha256:")
    assert bundle["export_metadata"]["retention_days"] >= 1
    assert bundle["export_metadata"]["access_scope"]
    assert bundle["export_metadata"]["signer"]["signed_digest"] == bundle["export_metadata"]["digest"]
    assert bundle["export_metadata"]["environment"]["digest_algorithm"] == "sha256"


def test_export_bundle_digest_is_reproducible_for_unchanged_ledger(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {"a": 1}})
    ledger.append_bundle_with_digest(
        "epoch-1",
        {
            "bundle_id": "bundle-1",
            "impact": 0.1,
            "risk_tier": "low",
            "certificate": {"bundle_id": "bundle-1"},
            "strategy_set": [],
        },
    )

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=tmp_path / "sandbox_evidence.jsonl",
        export_dir=tmp_path / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    first = builder.build_bundle(epoch_start="epoch-1", persist=True)
    second = builder.build_bundle(epoch_start="epoch-1", persist=True)

    assert first["export_metadata"]["digest"] == second["export_metadata"]["digest"]
    assert first["bundle_id"] == second["bundle_id"]
    assert canonical_json(first) == canonical_json(second)
    assert first["export_metadata"]["digest"] == sha256_prefixed_digest({k: v for k, v in first.items() if k not in {"bundle_id", "export_metadata"}})


def test_validate_bundle_allow_legacy_accepts_missing_provenance_fields(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {"a": 1}})
    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=tmp_path / "sandbox_evidence.jsonl",
        export_dir=tmp_path / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    bundle = builder.build_bundle(epoch_start="epoch-1", persist=False)
    legacy_bundle = dict(bundle)
    legacy_bundle.pop("governor_version", None)
    legacy_bundle.pop("fitness_weights_hash", None)
    legacy_bundle.pop("goal_graph_hash", None)

    assert builder.validate_bundle(legacy_bundle, allow_legacy=True) == []


def test_export_bundle_rejects_invalid_sandbox_jsonl(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {}})

    sandbox_path = tmp_path / "sandbox_evidence.jsonl"
    sandbox_path.write_text("{\"payload\":{}\n", encoding="utf-8")

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=sandbox_path,
        export_dir=tmp_path / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    try:
        builder.build_bundle(epoch_start="epoch-1", persist=False)
        assert False, "expected invalid_jsonl failure"
    except EvidenceBundleError as exc:
        assert "invalid_jsonl" in str(exc)


def test_export_bundle_rejects_missing_schema(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {}})

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=tmp_path / "sandbox_evidence.jsonl",
        export_dir=tmp_path / "exports",
        schema_path=tmp_path / "missing_schema.json",
    )
    try:
        builder.build_bundle(epoch_start="epoch-1", persist=False)
        assert False, "expected missing_schema failure"
    except EvidenceBundleError as exc:
        assert "missing_schema" in str(exc)


def test_export_bundle_rejects_immutable_overwrite(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {"x": 1}})

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=tmp_path / "sandbox_evidence.jsonl",
        export_dir=tmp_path / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    first = builder.build_bundle(epoch_start="epoch-1", persist=True)
    export_path = tmp_path / "exports" / f"{first['bundle_id']}.json"
    export_path.write_text("{}", encoding="utf-8")

    try:
        builder.build_bundle(epoch_start="epoch-1", persist=True)
        assert False, "expected immutable_export_mismatch"
    except EvidenceBundleError as exc:
        assert "immutable_export_mismatch" in str(exc)


def test_validate_bundle_legacy_mode_backfills_new_required_fields(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {}})

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=tmp_path / "sandbox_evidence.jsonl",
        export_dir=tmp_path / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    bundle = builder.build_bundle(epoch_start="epoch-1", persist=False)
    legacy_bundle = dict(bundle)
    legacy_bundle.pop("scoring_algorithm_version")
    legacy_bundle.pop("constitution_version")
    legacy_bundle.pop("governor_version")
    legacy_bundle.pop("fitness_weights_hash")
    legacy_bundle.pop("goal_graph_hash")

    strict_errors = builder.validate_bundle(legacy_bundle)
    assert "$.scoring_algorithm_version:missing_required" in strict_errors
    assert "$.constitution_version:missing_required" in strict_errors
    assert "$.governor_version:missing_required" in strict_errors
    assert "$.fitness_weights_hash:missing_required" in strict_errors
    assert "$.goal_graph_hash:missing_required" in strict_errors

    assert builder.validate_bundle(legacy_bundle, allow_legacy=True) == []


def test_legacy_bundle_validation_disabled_by_default_in_strict_context(monkeypatch) -> None:
    from runtime.evolution import evidence_bundle as module

    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.delenv("ADAAD_ENABLE_LEGACY_EVIDENCE_BUNDLE", raising=False)

    assert module._legacy_bundle_validation_enabled() is False


def test_legacy_bundle_validation_can_be_explicitly_enabled(monkeypatch) -> None:
    from runtime.evolution import evidence_bundle as module

    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.setenv("ADAAD_ENABLE_LEGACY_EVIDENCE_BUNDLE", "1")

    assert module._legacy_bundle_validation_enabled() is True


def test_evidence_bundle_uses_canonical_constitution_version_when_env_unset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ADAAD_CONSTITUTION_VERSION", raising=False)
    from runtime.evolution import evidence_bundle as module

    importlib.reload(module)

    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {}})

    builder = module.EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=tmp_path / "sandbox_evidence.jsonl",
        export_dir=tmp_path / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    bundle = builder.build_bundle(epoch_start="epoch-1", persist=False)

    assert bundle["constitution_version"] == CONSTITUTION_VERSION

    importlib.reload(module)
