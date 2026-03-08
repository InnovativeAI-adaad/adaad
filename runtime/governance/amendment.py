# SPDX-License-Identifier: Apache-2.0
"""Constitutional amendment proposal and approval workflow."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Sequence

from runtime import ROOT_DIR
from runtime import constitution
from runtime.constitution import CONSTITUTION_VERSION, reload_constitution_policy
from runtime.governance.amendment_pipeline import AmendmentPipeline
from runtime.governance.deterministic_filesystem import read_file_deterministic
from runtime.governance.foundation import RuntimeDeterminismProvider, default_provider, require_replay_safe_provider
from runtime.governance.review_quality import record_review_quality
from runtime.tools.execution_contract import ToolExecutionRequest, evaluate_governance_tool_findings, execute_tool_request
from security.ledger import journal


@dataclass
class AmendmentProposal:
    proposal_id: str
    proposer: str
    timestamp: str
    old_policy_hash: str
    new_policy_text: str
    new_policy_hash: str
    rationale: str
    approvals: List[str]
    rejections: List[str]
    status: str
    phase_transitions: List[dict[str, Any]]


class AmendmentEngine:
    def __init__(
        self,
        proposals_dir: Path | None = None,
        required_approvals: int = 2,
        rejection_threshold: int = 1,
        provider: RuntimeDeterminismProvider | None = None,
        *,
        replay_mode: str = "off",
        simulation_tool_requests: Sequence[ToolExecutionRequest] | None = None,
    ):
        self.proposals_dir = proposals_dir or (ROOT_DIR / "runtime" / "governance" / "proposals")
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.required_approvals = required_approvals
        self.rejection_threshold = rejection_threshold
        self.provider = provider or default_provider()
        self.simulation_tool_requests = tuple(simulation_tool_requests or ())
        require_replay_safe_provider(self.provider, replay_mode=replay_mode)

    def propose_amendment(self, *, proposer: str, new_policy_text: str, rationale: str, old_policy_hash: str) -> AmendmentProposal:
        new_hash = hashlib.sha256(new_policy_text.encode("utf-8")).hexdigest()
        proposal_id = f"amendment-{self.provider.format_utc('%Y%m%dT%H%M%SZ')}"
        proposal = AmendmentProposal(
            proposal_id=proposal_id,
            proposer=proposer,
            timestamp=self.provider.iso_now(),
            old_policy_hash=old_policy_hash,
            new_policy_text=new_policy_text,
            new_policy_hash=new_hash,
            rationale=rationale,
            approvals=[],
            rejections=[],
            status="pending",
            phase_transitions=[],
        )
        self._save_proposal(proposal)
        journal.write_entry(
            agent_id="system",
            action="constitutional_amendment_proposed",
            payload={
                "proposal_id": proposal_id,
                "proposer": proposer,
                "policy_hash_change": f"{old_policy_hash[:8]}→{new_hash[:8]}",
                "rationale": rationale,
            },
        )
        return proposal

    def approve_amendment(
        self,
        proposal_id: str,
        approver: str,
        *,
        comment_count: int = 0,
        overridden: bool = False,
    ) -> AmendmentProposal:
        proposal = self._load_proposal(proposal_id)
        if proposal.status not in {"pending", "approved"}:
            return proposal
        if approver not in proposal.approvals:
            proposal.approvals.append(approver)

        self._run_pipeline(proposal)
        record_review_quality(
            {
                "mutation_id": proposal.proposal_id,
                "review_id": f"approve:{proposal.proposal_id}:{approver}",
                "reviewer": approver,
                "latency_seconds": self._review_latency_seconds(proposal.timestamp),
                "comment_count": comment_count,
                "decision": "approve",
                "overridden": overridden,
                "context": "constitutional_amendment",
            }
        )
        self._save_proposal(proposal)
        return proposal

    def reject_amendment(
        self,
        proposal_id: str,
        rejector: str,
        *,
        comment_count: int = 0,
        overridden: bool = False,
    ) -> AmendmentProposal:
        proposal = self._load_proposal(proposal_id)
        if rejector not in proposal.rejections:
            proposal.rejections.append(rejector)

        self._run_pipeline(proposal)
        self._save_proposal(proposal)
        record_review_quality(
            {
                "mutation_id": proposal.proposal_id,
                "review_id": f"reject:{proposal.proposal_id}:{rejector}",
                "reviewer": rejector,
                "latency_seconds": self._review_latency_seconds(proposal.timestamp),
                "comment_count": comment_count,
                "decision": "reject",
                "overridden": overridden,
                "context": "constitutional_amendment",
            }
        )
        if proposal.status == "rejected":
            journal.write_entry(
                agent_id="system",
                action="constitutional_amendment_rejected",
                payload={"proposal_id": proposal_id, "rejector": rejector},
            )
        return proposal

    def _run_pipeline(self, proposal: AmendmentProposal) -> None:
        pipeline = AmendmentPipeline(
            required_approvals=self.required_approvals,
            rejection_threshold=self.rejection_threshold,
            proposal_id=proposal.proposal_id,
            transition_log=proposal.phase_transitions,
            run_simulation_gate=self._simulation_gate,
            apply_effectuation=lambda: self._effectuate_amendment(proposal),
        )
        result = pipeline.run(
            approvals=len(proposal.approvals),
            rejections=len(proposal.rejections),
            status=proposal.status,
        )
        proposal.status = result.proposal_status

    def _simulation_gate(self) -> dict[str, Any]:
        # pre-ADAAD-8 simulation integration is advisory by default; when tool checks
        # are configured, failures are machine-classified into block/warn/advisory tiers.
        if not self.simulation_tool_requests:
            return {"ok": True, "mode": "advisory_pre_adaad_8", "tool_findings": []}

        results = [execute_tool_request(request) for request in self.simulation_tool_requests]
        classification = evaluate_governance_tool_findings(results)
        classification["mode"] = "tool_contract_governance"
        return classification

    def _effectuate_amendment(self, proposal: AmendmentProposal) -> bool:
        if constitution.POLICY_HASH == proposal.new_policy_hash:
            journal.write_entry(
                agent_id="system",
                action="constitutional_amendment_already_effective",
                payload={"proposal_id": proposal.proposal_id, "new_policy_hash": proposal.new_policy_hash},
            )
            return False

        staged_policy = self.proposals_dir / f"{proposal.proposal_id}.policy.json"
        staged_policy.write_text(proposal.new_policy_text, encoding="utf-8")
        try:
            new_hash = reload_constitution_policy(path=staged_policy)
        except TypeError:
            new_hash = reload_constitution_policy()
        if new_hash != proposal.new_policy_hash:
            raise RuntimeError("policy_hash_mismatch_after_apply")
        journal.write_entry(
            agent_id="system",
            action="constitutional_amendment_applied",
            payload={
                "proposal_id": proposal.proposal_id,
                "approvers": ",".join(proposal.approvals),
                "new_policy_hash": new_hash,
                "version": CONSTITUTION_VERSION,
            },
        )
        return True

    def _review_latency_seconds(self, submitted_ts: str) -> float:
        try:
            start = datetime.fromisoformat(submitted_ts.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        now = self.provider.now_utc().astimezone(timezone.utc)
        delta = (now - start).total_seconds()
        return round(max(0.0, float(delta)), 6)

    def _load_proposal(self, proposal_id: str) -> AmendmentProposal:
        path = self.proposals_dir / f"{proposal_id}.json"
        data = json.loads(read_file_deterministic(path))
        data.setdefault("phase_transitions", [])
        return AmendmentProposal(**data)

    def _save_proposal(self, proposal: AmendmentProposal) -> None:
        path = self.proposals_dir / f"{proposal.proposal_id}.json"
        path.write_text(json.dumps(proposal.__dict__, indent=2), encoding="utf-8")


__all__ = ["AmendmentProposal", "AmendmentEngine"]
