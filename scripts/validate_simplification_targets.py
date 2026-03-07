#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed validator for simplification complexity/safety targets."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="governance/simplification_targets.json",
        help="Path to simplification target contract JSON.",
    )
    return parser.parse_args()


def _module_name(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _collect_imports(py_file: Path) -> set[str]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _extract_env_default(path: Path, env_name: str) -> int:
    pattern = re.compile(rf"{re.escape(env_name)}\",\s*\"(\d+)\"")
    text = path.read_text(encoding="utf-8")
    match = pattern.search(text)
    if not match:
        raise ValueError(f"missing_env_default:{env_name}")
    return int(match.group(1))


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    contract_path = repo_root / args.contract
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    errors: list[str] = []

    py_files = [
        path
        for path in repo_root.rglob("*.py")
        if ".git" not in path.parts and "__pycache__" not in path.parts
    ]
    imports_by_file = {path.relative_to(repo_root): _collect_imports(path) for path in py_files}

    # 1) File size and fan-in budgets.
    for budget in contract.get("critical_file_budgets", []):
        rel = Path(str(budget["path"]))
        target = repo_root / rel
        if not target.exists():
            errors.append(f"missing_file:{rel}")
            continue

        lines = _line_count(target)
        max_lines = int(budget["max_lines"])
        if lines > max_lines:
            errors.append(f"line_budget_exceeded:{rel}:{lines}>{max_lines}")

        target_module = _module_name(rel)
        fan_in = 0
        for file_rel, imports in imports_by_file.items():
            if file_rel == rel:
                continue
            if any(item == target_module or item.startswith(f"{target_module}.") for item in imports):
                fan_in += 1

        max_fan_in = int(budget["max_fan_in"])
        if fan_in > max_fan_in:
            errors.append(f"fan_in_budget_exceeded:{rel}:{fan_in}>{max_fan_in}")

    # 2) Legacy-path reduction target + no-regression threshold.
    legacy = contract["legacy_path_reduction"]
    baseline = int(legacy["baseline_branches"])
    target_reduction_percent = float(legacy["target_reduction_percent"])
    target_max = int(legacy["target_max_branches"])
    enforced_max = int(legacy["enforced_max_branches"])

    computed_target_max = int(baseline * (1.0 - (target_reduction_percent / 100.0)))
    if target_max > computed_target_max:
        errors.append(
            f"legacy_target_misaligned:target_max={target_max}:computed_max={computed_target_max}"
        )

    pattern = re.compile(str(legacy["pattern"]), re.IGNORECASE)
    legacy_count = 0
    for root in legacy.get("search_roots", []):
        for py_file in (repo_root / root).rglob("*.py"):
            legacy_count += len(pattern.findall(py_file.read_text(encoding="utf-8")))

    if legacy_count > enforced_max:
        errors.append(f"legacy_regression:{legacy_count}>{enforced_max}")

    # 3) Unified metrics-schema producer coverage.
    metrics = contract["metrics_schema_adoption"]
    producers = [Path(item) for item in metrics.get("producers", [])]
    required_import = str(metrics["required_import"])
    required_constructor = str(metrics["required_constructor"])
    covered = 0
    for producer in producers:
        content = (repo_root / producer).read_text(encoding="utf-8")
        has_import = required_import in content
        has_constructor = required_constructor in content
        if has_import and has_constructor:
            covered += 1
        else:
            errors.append(f"metrics_schema_not_adopted:{producer}")

    required_coverage = float(metrics["required_coverage_percent"])
    coverage_percent = (100.0 * covered / len(producers)) if producers else 100.0
    if coverage_percent < required_coverage:
        errors.append(f"metrics_coverage_below_target:{coverage_percent:.2f}<{required_coverage:.2f}")

    # 4) Runtime cost targets and experiment caps.
    constitution = json.loads((repo_root / "runtime/governance/constitution.yaml").read_text(encoding="utf-8"))
    limits = constitution.get("resource_bounds_policy", {}).get("limits", {})
    caps = contract["runtime_cost_targets"]["constitution_limits"]

    if int(limits.get("memory_mb", 0)) > int(caps["memory_mb_max"]):
        errors.append(f"memory_cap_exceeded:{limits.get('memory_mb')}>{caps['memory_mb_max']}")
    if int(limits.get("cpu_seconds", 0)) > int(caps["cpu_seconds_max"]):
        errors.append(f"cpu_cap_exceeded:{limits.get('cpu_seconds')}>{caps['cpu_seconds_max']}")
    if int(limits.get("wall_seconds", 0)) > int(caps["wall_seconds_max"]):
        errors.append(f"wall_cap_exceeded:{limits.get('wall_seconds')}>{caps['wall_seconds_max']}")

    beast_file = repo_root / "app/beast_mode_loop.py"
    beast_caps = contract["runtime_cost_targets"]["experiment_caps"]
    cycle_budget = _extract_env_default(beast_file, "ADAAD_BEAST_CYCLE_BUDGET")
    mutation_quota = _extract_env_default(beast_file, "ADAAD_BEAST_MUTATION_QUOTA")
    if cycle_budget > int(beast_caps["beast_cycle_budget_max"]):
        errors.append(f"beast_cycle_budget_exceeded:{cycle_budget}>{beast_caps['beast_cycle_budget_max']}")
    if mutation_quota > int(beast_caps["beast_mutation_quota_max"]):
        errors.append(f"beast_mutation_quota_exceeded:{mutation_quota}>{beast_caps['beast_mutation_quota_max']}")

    report = {
        "contract": str(contract_path.relative_to(repo_root)),
        "legacy_count": legacy_count,
        "metrics_coverage_percent": round(coverage_percent, 2),
        "status": "ok" if not errors else "error",
        "errors": errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if errors:
        raise SystemExit("simplification_target_validation_failed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
