#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "docs/assets/qr/registry.json"

REQUIRED_UTM = {
    "utm_source": "qr",
    "utm_campaign": "install_tracks_2026q2",
}

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DISALLOWED_SVG_TAGS = {"script", "foreignObject", "iframe", "object", "embed", "audio", "video", "image"}
DISALLOWED_ATTR_NAMES = {"href", "xlink:href"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate QR campaign registry attribution and asset coverage."
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Path to QR registry JSON (default: docs/assets/qr/registry.json)",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format.",
    )
    return parser


def _is_managed_redirect(target_url: str, managed_redirect_prefixes: list[str]) -> bool:
    return any(target_url.startswith(prefix) for prefix in managed_redirect_prefixes)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _short_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _validate_svg_safety(asset_file: Path, target_id: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    try:
        tree = ET.parse(asset_file)
    except ET.ParseError as exc:
        return [
            {
                "target": target_id,
                "kind": "svg_parse_error",
                "detail": f"{asset_file.as_posix()}: invalid SVG XML: {exc}",
            }
        ]

    root = tree.getroot()
    if _short_tag(root.tag) != "svg":
        findings.append(
            {
                "target": target_id,
                "kind": "svg_root_must_be_svg",
                "detail": f"{asset_file.as_posix()}: expected root <svg>, found <{_short_tag(root.tag)}>",
            }
        )

    for element in root.iter():
        tag = _short_tag(element.tag)
        if tag in DISALLOWED_SVG_TAGS:
            findings.append(
                {
                    "target": target_id,
                    "kind": "svg_disallowed_tag",
                    "detail": f"{asset_file.as_posix()}: disallowed <{tag}> element (rule: svg_safe_structure)",
                }
            )
        for attr_name, attr_value in element.attrib.items():
            short_attr = _short_tag(attr_name).lower()
            if short_attr.startswith("on"):
                findings.append(
                    {
                        "target": target_id,
                        "kind": "svg_disallowed_attribute",
                        "detail": (
                            f"{asset_file.as_posix()}: disallowed event attribute {short_attr!r} "
                            "(rule: svg_no_event_handlers)"
                        ),
                    }
                )
            if short_attr in DISALLOWED_ATTR_NAMES and str(attr_value).strip():
                value = str(attr_value).strip().lower()
                if value.startswith(("http://", "https://", "javascript:", "data:")):
                    findings.append(
                        {
                            "target": target_id,
                            "kind": "svg_external_reference",
                            "detail": (
                                f"{asset_file.as_posix()}: disallowed external reference in {short_attr!r}: "
                                f"{attr_value!r} (rule: svg_no_external_references)"
                            ),
                        }
                    )

    return findings


def _validate_target(
    target: dict[str, object],
    approved_query_params: set[str],
    managed_redirect_prefixes: list[str],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    target_id = str(target.get("id", "<unknown>"))
    asset_path = str(target.get("asset_path", ""))
    target_url = str(target.get("target_url", ""))

    if not asset_path:
        findings.append({"target": target_id, "kind": "missing_asset_path", "detail": "asset_path is required"})
    else:
        asset_file = ROOT / asset_path
        if not asset_file.exists():
            findings.append(
                {
                    "target": target_id,
                    "kind": "missing_asset",
                    "detail": f"asset not found: {asset_path}",
                }
            )
        else:
            if not asset_path.startswith("docs/assets/qr/"):
                findings.append(
                    {
                        "target": target_id,
                        "kind": "asset_location_violation",
                        "detail": (
                            f"{asset_path}: must be stored under docs/assets/qr/ "
                            "(rule: canonical_qr_asset_location)"
                        ),
                    }
                )
            if not asset_path.endswith(".svg"):
                findings.append(
                    {
                        "target": target_id,
                        "kind": "asset_extension_violation",
                        "detail": (
                            f"{asset_path}: expected .svg extension "
                            "(rule: canonical_qr_asset_extension)"
                        ),
                    }
                )
            expected_basename = f"{target_id.replace('-', '_')}.svg"
            if asset_file.name != expected_basename:
                findings.append(
                    {
                        "target": target_id,
                        "kind": "asset_naming_violation",
                        "detail": (
                            f"{asset_path}: expected file name {expected_basename!r} for target id {target_id!r} "
                            "(rule: canonical_qr_asset_name)"
                        ),
                    }
                )

            findings.extend(_validate_svg_safety(asset_file, target_id))

            expected_hash = str(target.get("asset_sha256", "")).strip()
            if not expected_hash:
                findings.append(
                    {
                        "target": target_id,
                        "kind": "missing_asset_sha256",
                        "detail": (
                            f"{asset_path}: missing asset_sha256 metadata "
                            "(rule: required_asset_integrity_hash)"
                        ),
                    }
                )
            elif SHA256_RE.fullmatch(expected_hash) is None:
                findings.append(
                    {
                        "target": target_id,
                        "kind": "invalid_asset_sha256_format",
                        "detail": (
                            f"{asset_path}: asset_sha256 must match 'sha256:<64 lowercase hex>' "
                            "(rule: required_asset_integrity_hash_format)"
                        ),
                    }
                )
            else:
                actual_hash = _sha256(asset_file)
                if expected_hash != actual_hash:
                    findings.append(
                        {
                            "target": target_id,
                            "kind": "asset_sha256_mismatch",
                            "detail": (
                                f"{asset_path}: declared {expected_hash}, computed {actual_hash} "
                                "(rule: required_asset_integrity_hash_match)"
                            ),
                        }
                    )

    if not target_url:
        findings.append({"target": target_id, "kind": "missing_target_url", "detail": "target_url is required"})
        return findings

    split = urlsplit(target_url)
    if split.scheme not in {"http", "https"}:
        findings.append(
            {
                "target": target_id,
                "kind": "unsupported_scheme",
                "detail": f"unsupported scheme: {split.scheme or '<none>'}",
            }
        )
        return findings

    if _is_managed_redirect(target_url, managed_redirect_prefixes):
        return findings

    query_pairs = parse_qsl(split.query, keep_blank_values=True)
    query_map = {key: value for key, value in query_pairs}
    unknown_params = sorted({key for key, _ in query_pairs if key not in approved_query_params})
    if unknown_params:
        findings.append(
            {
                "target": target_id,
                "kind": "unapproved_query_params",
                "detail": f"found unapproved query params: {', '.join(unknown_params)}",
            }
        )

    for required_key, required_value in REQUIRED_UTM.items():
        if query_map.get(required_key) != required_value:
            findings.append(
                {
                    "target": target_id,
                    "kind": "invalid_required_utm",
                    "detail": f"{required_key} must equal {required_value!r}",
                }
            )

    medium = query_map.get("utm_medium", "")
    if not medium.strip():
        findings.append(
            {
                "target": target_id,
                "kind": "missing_utm_medium",
                "detail": "utm_medium must be set for non-managed redirect targets",
            }
        )

    return findings


def validate_registry(registry_path: Path) -> tuple[bool, list[dict[str, str]]]:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    approved_query_params = set(payload.get("approved_query_params", []))
    managed_redirect_prefixes = list(payload.get("managed_redirect_prefixes", []))
    targets = payload.get("targets", [])

    if not isinstance(targets, list):
        return False, [{"target": "<registry>", "kind": "invalid_schema", "detail": "targets must be a list"}]

    findings: list[dict[str, str]] = []
    active_targets = [target for target in targets if isinstance(target, dict) and target.get("active") is True]

    seen_ids: set[str] = set()
    for target in active_targets:
        target_id = str(target.get("id", "<unknown>"))
        if ID_RE.fullmatch(target_id) is None:
            findings.append(
                {
                    "target": target_id,
                    "kind": "invalid_target_id_format",
                    "detail": "target id must use lowercase kebab-case (rule: canonical_target_id_format)",
                }
            )
        if target_id in seen_ids:
            findings.append(
                {
                    "target": target_id,
                    "kind": "duplicate_target_id",
                    "detail": "active target id must be unique",
                }
            )
        seen_ids.add(target_id)
        findings.extend(_validate_target(target, approved_query_params, managed_redirect_prefixes))

    return not findings, sorted(findings, key=lambda item: (item["target"], item["kind"], item["detail"]))


def main() -> int:
    args = _build_parser().parse_args()
    registry_path = Path(args.registry)
    ok, findings = validate_registry(registry_path)
    if args.format == "json":
        print(json.dumps({"validator": "qr_registry", "ok": ok, "findings": findings}, sort_keys=True))
    else:
        if ok:
            print("QR registry validation passed.")
        else:
            print("QR registry validation failed:")
            for finding in findings:
                print(f"- [{finding['kind']}] {finding['target']}: {finding['detail']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
