# SPDX-License-Identifier: Apache-2.0
"""Phase 63 — Exception Token infrastructure.

Constitutional invariants:
  EXCEP-SCOPE-0   Tokens scoped to single capability + single rule; Tier-0 ineligible.
  EXCEP-HUMAN-0   HUMAN-0 required before any token granted for Tier-1 capabilities.
  EXCEP-TTL-0     Tokens expire at most 3 epochs from grant; non-renewable without new HUMAN-0.
  EXCEP-REVOKE-0  Auto-revocation immediate on any trigger condition; no grace period.

Only AST-COMPLEX-0 is eligible for exception tokens in Phase 63.
Tier-0 capabilities are permanently ineligible.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXCEPTION_TOKEN_MAX_TTL: int = 3          # EXCEP-TTL-0: hard ceiling in epochs
ELIGIBLE_RULE_IDS: frozenset[str] = frozenset({"AST-COMPLEX-0"})  # Phase 63 scope
TIER_0_CAPABILITY_NAMES: frozenset[str] = frozenset({
    "governance.gate",
    "governance.policy",
    "determinism.provider",
})

_LEDGER_PATH = Path(os.getenv("ADAAD_EXCEPTION_LEDGER", "data/exception_tokens.jsonl"))


# ---------------------------------------------------------------------------
# ExceptionToken — immutable schema (EXCEP-SCOPE-0)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExceptionToken:
    """Immutable exception token — time-bounded, capability-scoped.

    token_id = sha256(epoch_id + capability_name + rule_id + scope_hash)
    All fields required; constructed only via ExceptionToken.create().
    """

    token_id: str
    capability_name: str
    rule_id: str
    granted_at_epoch: str
    expires_at_epoch: int          # max granted_epoch_seq + TTL (EXCEP-TTL-0)
    granted_epoch_seq: int         # ordinal epoch number at grant time
    lineage_projection: List[float]
    human_approval_ref: Optional[str]  # required for Tier-1 (EXCEP-HUMAN-0)
    revocation_trigger: str
    revoked: bool = False
    revocation_reason: Optional[str] = None

    @classmethod
    def create(
        cls,
        *,
        capability_name: str,
        rule_id: str,
        granted_at_epoch: str,
        granted_epoch_seq: int,
        lineage_projection: Sequence[float],
        human_approval_ref: Optional[str] = None,
        ttl_epochs: int = EXCEPTION_TOKEN_MAX_TTL,
    ) -> "ExceptionToken":
        """Construct and validate an ExceptionToken.

        Raises ValueError on any EXCEP-SCOPE-0 or EXCEP-TTL-0 violation.
        Raises ValueError if EXCEP-HUMAN-0 is violated (Tier-1 without ref).
        """
        # EXCEP-SCOPE-0: Tier-0 permanently ineligible
        if capability_name in TIER_0_CAPABILITY_NAMES:
            raise ValueError(
                f"EXCEP-SCOPE-0 violation: Tier-0 capability '{capability_name}' "
                "is permanently ineligible for exception tokens"
            )
        # EXCEP-SCOPE-0: only eligible rule IDs
        if rule_id not in ELIGIBLE_RULE_IDS:
            raise ValueError(
                f"EXCEP-SCOPE-0 violation: rule_id '{rule_id}' is not eligible; "
                f"eligible rules: {sorted(ELIGIBLE_RULE_IDS)}"
            )
        # EXCEP-TTL-0: TTL hard ceiling
        if ttl_epochs < 1 or ttl_epochs > EXCEPTION_TOKEN_MAX_TTL:
            raise ValueError(
                f"EXCEP-TTL-0 violation: ttl_epochs={ttl_epochs} outside [1, {EXCEPTION_TOKEN_MAX_TTL}]"
            )
        # EXCEP-HUMAN-0: Tier-1 requires human_approval_ref
        # (Tier-0 already blocked above; all remaining are Tier-1)
        if human_approval_ref is None or not human_approval_ref.strip():
            raise ValueError(
                "EXCEP-HUMAN-0 violation: human_approval_ref required for Tier-1 capability "
                f"'{capability_name}'"
            )

        scope_hash = _scope_hash(capability_name, rule_id, granted_at_epoch)
        token_id = _token_id(granted_at_epoch, capability_name, rule_id, scope_hash)
        expires_at_epoch = granted_epoch_seq + ttl_epochs

        return cls(
            token_id=token_id,
            capability_name=capability_name,
            rule_id=rule_id,
            granted_at_epoch=granted_at_epoch,
            granted_epoch_seq=granted_epoch_seq,
            expires_at_epoch=expires_at_epoch,
            lineage_projection=list(lineage_projection),
            human_approval_ref=human_approval_ref,
            revocation_trigger=(
                "auto-revoke on: lineage_diverges | capability_contract_changes | "
                "test_failure_rate_exceeds_threshold | epoch_window_expires"
            ),
            revoked=False,
            revocation_reason=None,
        )

    def is_active(self, current_epoch_seq: int) -> bool:
        """Return True iff token is not revoked and not expired."""
        return (not self.revoked) and (current_epoch_seq <= self.expires_at_epoch)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_id": self.token_id,
            "capability_name": self.capability_name,
            "rule_id": self.rule_id,
            "granted_at_epoch": self.granted_at_epoch,
            "granted_epoch_seq": self.granted_epoch_seq,
            "expires_at_epoch": self.expires_at_epoch,
            "lineage_projection": self.lineage_projection,
            "human_approval_ref": self.human_approval_ref,
            "revocation_trigger": self.revocation_trigger,
            "revoked": self.revoked,
            "revocation_reason": self.revocation_reason,
        }


# ---------------------------------------------------------------------------
# ExceptionTokenLedger — append-only JSONL; monitors for auto-revocation
# ---------------------------------------------------------------------------

class ExceptionTokenLedger:
    """Append-only exception token ledger with immediate auto-revocation.

    EXCEP-REVOKE-0: revocation is immediate on any trigger; no grace period.
    """

    def __init__(self, ledger_path: Path = _LEDGER_PATH) -> None:
        self._path = ledger_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._tokens: Dict[str, ExceptionToken] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def grant(self, token: ExceptionToken) -> None:
        """Write a new token to the ledger. Raises if token_id already exists."""
        if token.token_id in self._tokens:
            raise ValueError(f"ExceptionTokenLedger: token_id {token.token_id} already exists")
        self._tokens[token.token_id] = token
        self._append({"event": "granted", **token.to_dict()})

    def revoke(self, token_id: str, reason: str) -> None:
        """EXCEP-REVOKE-0: immediate revocation; no grace period."""
        token = self._tokens.get(token_id)
        if token is None:
            raise KeyError(f"ExceptionTokenLedger: unknown token_id {token_id}")
        if token.revoked:
            return  # idempotent
        import dataclasses
        revoked_token = dataclasses.replace(token, revoked=True, revocation_reason=reason)
        self._tokens[token_id] = revoked_token
        self._append({"event": "revoked", "token_id": token_id, "reason": reason})

    def active_tokens_for(
        self, capability_name: str, current_epoch_seq: int
    ) -> List[ExceptionToken]:
        """Return all active (non-revoked, non-expired) tokens for a capability."""
        result = []
        for t in self._tokens.values():
            if t.capability_name == capability_name and t.is_active(current_epoch_seq):
                result.append(t)
        return result

    def check_and_expire(self, current_epoch_seq: int) -> List[str]:
        """EXCEP-REVOKE-0: expire all tokens whose window has passed. Returns revoked IDs."""
        revoked_ids = []
        for token_id, token in list(self._tokens.items()):
            if not token.revoked and current_epoch_seq > token.expires_at_epoch:
                self.revoke(token_id, "epoch_window_expires")
                revoked_ids.append(token_id)
        return revoked_ids

    def has_active_token(
        self, capability_name: str, rule_id: str, current_epoch_seq: int
    ) -> bool:
        """Return True if an active token exists for (capability, rule) at this epoch."""
        for t in self.active_tokens_for(capability_name, current_epoch_seq):
            if t.rule_id == rule_id:
                return True
        return False

    def get(self, token_id: str) -> Optional[ExceptionToken]:
        return self._tokens.get(token_id)

    def all_tokens(self) -> List[ExceptionToken]:
        return list(self._tokens.values())

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if not self._path.exists():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = record.get("event")
            token_id = record.get("token_id", "")
            if event == "granted":
                try:
                    token = self._reconstruct(record)
                    self._tokens[token_id] = token
                except Exception:
                    pass
            elif event == "revoked" and token_id in self._tokens:
                import dataclasses
                self._tokens[token_id] = dataclasses.replace(
                    self._tokens[token_id],
                    revoked=True,
                    revocation_reason=record.get("reason", "unknown"),
                )

    def _append(self, record: Dict[str, Any]) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

    @staticmethod
    def _reconstruct(record: Dict[str, Any]) -> ExceptionToken:
        return ExceptionToken(
            token_id=record["token_id"],
            capability_name=record["capability_name"],
            rule_id=record["rule_id"],
            granted_at_epoch=record["granted_at_epoch"],
            granted_epoch_seq=int(record["granted_epoch_seq"]),
            expires_at_epoch=int(record["expires_at_epoch"]),
            lineage_projection=list(record.get("lineage_projection", [])),
            human_approval_ref=record.get("human_approval_ref"),
            revocation_trigger=record.get("revocation_trigger", ""),
            revoked=bool(record.get("revoked", False)),
            revocation_reason=record.get("revocation_reason"),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scope_hash(capability_name: str, rule_id: str, epoch_id: str) -> str:
    payload = json.dumps(
        {"capability_name": capability_name, "rule_id": rule_id, "epoch_id": epoch_id},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _token_id(epoch_id: str, capability_name: str, rule_id: str, scope_hash: str) -> str:
    payload = json.dumps(
        {"epoch_id": epoch_id, "capability_name": capability_name,
         "rule_id": rule_id, "scope_hash": scope_hash},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "EXCEPTION_TOKEN_MAX_TTL",
    "ELIGIBLE_RULE_IDS",
    "TIER_0_CAPABILITY_NAMES",
    "ExceptionToken",
    "ExceptionTokenLedger",
]
