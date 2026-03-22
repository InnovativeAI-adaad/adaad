# SPDX-License-Identifier: Apache-2.0
"""Innovation #1 — Invariant Discovery Engine.

Watches failed mutations, extracts patterns, proposes new constitutional rules.
The system discovers its own laws from its own failure history.
"""
from __future__ import annotations
import hashlib, json, re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MIN_PATTERN_FREQUENCY: int = 5
MIN_PRECISION: float = 0.80  # rule fires correctly this % of the time

@dataclass
class DiscoveredRule:
    rule_id: str
    pattern_description: str
    failure_pattern: str          # what the failing mutations have in common
    observed_frequency: int
    estimated_precision: float
    proposed_yaml: str            # ready-to-insert constitution.yaml fragment
    discovery_epoch: str
    evidence_mutation_ids: list[str] = field(default_factory=list)
    status: str = "proposed"      # proposed → human_review → accepted | rejected

    @property
    def digest(self) -> str:
        payload = json.dumps({"rule_id": self.rule_id,
                               "pattern": self.failure_pattern}, sort_keys=True)
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


class InvariantDiscoveryEngine:
    """Mines governance failures → proposes new constitutional invariants."""

    def __init__(self, ledger_path: Path = Path("data/discovered_rules.jsonl"),
                 min_frequency: int = MIN_PATTERN_FREQUENCY,
                 min_precision: float = MIN_PRECISION):
        self.ledger_path = Path(ledger_path)
        self.min_frequency = min_frequency
        self.min_precision = min_precision
        self._known_patterns: set[str] = set()

    def analyze_failures(self, rejected_records: list[dict[str, Any]],
                         epoch_id: str) -> list[DiscoveredRule]:
        """Mine rejected_records for recurring constitutional gaps."""
        if not rejected_records:
            return []

        # Extract failure patterns
        pattern_counts: Counter = Counter()
        pattern_examples: dict[str, list[str]] = {}

        for r in rejected_records:
            rules = r.get("failed_rules", []) or []
            reasons = r.get("reason_codes", []) or []
            mid = r.get("mutation_id", "")
            # Pair-wise co-occurrence of failed rules (compound patterns)
            for rule in rules + reasons:
                if rule:
                    pattern_counts[rule] += 1
                    pattern_examples.setdefault(rule, []).append(mid)
            # Target file patterns
            for f in r.get("changed_files", []):
                fpath = str(f) if not isinstance(f, str) else f
                if "runtime/" in fpath:
                    layer = fpath.split("/")[1] if "/" in fpath else fpath
                    key = f"targets_runtime_{layer}"
                    pattern_counts[key] += 1
                    pattern_examples.setdefault(key, []).append(mid)

        discovered: list[DiscoveredRule] = []
        for pattern, count in pattern_counts.most_common():
            if count < self.min_frequency:
                break
            if pattern in self._known_patterns:
                continue
            total_with_pattern = count
            total_failures = len(rejected_records)
            precision = total_with_pattern / total_failures if total_failures else 0.0
            if precision < self.min_precision:
                continue

            rule_id = f"DISC-{epoch_id.replace('-','')[:8]}-{len(discovered):02d}"
            yaml_fragment = self._generate_rule_yaml(rule_id, pattern)
            rule = DiscoveredRule(
                rule_id=rule_id,
                pattern_description=f"Failures matching pattern: {pattern}",
                failure_pattern=pattern,
                observed_frequency=count,
                estimated_precision=round(precision, 4),
                proposed_yaml=yaml_fragment,
                discovery_epoch=epoch_id,
                evidence_mutation_ids=pattern_examples.get(pattern, [])[:5],
            )
            discovered.append(rule)
            self._known_patterns.add(pattern)
            self._persist(rule)

        return discovered

    def _generate_rule_yaml(self, rule_id: str, pattern: str) -> str:
        safe_name = re.sub(r'[^a-z0-9_]', '_', pattern.lower())[:40]
        return (
            f'{{"name": "{safe_name}", "enabled": true, "severity": "warning",\n'
            f' "tier_overrides": {{"SANDBOX": "advisory"}},\n'
            f' "reason": "Auto-discovered pattern: {pattern} (rule {rule_id}). '
            f'Requires human review before promotion to blocking.",\n'
            f' "validator": "discovered_{safe_name}"}}'
        )

    def pending_rules(self) -> list[DiscoveredRule]:
        if not self.ledger_path.exists():
            return []
        rules = []
        for line in self.ledger_path.read_text().splitlines():
            if line.strip():
                try:
                    d = json.loads(line)
                    if d.get("status") == "proposed":
                        rules.append(DiscoveredRule(**d))
                except Exception:
                    pass
        return rules

    def _persist(self, rule: DiscoveredRule) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        import dataclasses
        entry = dataclasses.asdict(rule)
        with self.ledger_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


__all__ = ["InvariantDiscoveryEngine", "DiscoveredRule",
           "MIN_PATTERN_FREQUENCY", "MIN_PRECISION"]
