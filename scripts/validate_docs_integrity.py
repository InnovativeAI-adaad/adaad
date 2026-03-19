#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MD_LINK_PATTERN = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
HTML_IMG_PATTERN = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ATTR_PATTERN = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(["\'])(.*?)\2')
SVG_IMAGE_TAG_PATTERN = re.compile(r"<image\b[^>]*>", re.IGNORECASE)

GOVERNANCE_ALWAYS_ROOTS: frozenset[str] = frozenset(
    {
        "docs/governance",
        "docs/comms",
        "docs/release",
        "docs/releases",
    }
)
SCOPED_DOC_EXTENSIONS: frozenset[str] = frozenset({".md", ".html", ".svg", ".txt", ".rst"})


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
        "--changed-files",
        default=None,
        help="Optional newline-delimited changed-files list for scoped validation.",
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


def _scan_svg_asset_file(svg_file: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    text = svg_file.read_text(encoding="utf-8")
    relative_file = str(svg_file.relative_to(ROOT))
    for line_number, line in enumerate(text.splitlines(), start=1):
        for tag_match in SVG_IMAGE_TAG_PATTERN.finditer(line):
            attrs = _parse_html_attributes(tag_match.group(0))
            href = _normalize_destination(attrs.get("href", ""))
            if not href or not _is_local_target(href):
                continue

            if href.startswith("docs/assets/"):
                findings.append(
                    {
                        "kind": "bad_svg_intra_asset_href_path",
                        "file": relative_file,
                        "line": line_number,
                        "target": href,
                    }
                )

            target_path = _resolve_target(svg_file, href)
            if not target_path.exists():
                findings.append(
                    {
                        "kind": "missing_local_target",
                        "file": relative_file,
                        "line": line_number,
                        "target": href,
                    }
                )
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


def _collect_svg_targets() -> list[Path]:
    docs_assets = ROOT / "docs/assets"
    if not docs_assets.exists():
        return []
    return sorted(docs_assets.rglob("*.svg"))


def _fatal(code: str, message: str) -> None:
    print(json.dumps({"event": code, "message": message}, sort_keys=True))
    raise SystemExit(1)


def _resolve_targets(args: argparse.Namespace) -> tuple[list[Path], str]:
    if args.changed_files is None:
        markdown_targets = _resolve_markdown_targets(args.roots)
        svg_targets = _collect_svg_targets()
        return sorted(set(markdown_targets + svg_targets)), "full"

    changed_files_path = Path(args.changed_files)
    if not changed_files_path.exists():
        _fatal("DOCS_INTEGRITY_ERROR_CHANGED_FILES_MISSING", f"--changed-files path does not exist: {changed_files_path}")

    try:
        lines = changed_files_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fatal("DOCS_INTEGRITY_ERROR_CHANGED_FILES_READ", str(exc))

    direct_targets: set[Path] = set()
    governance_roots_to_expand: set[str] = set()

    for raw_line in lines:
        rel = raw_line.strip()
        if not rel:
            continue
        normalized = rel.replace("\\", "/")
        target = (ROOT / normalized).resolve()
        if target.suffix.lower() not in SCOPED_DOC_EXTENSIONS:
            continue
        if normalized.endswith(".svg") and normalized.startswith("docs/assets/") and target.exists():
            direct_targets.add(target)
            continue
        if normalized.endswith(".md") and target.exists():
            direct_targets.add(target)

        for root in GOVERNANCE_ALWAYS_ROOTS:
            if normalized == root or normalized.startswith(f"{root}/"):
                governance_roots_to_expand.add(root)
                break

    for gov_root in sorted(governance_roots_to_expand):
        direct_targets.update(_resolve_markdown_targets([gov_root]))
        gov_assets = ROOT / gov_root
        if gov_assets.exists():
            direct_targets.update(path for path in gov_assets.rglob("*.svg") if path.is_file())

    if not direct_targets:
        return [], "empty-scoped"

    mode = "scoped+gov-always" if governance_roots_to_expand else "scoped"
    return sorted(direct_targets), mode


def _collect_findings_with_metadata(
    roots: list[str] | None = None,
    enforce_image_weight_markers: bool = False,
    image_weight_roots: list[str] | None = None,
    changed_files: str | None = None,
) -> tuple[list[dict[str, object]], str, int]:
    findings: list[dict[str, object]] = []
    image_weight_scope_files: set[Path] = set()
    if enforce_image_weight_markers:
        image_weight_scope_files = set(_resolve_markdown_targets(image_weight_roots))

    args = argparse.Namespace(roots=roots, changed_files=changed_files)
    targets, mode = _resolve_targets(args)

    if mode == "empty-scoped":
        return [], mode, 0

    markdown_targets = [path for path in targets if path.suffix.lower() == ".md"]
    svg_targets = [path for path in targets if path.suffix.lower() == ".svg"]

    for markdown_file in markdown_targets:
        scoped_marker_check = enforce_image_weight_markers and markdown_file in image_weight_scope_files
        findings.extend(_scan_markdown_file(markdown_file, enforce_image_weight_markers=scoped_marker_check))

    for svg_file in svg_targets:
        findings.extend(_scan_svg_asset_file(svg_file))

    findings = sorted(findings, key=lambda item: (str(item["file"]), int(item["line"]), str(item["kind"]), str(item["target"])))
    return findings, mode, len(targets)


def _collect_findings(
    roots: list[str] | None = None,
    enforce_image_weight_markers: bool = False,
    image_weight_roots: list[str] | None = None,
    changed_files: str | None = None,
) -> list[dict[str, object]]:
    findings, _mode, _target_count = _collect_findings_with_metadata(
        roots=roots,
        enforce_image_weight_markers=enforce_image_weight_markers,
        image_weight_roots=image_weight_roots,
        changed_files=changed_files,
    )
    return findings


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
    mode = "full"
    target_count = 0
    try:
        findings, mode, target_count = _collect_findings_with_metadata(
            roots=args.roots,
            changed_files=args.changed_files,
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

    if args.format == "json":
        print(json.dumps({"event": "validation_start", "mode": mode, "target_count": target_count}, sort_keys=True))
    _emit(findings=findings, output_format=args.format)
    if args.format == "json":
        print(json.dumps({"event": "validation_complete", "mode": mode, "errors": len(findings), "files_checked": target_count}, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
