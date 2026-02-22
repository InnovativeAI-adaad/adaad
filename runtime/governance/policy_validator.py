# SPDX-License-Identifier: Apache-2.0
"""Pre-proposal validation for constitutional policy text."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PolicyValidationResult:
    valid: bool
    errors: list[str]


class PolicyValidator:
    def validate(self, policy_text: str) -> PolicyValidationResult:
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
            result = PolicyValidationResult(valid=True, errors=[])
        except Exception as exc:
            result = PolicyValidationResult(valid=False, errors=[str(exc)])
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError as exc:
                    result.errors.append(f"Temporary policy file cleanup failed: {exc}")

        return result


__all__ = ["PolicyValidator", "PolicyValidationResult"]
