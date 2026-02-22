# SPDX-License-Identifier: Apache-2.0
"""Validation for incoming MCP mutation proposals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from app.agents.mutation_request import MutationRequest
from runtime.constitution import Tier, evaluate_mutation

SCHEMA_PATH = Path("schemas/llm_mutation_proposal.v1.json")
TIER0_PATH_PREFIXES = ("runtime/", "security/")
TIER0_EXACT_PATHS = {"app/main.py", "app/mutation_executor.py", "runtime/constitution.py"}


class ProposalValidationError(ValueError):
    def __init__(self, status_code: int, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def _load_schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> None:
    required = set(schema.get("required") or [])
    missing = [field for field in required if field not in payload]
    if missing:
        raise ProposalValidationError(400, "schema_validation_failed", f"missing_required:{','.join(sorted(missing))}")

    if schema.get("additionalProperties") is False:
        allowed = set((schema.get("properties") or {}).keys())
        extras = sorted(set(payload.keys()) - allowed)
        if extras:
            raise ProposalValidationError(400, "schema_validation_failed", f"unexpected_fields:{','.join(extras)}")


def _is_tier0_path(path: str) -> bool:
    normalized = str(path or "").strip()
    if normalized in TIER0_EXACT_PATHS:
        return True
    return any(normalized.startswith(prefix) for prefix in TIER0_PATH_PREFIXES)


def _contains_banned_eval(payload: Any) -> bool:
    if isinstance(payload, dict):
        return any(_contains_banned_eval(v) for v in payload.values())
    if isinstance(payload, list):
        return any(_contains_banned_eval(v) for v in payload)
    if isinstance(payload, str):
        return "eval" in payload
    return False


def validate_proposal(raw_payload: Dict[str, Any]) -> Tuple[MutationRequest, Dict[str, Any]]:
    schema = _load_schema()

    # 1. schema validation
    _validate_schema(raw_payload, schema)

    payload = dict(raw_payload)
    # 2. unconditional authority override
    payload["authority_level"] = "governor-review"

    # 3. Tier-0 path check
    elevation_token = str(payload.get("elevation_token") or "").strip()
    for target in payload.get("targets") or []:
        if _is_tier0_path(str((target or {}).get("path") or "")) and not elevation_token:
            raise ProposalValidationError(403, "tier0_escalation_required", "human elevation_token required")

    # pre-check for banned token before constitutional evaluation contract output
    if _contains_banned_eval(payload.get("ops") or []) or _contains_banned_eval(payload.get("targets") or []):
        raise ProposalValidationError(422, "pre_check_failed", "banned token: eval")

    request = MutationRequest.from_dict(payload)

    # 4. constitutional pre-check
    verdict = evaluate_mutation(request, Tier.STABLE)
    if not verdict.get("passed", False):
        blocking = [v for v in verdict.get("verdicts", []) if str(v.get("severity", "")).lower() == "blocking" and not v.get("ok", False)]
        if blocking:
            raise ProposalValidationError(422, "pre_check_failed", json.dumps(verdict.get("verdicts", []), sort_keys=True))

    # 5. return tuple
    return request, verdict


__all__ = ["ProposalValidationError", "validate_proposal"]
