#!/usr/bin/env python3
"""Validate primary test-lane marker coverage across the pytest suite."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Iterable

import pytest

PRIMARY_MARKERS = (
    "autonomous_critical",
    "governance_gate",
    "regression_standard",
    "dev_only",
)


@dataclass(frozen=True)
class MarkerIssue:
    nodeid: str
    markers: tuple[str, ...]


def _primary_markers(item: pytest.Item) -> tuple[str, ...]:
    found: list[str] = []
    for marker in item.iter_markers():
        if marker.name in PRIMARY_MARKERS and marker.name not in found:
            found.append(marker.name)
    return tuple(found)


class _InventoryPlugin:
    def __init__(self) -> None:
        self.issues: list[MarkerIssue] = []
        self.total_collected = 0

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        self.total_collected = len(items)
        for item in items:
            markers = _primary_markers(item)
            if len(markers) != 1:
                self.issues.append(MarkerIssue(nodeid=item.nodeid, markers=markers))


def _format_markers(markers: Iterable[str]) -> str:
    materialized = tuple(markers)
    return ", ".join(materialized) if materialized else "<none>"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-issues", type=int, default=200, help="Maximum issue lines printed.")
    args = parser.parse_args()

    plugin = _InventoryPlugin()
    exit_code = pytest.main(["tests", "--collect-only", "-p", "no:terminal"], plugins=[plugin])
    if exit_code != 0:
        return exit_code

    if plugin.total_collected == 0:
        print("[marker-inventory] No tests were collected.")
        return 1

    if plugin.issues:
        print(
            "[marker-inventory] FAIL: primary lane marker coverage is incomplete "
            f"({len(plugin.issues)} / {plugin.total_collected} tests invalid)."
        )
        for issue in plugin.issues[: args.max_issues]:
            print(f" - {issue.nodeid}: {_format_markers(issue.markers)}")
        if len(plugin.issues) > args.max_issues:
            remaining = len(plugin.issues) - args.max_issues
            print(f" ... {remaining} additional issue(s) omitted.")
        return 1

    print(f"[marker-inventory] PASS: {plugin.total_collected} / {plugin.total_collected} tests have exactly one primary lane marker.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
