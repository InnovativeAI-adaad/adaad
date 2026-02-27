# SPDX-License-Identifier: Apache-2.0
"""Adapter that bridges Proposal contracts to concrete LLM provider calls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from runtime.intelligence.llm_provider import LLMProviderClient
from runtime.intelligence.proposal import ProposalModule, ProposalTargetFile
from runtime.intelligence.strategy import StrategyDecision, StrategyInput


@dataclass(frozen=True)
class ProposalAdapter:
    """LLM-backed proposal adapter with replay/evidence-friendly payload capture."""

    provider_client: LLMProviderClient
    proposal_module: ProposalModule

    def build_from_strategy(self, *, context: StrategyInput, strategy: StrategyDecision):
        system_prompt = (
            "You are an AGM proposal engine. Return strict JSON with fields: "
            "title, summary, estimated_impact, real_diff, target_files, projected_impact, metadata."
        )
        user_prompt = (
            f"cycle_id={context.cycle_id}\n"
            f"strategy_id={strategy.strategy_id}\n"
            f"rationale={strategy.rationale}\n"
            f"signals={json.dumps(context.signals, sort_keys=True)}"
        )

        provider_result = self.provider_client.request_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        payload = provider_result.payload if isinstance(provider_result.payload, dict) else {}

        return self.proposal_module.build(
            cycle_id=context.cycle_id,
            strategy_id=strategy.strategy_id,
            rationale=self._read_string(payload, "summary") or strategy.rationale,
            real_diff=self._read_string(payload, "real_diff") or "",
            target_files=self._parse_target_files(payload.get("target_files")),
            projected_impact=self._read_mapping(payload, "projected_impact"),
            evidence={
                "llm_provider_result": provider_result.to_dict(),
                "llm_raw_payload": payload,
            },
            metadata={
                "cycle_id": context.cycle_id,
                "strategy_id": strategy.strategy_id,
                **self._read_mapping(payload, "metadata"),
            },
        )

    @staticmethod
    def _read_string(payload: Mapping[str, Any], key: str) -> str | None:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
        return None

    @staticmethod
    def _read_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    @staticmethod
    def _parse_target_files(value: Any) -> tuple[ProposalTargetFile, ...]:
        if not isinstance(value, list):
            return ()

        parsed: list[ProposalTargetFile] = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            path = item.get("path")
            if not isinstance(path, str) or not path.strip():
                continue
            parsed.append(
                ProposalTargetFile(
                    path=path,
                    language=item.get("language") if isinstance(item.get("language"), str) else None,
                    exists=item.get("exists") if isinstance(item.get("exists"), bool) else None,
                    content=item.get("content") if isinstance(item.get("content"), str) else None,
                    metadata=dict(item.get("metadata")) if isinstance(item.get("metadata"), Mapping) else {},
                )
            )
        return tuple(parsed)
