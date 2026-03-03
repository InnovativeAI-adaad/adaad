from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from runtime.governance.branch_manager import BranchManager, json_dump
from runtime.governance.foundation.determinism import RuntimeDeterminismProvider, default_provider


@dataclass
class StageBranchCreator:
    """Create intake stage branches and append provenance manifest fields."""

    branch_manager: BranchManager = field(default_factory=BranchManager)
    provider: RuntimeDeterminismProvider = field(default_factory=default_provider)

    def _build_branch_name(self, intake_id: str, scan_id: str) -> str:
        token = self.provider.next_id(label=f"stage-branch:{intake_id}:{scan_id}", length=12)
        return f"stage-{intake_id}-{token}"

    def create_stage_branch(
        self,
        *,
        intake_id: str,
        scan_id: str,
        sources: Sequence[str] | None = None,
        blocked: bool = False,
        fail_closed: bool = True,
    ) -> Path:
        if blocked and fail_closed:
            raise PermissionError("mutation_blocked_fail_closed")

        branch_name = self._build_branch_name(intake_id=intake_id, scan_id=scan_id)
        branch_path = self.branch_manager.create_branch(branch_name)
        manifest_path = branch_path / ".manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["created_at"] = self.provider.iso_now()
        payload["intake_id"] = intake_id
        payload["scan_id"] = scan_id
        payload["sources"] = list(sources) if sources is not None else list(payload.get("sources", []))
        manifest_path.write_text(json_dump(payload), encoding="utf-8")
        return branch_path


__all__ = ["StageBranchCreator"]
