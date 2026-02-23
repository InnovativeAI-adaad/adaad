# SPDX-License-Identifier: Apache-2.0
"""Pre-proposal validation for constitutional policy text."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from runtime.governance.canon_law import CanonLawError, emit_violation_event, load_canon_law, one_way_escalation


@dataclass
class PolicyValidationResult:
    valid: bool
    errors: list[str]
    escalation: str = "advisory"
    mutation_blocked: bool = False
    fail_closed: bool = False


class PolicyValidator:
    def validate(self, policy_text: str) -> PolicyValidationResult:
        escalation = "advisory"
        try:
            clauses = load_canon_law()
        except CanonLawError as exc:
            return PolicyValidationResult(valid=False, errors=[f"canon_law_error:{exc}"], escalation="critical", mutation_blocked=True, fail_closed=True)
        mutation_blocked = False
        fail_closed = False

        if not policy_text.strip():
            clause = clauses["II.policy_payload_must_be_nonempty"]
            entry = emit_violation_event(component="policy_validator", clause=clause, reason="policy_payload_empty")
            escalation = one_way_escalation(escalation, clause.escalation)
            mutation_blocked = mutation_blocked or clause.mutation_block
            fail_closed = fail_closed or clause.fail_closed
            return PolicyValidationResult(
                valid=False,
                errors=["policy_payload_empty", f"ledger_hash:{entry.get('hash','')}"],
                escalation=escalation,
                mutation_blocked=mutation_blocked,
                fail_closed=fail_closed,
            )

        tmp_path: Path | None = None
        result: PolicyValidationResult
        try:
            from runtime.constitution import CONSTITUTION_VERSION, load_constitution_policy

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".json",
                prefix="policy_validator_",
                delete=False,
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(policy_text)
                tmp_file.flush()

            load_constitution_policy(path=tmp_path, expected_version=CONSTITUTION_VERSION)
            result = PolicyValidationResult(
                valid=True,
                errors=[],
                escalation=escalation,
                mutation_blocked=mutation_blocked,
                fail_closed=fail_closed,
            )
        except CanonLawError as exc:
            clause = clauses["VIII.undefined_state_fail_closed"]
            entry = emit_violation_event(component="policy_validator", clause=clause, reason="undefined_state", context={"error": str(exc)})
            escalation = one_way_escalation(escalation, clause.escalation)
            result = PolicyValidationResult(
                valid=False,
                errors=[str(exc), f"ledger_hash:{entry.get('hash','')}"],
                escalation=escalation,
                mutation_blocked=clause.mutation_block,
                fail_closed=clause.fail_closed,
            )
        except Exception as exc:
            clause = clauses["I.policy_parse_must_succeed"]
            entry = emit_violation_event(component="policy_validator", clause=clause, reason="policy_parse_failed", context={"error": str(exc)})
            escalation = one_way_escalation(escalation, clause.escalation)
            mutation_blocked = mutation_blocked or clause.mutation_block
            fail_closed = fail_closed or clause.fail_closed
            result = PolicyValidationResult(
                valid=False,
                errors=[str(exc), f"ledger_hash:{entry.get('hash','')}"],
                escalation=escalation,
                mutation_blocked=mutation_blocked,
                fail_closed=fail_closed,
            )
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError as exc:
                    result.errors.append(f"Temporary policy file cleanup failed: {exc}")

        return result


__all__ = ["PolicyValidator", "PolicyValidationResult"]
