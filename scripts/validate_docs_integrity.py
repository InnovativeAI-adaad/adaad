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
        description="Validate markdown local links/images, image alt text, and optional image-weight markers."
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format. Defaults to json for CI readability.",
    )
    parser.add_argument(
        "--roots",
        nargs="+",
        default=None,
        help="Optional markdown roots (files or directories) relative to repo root.",
    )
    parser.add_argument(
        "--enforce-image-weight-markers",
        action="store_true",
        help=(
            "Enable optional checks that HTML <img> tags in human-facing docs include "
            "approved low/critical image-weight markers."
        ),
    )
    parser.add_argument(
        "--image-weight-roots",
        nargs="+",
        default=["README.md", "docs"],
        help=(
            "Markdown files/directories (relative to repo root) used for optional image-weight marker checks. "
            "Defaults to README.md and docs/."
        ),
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



def _has_approved_image_weight_marker(attrs: dict[str, str]) -> bool:
    class_tokens = {token.strip().lower() for token in attrs.get("class", "").split() if token.strip()}
    if {"img-low-weight", "img-critical"} & class_tokens:
        return True
    marker = attrs.get("data-img-weight", "").strip().lower()
    return marker in {"low", "critical"}



def _parse_html_attributes(tag_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_PATTERN.finditer(tag_text):
        attrs[match.group(1).lower()] = match.group(3)
    return attrs


def _scan_html_image_tag(markdown_file: Path, line_number: int, tag_text: str, enforce_image_weight_markers: bool = False) -> list[dict[str, object]]:
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

    if enforce_image_weight_markers and not _has_approved_image_weight_marker(attrs):
        findings.append(
            {
                "kind": "missing_image_weight_marker",
                "file": str(markdown_file.relative_to(ROOT)),
                "line": line_number,
                "target": source or "<html-img>",
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


def _scan_markdown_file(markdown_file: Path, enforce_image_weight_markers: bool = False) -> list[dict[str, object]]:
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
            findings.extend(_scan_html_image_tag(markdown_file, line_number, tag_match.group(0), enforce_image_weight_markers=enforce_image_weight_markers))
    return findings


def _resolve_markdown_targets(roots: list[str] | None) -> list[Path]:
    if roots is None:
        return sorted(ROOT.rglob("*.md"))

    targets: set[Path] = set()
    for root in roots:
        candidate = (ROOT / root).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"markdown root not found: {root}")
        if candidate.is_file():
            if candidate.suffix.lower() == ".md":
                targets.add(candidate)
            continue
        targets.update(path for path in candidate.rglob("*.md") if path.is_file())
    return sorted(targets)


def _collect_findings(
    roots: list[str] | None = None,
    enforce_image_weight_markers: bool = False,
    image_weight_roots: list[str] | None = None,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    image_weight_scope_files: set[Path] = set()
    if enforce_image_weight_markers:
        image_weight_scope_files = set(_resolve_markdown_targets(image_weight_roots))

    for markdown_file in _resolve_markdown_targets(roots):
        scoped_marker_check = enforce_image_weight_markers and markdown_file in image_weight_scope_files
        findings.extend(_scan_markdown_file(markdown_file, enforce_image_weight_markers=scoped_marker_check))
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
        findings = _collect_findings(
            roots=args.roots,
            enforce_image_weight_markers=args.enforce_image_weight_markers,
            image_weight_roots=args.image_weight_roots,
        )
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
