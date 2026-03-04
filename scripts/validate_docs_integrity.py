#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MD_LINK_PATTERN = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
HTML_IMG_PATTERN = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ATTR_PATTERN = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(["\'])(.*?)\2')


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate markdown local links/images and markdown image alt text."
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format. Defaults to json for CI readability.",
    )
    return parser


def _normalize_destination(raw_destination: str) -> str:
    destination = raw_destination.strip()
    if not destination:
        return ""
    if destination.startswith("<") and ">" in destination:
        destination = destination[1 : destination.index(">")].strip()
    else:
        destination = destination.split(maxsplit=1)[0]
    return destination.strip()


def _is_local_target(destination: str) -> bool:
    if not destination or destination.startswith("#"):
        return False
    split = urlsplit(destination)
    if split.scheme or split.netloc:
        return False
    return True


def _resolve_target(markdown_file: Path, destination: str) -> Path:
    path_component = destination.split("#", 1)[0].split("?", 1)[0]
    return (markdown_file.parent / path_component).resolve()




def _parse_html_attributes(tag_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_PATTERN.finditer(tag_text):
        attrs[match.group(1).lower()] = match.group(3)
    return attrs


def _scan_html_image_tag(markdown_file: Path, line_number: int, tag_text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    attrs = _parse_html_attributes(tag_text)
    if "src" not in attrs:
        return findings

    alt_value = attrs.get("alt")
    source = _normalize_destination(attrs.get("src", ""))

    if alt_value is None or not alt_value.strip():
        findings.append(
            {
                "kind": "missing_html_image_alt_text",
                "file": str(markdown_file.relative_to(ROOT)),
                "line": line_number,
                "target": source,
            }
        )

    if _is_local_target(source):
        target_path = _resolve_target(markdown_file, source)
        if not target_path.exists():
            findings.append(
                {
                    "kind": "missing_local_target",
                    "file": str(markdown_file.relative_to(ROOT)),
                    "line": line_number,
                    "target": source,
                }
            )

    return findings


def _scan_markdown_file(markdown_file: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    text = markdown_file.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in MD_LINK_PATTERN.finditer(line):
            is_image = bool(match.group(1))
            label = match.group(2)
            destination = _normalize_destination(match.group(3))

            if is_image and not label.strip():
                findings.append(
                    {
                        "kind": "missing_image_alt_text",
                        "file": str(markdown_file.relative_to(ROOT)),
                        "line": line_number,
                        "target": destination,
                    }
                )

            if not _is_local_target(destination):
                continue

            target_path = _resolve_target(markdown_file, destination)
            if not target_path.exists():
                findings.append(
                    {
                        "kind": "missing_local_target",
                        "file": str(markdown_file.relative_to(ROOT)),
                        "line": line_number,
                        "target": destination,
                    }
                )

        for tag_match in HTML_IMG_PATTERN.finditer(line):
            findings.extend(_scan_html_image_tag(markdown_file, line_number, tag_match.group(0)))
    return findings


def _collect_findings() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for markdown_file in sorted(ROOT.rglob("*.md")):
        findings.extend(_scan_markdown_file(markdown_file))
    return sorted(findings, key=lambda item: (str(item["file"]), int(item["line"]), str(item["kind"]), str(item["target"])))


def _emit(findings: list[dict[str, object]], output_format: str) -> None:
    if output_format == "json":
        payload = {
            "validator": "docs_integrity",
            "ok": not findings,
            "findings": findings,
        }
        print(json.dumps(payload, sort_keys=True))
        return

    if findings:
        for finding in findings:
            print(
                "{kind}:{file}:{line}:{target}".format(
                    kind=finding["kind"],
                    file=finding["file"],
                    line=finding["line"],
                    target=finding["target"],
                )
            )
        return
    print("docs_integrity_ok")


def main() -> int:
    args = _build_parser().parse_args()
    findings: list[dict[str, object]] = []
    try:
        findings = _collect_findings()
    except Exception as exc:  # fail closed
        findings = [
            {
                "kind": "validator_error",
                "file": "<internal>",
                "line": 0,
                "target": f"{exc.__class__.__name__}:{exc}",
            }
        ]

    _emit(findings=findings, output_format=args.format)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
