# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Iterable, List

from adaad.agents.architect_graph_v1 import ArchitectGraph, GraphDict
from runtime.api.app_layer import BranchManager, GateCertifier, push_to_dashboard
from security.ledger.journal import append_tx
from security import cryovant

MutationFn = Callable[[Path], None]
_AUTH_FAILURE_REASON_PREFIX = "architect_governor_auth_failed"
_LOGGER = logging.getLogger(__name__)


def _default_mutation(_: Path) -> None:
    return None


def _validate_targets(targets: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    for t in targets:
        t = (t or "").strip().replace("\\", "/")
        pp = PurePosixPath(t)
        if not t or pp.is_absolute() or ".." in pp.parts:
            raise PermissionError(f"Invalid target path: {t!r}")
        cleaned.append(str(pp))
    return cleaned


@dataclass
class ArchitectGovernor:
    branch_manager: BranchManager = field(default_factory=BranchManager)
    certifier: GateCertifier = field(default_factory=GateCertifier)

    def snapshot(self) -> GraphDict:
        return ArchitectGraph().build()

    def execute_refactor(
        self,
        branch_name: str,
        targets: Iterable[str],
        cryovant_token: str,
        mutate: MutationFn = _default_mutation,
    ) -> Dict[str, object]:
        token = (cryovant_token or "").strip()
        if not token:
            raise PermissionError("cryovant_token required for autonomous refactor.")
        try:
            token_valid = cryovant.verify_governance_token(token)
        except cryovant.TokenExpiredError:
            _LOGGER.warning(
                "ArchitectGovernor.execute_refactor auth failed",
                extra={"reason_code": f"{_AUTH_FAILURE_REASON_PREFIX}:token_expired", "error_type": "TokenExpiredError"},
            )
            raise PermissionError("Invalid cryovant_token: token_expired.") from None
        except (cryovant.GovernanceTokenError, cryovant.MissingSigningKeyError) as exc:
            _LOGGER.warning(
                "ArchitectGovernor.execute_refactor auth failed",
                extra={
                    "reason_code": f"{_AUTH_FAILURE_REASON_PREFIX}:token_verification_error",
                    "error_type": type(exc).__name__,
                },
            )
            raise PermissionError("Invalid cryovant_token: token_verification_error.") from None
        if not token_valid:
            raise PermissionError("Invalid cryovant_token.")

        safe_targets = _validate_targets(targets)
        if not safe_targets:
            raise ValueError("targets must contain at least one relative path")

        branch = self.branch_manager.create_branch(branch_name)
        target_paths = [branch / rel for rel in safe_targets]
        relative_targets = list(safe_targets)

        for path in target_paths:
            mutate(path)

        certificates = []
        for path in target_paths:
            cert = self.certifier.certify(path, {"branch": branch_name, "cryovant_token": token})
            if isinstance(cert.get("metadata"), dict):
                cert["metadata"].pop("cryovant_token", None)
            certificates.append(cert)

        success = all(cert.get("passed") for cert in certificates)
        payload = {
            "branch": str(branch),
            "targets": relative_targets,
            "certificates": certificates,
        }

        if success:
            promoted = self.branch_manager.promote(branch_name, relative_targets)
            payload["promoted"] = [str(p) for p in promoted]
            push_to_dashboard("ARCHITECT_EVOLUTION_SUCCESS", payload)
            append_tx("ARCHITECT_EVOLUTION_SUCCESS", payload)
        else:
            push_to_dashboard("ARCHITECT_EVOLUTION_FAILED", payload)
            append_tx("ARCHITECT_EVOLUTION_FAILED", payload)
        return {"success": success, **payload}


__all__ = ["ArchitectGovernor"]
