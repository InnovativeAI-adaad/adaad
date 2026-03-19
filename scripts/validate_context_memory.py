#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate context memory schema and stale-reference alignment."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = REPO_ROOT / "context/context.json"
SCHEMA_PATH = REPO_ROOT / "context/context.schema.json"
PROCESSION_PATH = REPO_ROOT / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _validate_node(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []

    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(instance, dict):
            return [f"{path}:type_error:expected_object"]
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}:missing_required:{key}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if schema.get("additionalProperties", True) is False and key not in properties:
                errors.append(f"{path}:unexpected_property:{key}")
            if key in properties and isinstance(properties[key], dict):
                errors.extend(_validate_node(value, properties[key], f"{path}.{key}"))

    elif schema_type == "array":
        if not isinstance(instance, list):
            return [f"{path}:type_error:expected_array"]
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            errors.append(f"{path}:min_items:{min_items}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, value in enumerate(instance):
                errors.extend(_validate_node(value, item_schema, f"{path}[{idx}]"))

    elif schema_type == "string":
        if not isinstance(instance, str):
            errors.append(f"{path}:type_error:expected_string")
        elif isinstance(schema.get("minLength"), int) and len(instance) < schema["minLength"]:
            errors.append(f"{path}:min_length:{schema['minLength']}")

    if "$ref" in schema and isinstance(schema["$ref"], str):
        ref = schema["$ref"]
        if ref.startswith("#/$defs/"):
            ref_key = ref.split("/")[-1]
            defs = ROOT_SCHEMA.get("$defs", {})
            ref_schema = defs.get(ref_key)
            if isinstance(ref_schema, dict):
                errors.extend(_validate_node(instance, ref_schema, path))
            else:
                errors.append(f"{path}:invalid_ref:{ref}")

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and instance not in enum_values:
        errors.append(f"{path}:enum_error")

    return errors


def _require_existing_paths(errors: list[str], values: list[str], field_name: str) -> None:
    for value in values:
        if not (REPO_ROOT / value).exists():
            errors.append(f"{field_name}:missing_path:{value}")


def _extract_pattern(text: str, pattern: str, label: str) -> str | None:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_package_version() -> str | None:
    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    return _extract_pattern(text, r'^version\s*=\s*"([^"]+)"\s*$', "pyproject_version")


def main() -> int:
    global ROOT_SCHEMA
    try:
        ROOT_SCHEMA = _load_json(SCHEMA_PATH)
        context = _load_json(CONTEXT_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"context_memory_validation:failed:load_error:{exc}")
        return 1

    errors = _validate_node(context, ROOT_SCHEMA)

    authoritative_docs = context.get("authoritative_docs", [])
    if isinstance(authoritative_docs, list):
        _require_existing_paths(errors, [str(p) for p in authoritative_docs if isinstance(p, str)], "authoritative_docs")

    for entry in context.get("module_ownership", []):
        if isinstance(entry, dict):
            for key in ("module_path", "owner_doc"):
                value = entry.get(key)
                if isinstance(value, str) and not (REPO_ROOT / value).exists():
                    errors.append(f"module_ownership:{key}:missing_path:{value}")

    for entry in context.get("integration_points", []):
        if isinstance(entry, dict):
            source_doc = entry.get("source_doc")
            if isinstance(source_doc, str) and not (REPO_ROOT / source_doc).exists():
                errors.append(f"integration_points:source_doc:missing_path:{source_doc}")
            paths = entry.get("paths", [])
            if isinstance(paths, list):
                _require_existing_paths(errors, [str(p) for p in paths if isinstance(p, str)], "integration_points.paths")

    procession_text = PROCESSION_PATH.read_text(encoding="utf-8")
    expected_next_pr = _extract_pattern(procession_text, r'expected_next_pr:\s*"([^"]+)"', "expected_next_pr")
    expected_phase = _extract_pattern(procession_text, r'expected_active_phase:\s*"([^"]+)"', "expected_active_phase")

    active = context.get("active", {}) if isinstance(context.get("active"), dict) else {}
    if expected_next_pr and active.get("expected_next_pr_identifier") != expected_next_pr:
        errors.append("active:stale_reference:expected_next_pr_identifier")
    if expected_phase and active.get("phase") != expected_phase:
        errors.append("active:stale_reference:phase")

    package_version = _load_package_version()
    if package_version:
        expected_context_version = f"v{package_version}"
        if active.get("version") != expected_context_version:
            errors.append("active:stale_reference:version")

    if errors:
        print("context_memory_validation:failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("context_memory_validation:ok")
    return 0


ROOT_SCHEMA: dict[str, Any] = {}

if __name__ == "__main__":
    raise SystemExit(main())
