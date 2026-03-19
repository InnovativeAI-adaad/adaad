#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "docs/assets/qr/registry.json"

REQUIRED_UTM = {
    "utm_source": "qr",
    "utm_campaign": "install_tracks_2026q2",
}


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
        if not (ROOT / asset_path).exists():
            findings.append(
                {
                    "target": target_id,
                    "kind": "missing_asset",
                    "detail": f"asset not found: {asset_path}",
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
