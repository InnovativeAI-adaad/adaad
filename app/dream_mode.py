# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Dream mode handles mutation cycles for agents.

Phase 39: RuntimeDeterminismProvider injection — all clock and token calls
are now routed through the provider, making DreamMode fully replay-safe and
audit-verifiable.  Strict/audit tiers reject non-deterministic providers at
construction time via ``require_replay_safe_provider()``.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from adaad.agents.base_agent import stage_offspring
from adaad.agents.discovery import agent_path_from_id, iter_agent_dirs, resolve_agent_id
from runtime.api.app_layer import metrics, deterministic_context, deterministic_token
from runtime.governance.foundation import (
    RuntimeDeterminismProvider,
    SeededDeterminismProvider,
    SystemDeterminismProvider,
)
from runtime.governance.foundation.determinism import require_replay_safe_provider
from security import cryovant

ELEMENT_ID = "Fire"

_DEFAULT_DISCOVERY_SAMPLE_SIZE = 3


def _read_sample_size() -> int:
    """Read ADAAD_DREAM_DISCOVERY_SAMPLE_SIZE from env; fall back to default on invalid."""
    raw = os.getenv("ADAAD_DREAM_DISCOVERY_SAMPLE_SIZE", "").strip()
    if not raw:
        return _DEFAULT_DISCOVERY_SAMPLE_SIZE
    try:
        return int(raw)
    except (ValueError, TypeError):
        return _DEFAULT_DISCOVERY_SAMPLE_SIZE


def _include_full_tasks() -> bool:
    return os.getenv("ADAAD_METRICS_INCLUDE_FULL_TASKS", "").strip().lower() in {"1", "true", "yes", "on"}


class DreamMode:
    """
    Drives creative mutation cycles.

    Parameters
    ----------
    agents_root
        Root directory containing per-agent subdirectories.
    lineage_dir
        Directory used by the lineage ledger.
    replay_mode
        One of ``"off"``, ``"strict"``.  ``"strict"`` requires a deterministic
        provider and produces bit-identical output across replays.
    recovery_tier
        Governance recovery tier string.  ``"audit"``, ``"governance"``, and
        ``"critical"`` require a deterministic provider.
    provider
        :class:`~runtime.governance.foundation.RuntimeDeterminismProvider`
        instance.  Defaults to :class:`SystemDeterminismProvider`.
        Strict replay and audit tiers reject non-deterministic providers at
        construction time.
    """

    def __init__(
        self,
        agents_root: Path,
        lineage_dir: Path,
        *,
        replay_mode: str | None = None,
        recovery_tier: str | None = None,
        provider: "RuntimeDeterminismProvider | None" = None,
    ) -> None:
        self.agents_root = agents_root
        self.lineage_dir = lineage_dir
        self.replay_mode = (replay_mode or "off").strip().lower()
        self.recovery_tier = (recovery_tier or "standard").strip().lower()

        # Auto-provision a deterministic provider for strict/audit tiers when none
        # is explicitly supplied — preserves backward-compat for callers that rely
        # on strict mode without injecting a provider.
        _needs_det = (
            self.replay_mode == "strict"
            or self.recovery_tier in {"audit", "governance", "critical"}
        )
        if provider is None and _needs_det:
            import os as _os
            _seed = _os.getenv("ADAAD_DETERMINISTIC_SEED", "adaad-dream-default")
            self.provider: RuntimeDeterminismProvider = SeededDeterminismProvider(seed=_seed)
        else:
            self.provider = provider or SystemDeterminismProvider()

        # Fail-closed: reject non-deterministic providers for strict/audit contexts
        require_replay_safe_provider(
            self.provider,
            replay_mode=self.replay_mode,
            recovery_tier=self.recovery_tier,
        )

        # Entropy budget instance — reset by tests for strict replay idempotency
        from runtime.api.app_layer import EntropyBudget
        self.entropy_budget = EntropyBudget()

    @staticmethod
    def _clamp_aggression(value: float) -> float:
        """Clamp aggression coefficient to [0.0, 1.0]."""
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _read_json(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _extract_dream_scope(meta: Dict[str, object]) -> Optional[Dict[str, object]]:
        scope = meta.get("dream_scope")
        if not isinstance(scope, dict):
            return None
        allow = scope.get("allow", [])
        if isinstance(allow, str):
            allow = [allow]
        if not isinstance(allow, list):
            return None
        if not scope.get("enabled", True):
            return None
        if "mutation" not in allow:
            return None
        return scope

    def discover_tasks(self) -> List[str]:
        """Discover mutation-ready agents.

        Emits a ``dream_discovery`` metrics event with a controlled payload:
        - Always includes ``task_count`` and ``task_sample`` (capped at
          ``ADAAD_DREAM_DISCOVERY_SAMPLE_SIZE``, default 3).
        - Includes the full ``tasks`` list only when
          ``ADAAD_METRICS_INCLUDE_FULL_TASKS=1`` is set.
        """
        tasks: List[str] = []
        for agent_dir in iter_agent_dirs(self.agents_root):
            agent_id = resolve_agent_id(agent_dir, self.agents_root)
            meta = self._read_json(agent_dir / "meta.json")
            if not self._extract_dream_scope(meta):
                metrics.log(
                    event_type="dream_scope_blocked",
                    payload={"agent": agent_id},
                    level="WARNING",
                    element_id=ELEMENT_ID,
                )
                continue
            tasks.append(agent_id)

        sample_size = _read_sample_size()
        payload: Dict[str, object] = {
            "task_count": len(tasks),
            "task_sample": tasks[:sample_size],
        }
        if _include_full_tasks():
            payload["tasks"] = tasks

        metrics.log(event_type="dream_discovery", payload=payload, level="INFO")
        return tasks

    def run_cycle(
        self,
        agent_id: Optional[str] = None,
        *,
        epoch_id: str | None = None,
        bundle_id: str | None = None,
    ) -> Dict[str, str]:
        """Run a single dream mutation cycle.

        Dream only stages candidates; it does not promote.  All clock and token
        calls are routed through ``self.provider`` for determinism/replay safety.
        """
        metrics.log(
            event_type="evolution_cycle_start",
            payload={"agent": agent_id},
            level="INFO",
            element_id=ELEMENT_ID,
        )
        tasks = self.discover_tasks()
        if not tasks:
            metrics.log(
                event_type="evolution_cycle_end",
                payload={"agent": agent_id, "status": "skipped"},
                level="WARNING",
                element_id=ELEMENT_ID,
            )
            return {"status": "skipped", "reason": "no tasks"}

        selected = agent_id or tasks[0]
        if not cryovant.validate_ancestry(selected):
            metrics.log(
                event_type="evolution_cycle_end",
                payload={"agent": selected, "status": "blocked"},
                level="ERROR",
                element_id=ELEMENT_ID,
            )
            return {"status": "blocked", "agent": selected}

        agent_dir = agent_path_from_id(selected, self.agents_root)
        meta = self._read_json(agent_dir / "meta.json")
        dream_scope = self._extract_dream_scope(meta)
        if not dream_scope:
            metrics.log(
                event_type="dream_scope_blocked",
                payload={"agent": selected},
                level="ERROR",
                element_id=ELEMENT_ID,
            )
            return {"status": "blocked", "agent": selected, "reason": "dream_scope_missing"}

        metrics.log(
            event_type="evolution_cycle_decision",
            payload={"selected_agent": selected},
            level="INFO",
            element_id=ELEMENT_ID,
        )

        # Token generation: provider-routed for full replay-safety.
        # Strict/deterministic mode: use module-level deterministic_token() which
        # is keyed on epoch/bundle/agent — identical result across replays.
        # Non-strict mode: provider.next_token() — wall-clock / system entropy.
        if deterministic_context(replay_mode=self.replay_mode, recovery_tier=self.recovery_tier):
            token = deterministic_token(
                epoch_id=str(epoch_id or ""),
                bundle_id=str(bundle_id or ""),
                agent_id=selected,
                label="dream_token",
            )
        else:
            token = self.provider.next_token(label="dream_token")

        mutation_content = f"{selected}-mutation-{token}"

        # issued_at always routed through provider — enables clock injection in
        # tests and strict epoch-pinned deterministic replay.
        handoff_contract = {
            "schema_version": "1.0",
            "issued_at": self.provider.iso_now(),
            "issuer": "DreamMode",
            "agent": selected,
            "dream_scope": dream_scope,
            "constraints": {"sandboxed": True},
        }

        staged_path = stage_offspring(
            parent_id=selected,
            content=mutation_content,
            lineage_dir=self.lineage_dir,
            dream_mode=True,
            sandboxed=True,
            handoff_contract=handoff_contract,
        )
        metrics.log(
            event_type="dream_candidate_generated",
            payload={"agent": selected, "staged_path": str(staged_path)},
            level="INFO",
            element_id=ELEMENT_ID,
        )
        metrics.log(
            event_type="evolution_cycle_validation",
            payload={"agent": selected, "result": "validated"},
            level="INFO",
            element_id=ELEMENT_ID,
        )
        metrics.log(
            event_type="evolution_cycle_end",
            payload={"agent": selected, "status": "completed"},
            level="INFO",
            element_id=ELEMENT_ID,
        )
        return {"status": "completed", "agent": selected, "staged_path": str(staged_path)}
