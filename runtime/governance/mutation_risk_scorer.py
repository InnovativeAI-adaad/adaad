# SPDX-License-Identifier: Apache-2.0
"""Deterministic mutation-risk scoring and report emission."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from runtime import ROOT_DIR
from runtime.constitution import yaml
from runtime.timeutils import now_iso
from security.ledger import journal

RISK_REPORT_SCHEMA_PATH = ROOT_DIR / "schemas" / "mutation_risk_report.v1.json"
RISK_REPORT_OUTPUT_DIR = ROOT_DIR / "reports" / "risk"
RISK_THRESHOLDS_PATH = ROOT_DIR / "runtime" / "governance" / "risk_thresholds.yaml"


@dataclass(frozen=True)
class FileRiskScore:
    """Risk score detail for one file touched by a mutation."""

    path: str
    score: float
    changed_lines: int
    ast_relevant_change: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MutationRiskReport:
    """Deterministic mutation risk report payload."""

    schema_version: str
    mutation_id: str
    generated_at: str
    score: float
    threshold: float
    threshold_exceeded: bool
    file_scores: tuple[FileRiskScore, ...]
    report_sha256: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["file_scores"] = [
            {
                "path": item.path,
                "score": item.score,
                "changed_lines": item.changed_lines,
                "ast_relevant_change": item.ast_relevant_change,
                "reasons": list(item.reasons),
            }
            for item in self.file_scores
        ]
        return payload


class MutationRiskScorer:
    """Compute deterministic mutation risk scores and write governance reports."""

    _DEFAULT_WEIGHTS: dict[str, float] = {
        ".py": 0.55,
        ".js": 0.50,
        ".ts": 0.50,
        ".rs": 0.65,
        "default": 0.35,
    }
    _DEFAULT_SENSITIVE_PREFIXES: tuple[str, ...] = ("security/", "runtime/governance/", "app/orchestration/")

    def __init__(
        self,
        *,
        thresholds_path: Path = RISK_THRESHOLDS_PATH,
        schema_path: Path = RISK_REPORT_SCHEMA_PATH,
        output_dir: Path = RISK_REPORT_OUTPUT_DIR,
    ) -> None:
        self.thresholds_path = Path(thresholds_path)
        self.schema_path = Path(schema_path)
        self.output_dir = Path(output_dir)
        self._thresholds = self._load_thresholds(self.thresholds_path)

    def _load_thresholds(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"promotion_block_threshold": 0.8, "weights": dict(self._DEFAULT_WEIGHTS), "sensitive_prefixes": list(self._DEFAULT_SENSITIVE_PREFIXES)}
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("invalid_risk_thresholds:root_not_object")
        weights = dict(self._DEFAULT_WEIGHTS)
        raw_weights = loaded.get("weights")
        if isinstance(raw_weights, dict):
            for key, value in raw_weights.items():
                weights[str(key)] = float(value)
        prefixes = loaded.get("sensitive_prefixes")
        return {
            "promotion_block_threshold": float(loaded.get("promotion_block_threshold", 0.8)),
            "weights": weights,
            "sensitive_prefixes": [str(item) for item in prefixes] if isinstance(prefixes, list) else list(self._DEFAULT_SENSITIVE_PREFIXES),
        }

    @staticmethod
    def _stable_sha256(payload: Mapping[str, Any]) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _score_file(self, change: Mapping[str, Any]) -> FileRiskScore:
        path = str(change.get("path") or "")
        changed_lines = max(1, int(change.get("changed_lines") or 1))
        ast_relevant_change = bool(change.get("ast_relevant_change", True))
        suffix = Path(path).suffix.lower()
        weights: Mapping[str, float] = self._thresholds["weights"]
        base = float(weights.get(suffix, weights.get("default", 0.35)))
        score = base
        reasons: list[str] = [f"extension:{suffix or 'none'}"]

        prefixes: Sequence[str] = self._thresholds.get("sensitive_prefixes", [])
        if any(path.startswith(prefix) for prefix in prefixes):
            score += 0.2
            reasons.append("sensitive_path")
        if ast_relevant_change:
            score += 0.1
            reasons.append("ast_relevant_change")
        if changed_lines > 40:
            score += min(0.2, changed_lines / 500.0)
            reasons.append("large_change")

        return FileRiskScore(
            path=path,
            score=round(min(1.0, score), 6),
            changed_lines=changed_lines,
            ast_relevant_change=ast_relevant_change,
            reasons=tuple(sorted(reasons)),
        )

    def _validate_report_payload(self, payload: Mapping[str, Any]) -> None:
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        errors: list[str] = []
        self._validate_against_schema(schema=schema, payload=payload, path="$", errors=errors)
        if errors:
            raise ValueError(f"invalid_mutation_risk_report:{'|'.join(errors)}")

    def _validate_against_schema(self, *, schema: Mapping[str, Any], payload: Any, path: str, errors: list[str]) -> None:
        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(payload, dict):
            errors.append(f"{path}:expected_object")
            return
        if expected_type == "array" and not isinstance(payload, list):
            errors.append(f"{path}:expected_array")
            return
        if expected_type == "string" and not isinstance(payload, str):
            errors.append(f"{path}:expected_string")
            return
        if expected_type == "boolean" and not isinstance(payload, bool):
            errors.append(f"{path}:expected_boolean")
            return
        if expected_type == "number" and not isinstance(payload, (int, float)):
            errors.append(f"{path}:expected_number")
            return
        if expected_type == "integer" and (not isinstance(payload, int) or isinstance(payload, bool)):
            errors.append(f"{path}:expected_integer")
            return

        if "const" in schema and payload != schema["const"]:
            errors.append(f"{path}:const_mismatch")
        if "enum" in schema and payload not in schema["enum"]:
            errors.append(f"{path}:enum_mismatch")

        if isinstance(payload, str):
            min_length = schema.get("minLength")
            max_length = schema.get("maxLength")
            if isinstance(min_length, int) and len(payload) < min_length:
                errors.append(f"{path}:min_length")
            if isinstance(max_length, int) and len(payload) > max_length:
                errors.append(f"{path}:max_length")
        if isinstance(payload, (int, float)):
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")
            if isinstance(minimum, (int, float)) and payload < minimum:
                errors.append(f"{path}:minimum")
            if isinstance(maximum, (int, float)) and payload > maximum:
                errors.append(f"{path}:maximum")

        if isinstance(payload, dict):
            required = schema.get("required") if isinstance(schema.get("required"), list) else []
            for key in required:
                if key not in payload:
                    errors.append(f"{path}.{key}:missing_required")
            properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
            for key, value in payload.items():
                key_schema = properties.get(key)
                if isinstance(key_schema, dict):
                    self._validate_against_schema(schema=key_schema, payload=value, path=f"{path}.{key}", errors=errors)
                elif schema.get("additionalProperties") is False:
                    errors.append(f"{path}.{key}:additional_property")

        if isinstance(payload, list):
            items = schema.get("items")
            if isinstance(items, dict):
                for index, value in enumerate(payload):
                    self._validate_against_schema(schema=items, payload=value, path=f"{path}[{index}]", errors=errors)

    def score(
        self,
        *,
        mutation_id: str,
        changed_files: Sequence[Mapping[str, Any] | str],
        base_risk_score: float = 0.0,
        generated_at: str | None = None,
    ) -> MutationRiskReport:
        normalized_changes: list[dict[str, Any]] = []
        for item in changed_files:
            if isinstance(item, str):
                normalized_changes.append({"path": item, "changed_lines": 1, "ast_relevant_change": True})
            else:
                normalized_changes.append(dict(item))

        file_scores = tuple(self._score_file(change) for change in sorted(normalized_changes, key=lambda item: str(item.get("path") or "")))
        if file_scores:
            aggregate = sum(score.score for score in file_scores) / len(file_scores)
        else:
            aggregate = 0.0
        score = round(min(1.0, max(float(base_risk_score), aggregate)), 6)
        threshold = float(self._thresholds["promotion_block_threshold"])
        report = MutationRiskReport(
            schema_version="1.0",
            mutation_id=mutation_id,
            generated_at=generated_at or now_iso(),
            score=score,
            threshold=threshold,
            threshold_exceeded=score > threshold,
            file_scores=file_scores,
        )
        payload = report.to_payload()
        digest = self._stable_sha256(payload)
        report = MutationRiskReport(**{**payload, "report_sha256": digest, "file_scores": tuple(file_scores)})
        self._validate_report_payload(report.to_payload())
        self._write_report(report)
        self._emit_report_event(report)
        return report

    def _write_report(self, report: MutationRiskReport) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{report.mutation_id}.json"
        payload = report.to_payload()
        path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return path

    def _emit_report_event(self, report: MutationRiskReport) -> None:
        report_path = self.output_dir / f"{report.mutation_id}.json"
        if report_path.is_relative_to(ROOT_DIR):
            serialized_path = str(report_path.relative_to(ROOT_DIR))
        else:
            serialized_path = str(report_path)
        payload = {
            "mutation_id": report.mutation_id,
            "schema_version": report.schema_version,
            "report_path": serialized_path,
            "report_sha256": report.report_sha256,
            "score": report.score,
            "threshold": report.threshold,
            "threshold_exceeded": report.threshold_exceeded,
        }
        journal.write_entry(agent_id="system", action="mutation_risk_report_generated.v1", payload=payload)
        journal.append_tx(tx_type="mutation_risk_report_generated.v1", payload=payload)


__all__ = ["FileRiskScore", "MutationRiskReport", "MutationRiskScorer", "RISK_THRESHOLDS_PATH"]
