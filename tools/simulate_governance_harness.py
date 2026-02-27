# SPDX-License-Identifier: Apache-2.0
"""Deterministic governance simulation harness for constitutional rule evaluation."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.agents.mutation_request import MutationRequest
from runtime import constitution


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    kind: str
    description: str
    config: dict[str, Any]


@dataclass(frozen=True)
class PolicySummary:
    policy_label: str
    policy_hash: str
    total_requests: int
    passed: int
    blocked: int
    pass_rate: float
    block_rate: float
    warning_class_frequencies: dict[str, int]
    time_window_instability_delta: list[float]


@dataclass(frozen=True)
class SimulationSummary:
    scenario: str
    seed: int
    tier: str
    concurrent_streams: int
    total_requests: int
    unique_envelope_digests: int
    per_policy: dict[str, PolicySummary]
    candidate_regression_delta: dict[str, Any]


try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    from runtime.constitution import yaml  # fallback parser used by constitution module


def _load_scenarios(path: Path) -> dict[str, ScenarioDefinition]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(raw)
    elif path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(raw)
    else:
        raise ValueError(f"unsupported scenario file format: {path.suffix}")

    scenarios = payload.get("scenarios") if isinstance(payload, dict) else None
    if not isinstance(scenarios, list):
        raise ValueError("scenario file must define a top-level 'scenarios' list")

    parsed: dict[str, ScenarioDefinition] = {}
    for item in scenarios:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        kind = str(item.get("kind", "")).strip()
        if not name or not kind:
            continue
        parsed[name] = ScenarioDefinition(
            name=name,
            kind=kind,
            description=str(item.get("description", "")),
            config=dict(item.get("config") or {}),
        )
    if not parsed:
        raise ValueError("scenario file did not contain any valid scenarios")
    return parsed


def _request(index: int, *, stream_id: int, signature: str, nonce: str, epoch_id: str, value: int) -> MutationRequest:
    return MutationRequest(
        agent_id=f"test_subject_{stream_id}",
        generation_ts="2026-01-01T00:00:00Z",
        intent=f"simulate-{stream_id}-{index}",
        ops=[{"op": "replace", "path": "/value", "value": value}],
        signature=signature,
        nonce=nonce,
        epoch_id=epoch_id,
    )


def _build_request(index: int, stream_id: int, scenario: ScenarioDefinition, rng: random.Random) -> MutationRequest:
    base_nonce = f"nonce-{stream_id:03d}-{index:05d}"
    signature = "cryovant-dev-test"
    epoch_id = f"sim-epoch-{index // 100}"
    value = index

    if scenario.kind == "benign":
        return _request(index, stream_id=stream_id, signature=signature, nonce=base_nonce, epoch_id=epoch_id, value=value)

    if scenario.kind == "malformed_signatures":
        malformed_ratio = float(scenario.config.get("malformed_ratio", 0.2))
        if rng.random() < malformed_ratio:
            signature = f"invalid-signature-{stream_id}-{index}"

    if scenario.kind == "burst_failures":
        burst_every = max(1, int(scenario.config.get("burst_every", 10)))
        burst_size = max(1, int(scenario.config.get("burst_size", 3)))
        if index % burst_every < burst_size:
            signature = f"invalid-burst-{stream_id}-{index}"

    if scenario.kind == "replay_drifts":
        replay_ratio = float(scenario.config.get("replay_ratio", 0.35))
        if index > 2 and rng.random() < replay_ratio:
            nonce = f"nonce-{stream_id:03d}-{(index - rng.randint(1, min(index, 5))):05d}"
        else:
            nonce = base_nonce
        epoch_jitter = int(scenario.config.get("epoch_jitter", 2))
        epoch_id = f"sim-epoch-{max(0, index // 100 - rng.randint(0, epoch_jitter))}"
        return _request(index, stream_id=stream_id, signature=signature, nonce=nonce, epoch_id=epoch_id, value=value)

    if scenario.kind == "high_volume_mutation_spikes":
        spike_every = max(1, int(scenario.config.get("spike_every", 25)))
        spike_magnitude = max(10, int(scenario.config.get("spike_magnitude", 2000)))
        if index % spike_every == 0:
            value = spike_magnitude + index

    return _request(index, stream_id=stream_id, signature=signature, nonce=base_nonce, epoch_id=epoch_id, value=value)


def _windowed_instability(outcomes: list[bool], window_size: int) -> list[float]:
    if window_size <= 0:
        return []
    rates: list[float] = []
    for start in range(0, len(outcomes), window_size):
        window = outcomes[start : start + window_size]
        if not window:
            continue
        rates.append(sum(1 for item in window if item) / len(window))
    return [round(rates[idx] - rates[idx - 1], 6) for idx in range(1, len(rates))]


@contextmanager
def _policy_scope(policy_path: Path | None):
    if policy_path is None:
        yield
        return

    original_path = constitution.POLICY_PATH
    constitution.reload_constitution_policy(path=policy_path)
    try:
        yield
    finally:
        constitution.reload_constitution_policy(path=original_path)


def _run_for_policy(
    *,
    policy_label: str,
    policy_path: Path | None,
    scenario: ScenarioDefinition,
    request_count: int,
    concurrent_streams: int,
    tier: constitution.Tier,
    seed: int,
    window_size: int,
) -> tuple[PolicySummary, int]:
    warning_classes: Counter[str] = Counter()
    outcomes: list[bool] = []
    digests: set[str] = set()

    with _policy_scope(policy_path):
        rng = random.Random(seed)
        for idx in range(request_count):
            stream_id = idx % concurrent_streams
            request = _build_request(idx, stream_id, scenario, rng)
            verdict = constitution.evaluate_mutation(request, tier)
            passed = bool(verdict.get("passed"))
            outcomes.append(passed)
            warning_classes.update(str(item) for item in verdict.get("warnings", []))
            digests.add(str(verdict.get("governance_envelope", {}).get("digest", "")))

        total = len(outcomes)
        passed_count = sum(1 for item in outcomes if item)
        blocked_count = total - passed_count
        summary = PolicySummary(
            policy_label=policy_label,
            policy_hash=str(constitution.POLICY_HASH),
            total_requests=total,
            passed=passed_count,
            blocked=blocked_count,
            pass_rate=round(passed_count / max(1, total), 6),
            block_rate=round(blocked_count / max(1, total), 6),
            warning_class_frequencies=dict(sorted(warning_classes.items())),
            time_window_instability_delta=_windowed_instability(outcomes, window_size),
        )
    return summary, len(digests)


def run_simulation(
    *,
    count: int,
    tier: constitution.Tier,
    scenario: ScenarioDefinition,
    concurrent_streams: int,
    seed: int,
    window_size: int,
    baseline_policy: Path | None = None,
    candidate_policy: Path | None = None,
) -> SimulationSummary:
    per_policy: dict[str, PolicySummary] = {}
    digest_counts: dict[str, int] = {}

    baseline_summary, baseline_digests = _run_for_policy(
        policy_label="baseline",
        policy_path=baseline_policy,
        scenario=scenario,
        request_count=count,
        concurrent_streams=concurrent_streams,
        tier=tier,
        seed=seed,
        window_size=window_size,
    )
    per_policy["baseline"] = baseline_summary
    digest_counts["baseline"] = baseline_digests

    if candidate_policy is not None:
        candidate_summary, candidate_digests = _run_for_policy(
            policy_label="candidate",
            policy_path=candidate_policy,
            scenario=scenario,
            request_count=count,
            concurrent_streams=concurrent_streams,
            tier=tier,
            seed=seed,
            window_size=window_size,
        )
        per_policy["candidate"] = candidate_summary
        digest_counts["candidate"] = candidate_digests

    regression_delta: dict[str, Any] = {}
    if "candidate" in per_policy:
        baseline = per_policy["baseline"]
        candidate = per_policy["candidate"]
        regression_delta = {
            "pass_rate_delta": round(candidate.pass_rate - baseline.pass_rate, 6),
            "block_rate_delta": round(candidate.block_rate - baseline.block_rate, 6),
            "warning_class_deltas": {
                key: candidate.warning_class_frequencies.get(key, 0) - baseline.warning_class_frequencies.get(key, 0)
                for key in sorted(set(baseline.warning_class_frequencies) | set(candidate.warning_class_frequencies))
            },
        }

    return SimulationSummary(
        scenario=scenario.name,
        seed=seed,
        tier=tier.name,
        concurrent_streams=concurrent_streams,
        total_requests=count,
        unique_envelope_digests=sum(digest_counts.values()),
        per_policy=per_policy,
        candidate_regression_delta=regression_delta,
    )


def _as_json(summary: SimulationSummary) -> str:
    payload = asdict(summary)
    payload["per_policy"] = {key: asdict(value) for key, value in summary.per_policy.items()}
    return json.dumps(payload, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic governance simulation harness.")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--tier", choices=[tier.name for tier in constitution.Tier], default="SANDBOX")
    parser.add_argument("--scenario-file", default="tools/governance_scenarios.json")
    parser.add_argument("--scenario", required=True, help="Scenario name from scenario file.")
    parser.add_argument("--concurrent-streams", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--window-size", type=int, default=100)
    parser.add_argument("--baseline-policy", default="", help="Optional baseline policy artifact path.")
    parser.add_argument("--candidate-policy", default="", help="Optional candidate policy artifact path.")
    parser.add_argument("--output", default="", help="Optional JSON output file path.")
    args = parser.parse_args(argv)

    scenario_map = _load_scenarios(Path(args.scenario_file))
    if args.scenario not in scenario_map:
        available = ", ".join(sorted(scenario_map))
        raise SystemExit(f"Unknown scenario '{args.scenario}'. Available: {available}")

    summary = run_simulation(
        count=max(1, args.count),
        tier=constitution.Tier[args.tier],
        scenario=scenario_map[args.scenario],
        concurrent_streams=max(1, args.concurrent_streams),
        seed=args.seed,
        window_size=max(1, args.window_size),
        baseline_policy=Path(args.baseline_policy) if args.baseline_policy else None,
        candidate_policy=Path(args.candidate_policy) if args.candidate_policy else None,
    )
    payload = _as_json(summary)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
