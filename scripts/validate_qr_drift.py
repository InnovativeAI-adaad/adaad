#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "docs/assets/qr/registry.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate QR asset URL drift against canonical query ledger entries."
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
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=5.0,
        help="HTTP timeout for URL reachability checks.",
    )
    parser.add_argument(
        "--skip-reachability",
        action="store_true",
        help="Skip network reachability checks and only validate mappings/params.",
    )
    parser.add_argument(
        "--allow-unreachable",
        action="store_true",
        help="Do not fail validation when URL checks are unreachable (still reported in findings).",
    )
    return parser


def _normalize_query_map(url: str) -> dict[str, list[str]]:
    query_pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    query_map: dict[str, list[str]] = {}
    for key, value in query_pairs:
        query_map.setdefault(key, []).append(value)
    return {key: sorted(values) for key, values in sorted(query_map.items())}


def _normalize_expected_params(expected: dict[str, Any]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, raw_value in sorted(expected.items()):
        if isinstance(raw_value, list):
            normalized[key] = sorted(str(item) for item in raw_value)
        else:
            normalized[key] = [str(raw_value)]
    return normalized


def _resolve_expected_params(target: dict[str, Any], canonical_ledger: dict[str, Any]) -> dict[str, Any] | None:
    target_id = str(target.get("id", ""))
    placement = str(target.get("placement", ""))

    by_id = canonical_ledger.get("by_id", {})
    if isinstance(by_id, dict) and target_id in by_id and isinstance(by_id[target_id], dict):
        return by_id[target_id]

    by_placement = canonical_ledger.get("by_placement", {})
    if isinstance(by_placement, dict) and placement in by_placement and isinstance(by_placement[placement], dict):
        return by_placement[placement]
    return None


def _status_class(status_code: int | None) -> str:
    if status_code is None:
        return "unreachable"
    bucket = status_code // 100
    return f"{bucket}xx"


def _check_url(url: str, timeout_seconds: float) -> tuple[int | None, str | None]:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.getcode(), None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        pass

    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.getcode(), None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception as exc:  # pragma: no cover - transport-level failures are environment dependent
        return None, f"{type(exc).__name__}: {exc}"


def validate_qr_drift(
    registry_path: Path,
    *,
    timeout_seconds: float = 5.0,
    check_reachability: bool = True,
    fail_on_unreachable: bool = True,
) -> tuple[bool, dict[str, Any]]:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    targets = payload.get("targets", [])
    canonical_ledger = payload.get("canonical_query_ledger", {})

    if not isinstance(targets, list):
        return False, {"assets": [], "findings": [{"asset_id": "<registry>", "kind": "invalid_schema", "detail": "targets must be a list"}]}

    assets: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for target in targets:
        if not isinstance(target, dict) or target.get("active") is not True:
            continue

        asset_id = str(target.get("id", "<unknown>"))
        asset_path = str(target.get("asset_path", ""))
        target_url = str(target.get("target_url", ""))

        status_code: int | None = None
        error: str | None = None
        if check_reachability and target_url:
            status_code, error = _check_url(target_url, timeout_seconds)

        asset_row = {
            "asset_id": asset_id,
            "asset_path": asset_path,
            "target_url": target_url,
            "status_code": status_code,
            "status_class": _status_class(status_code) if check_reachability else "skipped",
            "reachable": bool(status_code is not None and status_code < 500),
        }
        if error:
            asset_row["error"] = error
        assets.append(asset_row)

        if not asset_path or not (ROOT / asset_path).exists():
            findings.append(
                {
                    "asset_id": asset_id,
                    "kind": "missing_asset",
                    "expected_params": {},
                    "observed_params": {},
                    "detail": f"asset not found: {asset_path or '<missing>'}",
                }
            )

        expected_raw = _resolve_expected_params(target, canonical_ledger)
        observed = _normalize_query_map(target_url) if target_url else {}

        if expected_raw is None:
            findings.append(
                {
                    "asset_id": asset_id,
                    "kind": "missing_canonical_ledger_entry",
                    "expected_params": {},
                    "observed_params": observed,
                    "detail": "No canonical ledger mapping for target id/placement",
                }
            )
        else:
            expected = _normalize_expected_params(expected_raw)
            if observed != expected:
                findings.append(
                    {
                        "asset_id": asset_id,
                        "kind": "query_param_mismatch",
                        "expected_params": expected,
                        "observed_params": observed,
                        "detail": "URL query params differ from canonical ledger entry",
                    }
                )

        if check_reachability and status_code is None:
            findings.append(
                {
                    "asset_id": asset_id,
                    "kind": "unreachable_url",
                    "expected_params": _normalize_expected_params(expected_raw) if isinstance(expected_raw, dict) else {},
                    "observed_params": observed,
                    "detail": error or "URL could not be reached",
                }
            )

    findings.sort(key=lambda row: (row["asset_id"], row["kind"]))
    hard_fail_findings = [
        finding
        for finding in findings
        if fail_on_unreachable or finding["kind"] != "unreachable_url"
    ]
    return not hard_fail_findings, {"assets": assets, "findings": findings}


def main() -> int:
    args = _build_parser().parse_args()
    ok, report = validate_qr_drift(
        Path(args.registry),
        timeout_seconds=args.timeout_seconds,
        check_reachability=not args.skip_reachability,
        fail_on_unreachable=not args.allow_unreachable,
    )
    payload = {"validator": "qr_drift", "ok": ok, **report}

    if args.format == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        if ok:
            print("QR drift validation passed.")
        else:
            print("QR drift validation failed:")
            for finding in report["findings"]:
                print(
                    f"- [{finding['kind']}] {finding['asset_id']}: "
                    f"expected={json.dumps(finding['expected_params'], sort_keys=True)} "
                    f"observed={json.dumps(finding['observed_params'], sort_keys=True)}"
                )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
