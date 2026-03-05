# SPDX-License-Identifier: Apache-2.0
"""Policy Simulation DSL Grammar — ADAAD-8 / v1.3

Bounded constraint expression language for the Policy Simulation Mode.
Grammar is version-locked at 10 core constraint types for v1.3.
Any future grammar extensions require a semantic version bump.

Grammar version: 1.0.0

Design:
- DSL expressions are parsed into ConstraintExpression dataclasses.
- The constraint_interpreter.py module converts these into SimulationPolicy objects.
- Malformed expressions raise SimulationDSLError with token + position.
- The grammar is deliberately minimal — non-technical stakeholders drive
  simulation via Aponi UI toggles that emit DSL strings under the hood.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Grammar versioning
# ---------------------------------------------------------------------------

DSL_GRAMMAR_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class SimulationDSLError(Exception):
    """Raised when a DSL expression cannot be parsed.

    Attributes:
        message: Human-readable description of the parse failure.
        token: Offending token string, if identifiable.
        position: Character offset in the expression string, if identifiable.
    """

    def __init__(self, message: str, token: str = "", position: int = -1):
        super().__init__(message)
        self.token = token
        self.position = position

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.token:
            parts.append(f"token={self.token!r}")
        if self.position >= 0:
            parts.append(f"position={self.position}")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# Constraint type registry (10 core types, v1.3-locked)
# ---------------------------------------------------------------------------

class ConstraintType(str, Enum):
    """The 10 core constraint types supported in DSL grammar v1.0.0."""
    REQUIRE_APPROVALS = "require_approvals"
    MAX_RISK_SCORE = "max_risk_score"
    MAX_MUTATIONS_PER_EPOCH = "max_mutations_per_epoch"
    MAX_COMPLEXITY_DELTA = "max_complexity_delta"
    FREEZE_TIER = "freeze_tier"
    REQUIRE_RULE = "require_rule"
    MIN_TEST_COVERAGE = "min_test_coverage"
    MAX_ENTROPY_PER_EPOCH = "max_entropy_per_epoch"
    ESCALATE_REVIEWERS_ON_RISK = "escalate_reviewers_on_risk"
    REQUIRE_LINEAGE_DEPTH = "require_lineage_depth"


# ---------------------------------------------------------------------------
# Parsed parameter types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConstraintExpression:
    """A fully parsed DSL constraint expression, ready for the interpreter."""
    constraint_type: ConstraintType
    kwargs: Dict[str, Any]
    raw_expression: str
    grammar_version: str = DSL_GRAMMAR_VERSION

    def __post_init__(self) -> None:
        # Validate required kwargs per constraint type.
        _VALIDATORS[self.constraint_type](self.kwargs, self.raw_expression)


# ---------------------------------------------------------------------------
# Parameter parsers and validators
# ---------------------------------------------------------------------------

def _parse_kwarg_string(raw: str) -> Dict[str, str]:
    """Parse 'key=value, key2=value2' into {key: value_str, ...}."""
    result: Dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SimulationDSLError(f"Expected key=value, got {part!r}", token=part)
        key, _, val = part.partition("=")
        result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def _require_float(kwargs: Dict[str, str], key: str, lo: float = 0.0, hi: float = 1.0, raw: str = "") -> float:
    if key not in kwargs:
        raise SimulationDSLError(f"Missing required parameter '{key}'", token=key)
    try:
        val = float(kwargs[key])
    except ValueError:
        raise SimulationDSLError(f"Parameter '{key}' must be a float, got {kwargs[key]!r}",
                                  token=kwargs[key], position=-1)
    if not (lo <= val <= hi):
        raise SimulationDSLError(f"Parameter '{key}'={val} out of range [{lo}, {hi}]",
                                  token=str(val))
    return val


def _require_int(kwargs: Dict[str, str], key: str, lo: int = 0, raw: str = "") -> int:
    if key not in kwargs:
        raise SimulationDSLError(f"Missing required parameter '{key}'", token=key)
    try:
        val = int(kwargs[key])
    except ValueError:
        raise SimulationDSLError(f"Parameter '{key}' must be an int, got {kwargs[key]!r}",
                                  token=kwargs[key])
    if val < lo:
        raise SimulationDSLError(f"Parameter '{key}'={val} must be >= {lo}", token=str(val))
    return val


def _require_str(kwargs: Dict[str, str], key: str, raw: str = "") -> str:
    if key not in kwargs:
        raise SimulationDSLError(f"Missing required parameter '{key}'", token=key)
    val = kwargs[key].strip()
    if not val:
        raise SimulationDSLError(f"Parameter '{key}' must not be empty", token=key)
    return val


# Per-type validators: called from ConstraintExpression.__post_init__

def _validate_require_approvals(kwargs: Dict[str, Any], raw: str) -> None:
    _require_str(kwargs, "tier", raw)
    count = _require_int(kwargs, "count", lo=1, raw=raw)
    if count > 20:
        raise SimulationDSLError("'count' must be <= 20 for require_approvals", token=str(count))


def _validate_max_risk_score(kwargs: Dict[str, Any], raw: str) -> None:
    _require_float(kwargs, "threshold", lo=0.0, hi=1.0, raw=raw)


def _validate_max_mutations_per_epoch(kwargs: Dict[str, Any], raw: str) -> None:
    _require_int(kwargs, "count", lo=1, raw=raw)


def _validate_max_complexity_delta(kwargs: Dict[str, Any], raw: str) -> None:
    _require_float(kwargs, "delta", lo=0.0, hi=1.0, raw=raw)


def _validate_freeze_tier(kwargs: Dict[str, Any], raw: str) -> None:
    _require_str(kwargs, "tier", raw)
    # reason is optional


def _validate_require_rule(kwargs: Dict[str, Any], raw: str) -> None:
    _require_str(kwargs, "rule_id", raw)
    severity = kwargs.get("severity", "BLOCKING").upper()
    if severity not in ("BLOCKING", "WARNING", "INFO"):
        raise SimulationDSLError(f"severity must be BLOCKING|WARNING|INFO, got {severity!r}", token=severity)


def _validate_min_test_coverage(kwargs: Dict[str, Any], raw: str) -> None:
    _require_float(kwargs, "threshold", lo=0.0, hi=1.0, raw=raw)


def _validate_max_entropy_per_epoch(kwargs: Dict[str, Any], raw: str) -> None:
    _require_float(kwargs, "ceiling", lo=0.0, hi=1.0, raw=raw)


def _validate_escalate_reviewers_on_risk(kwargs: Dict[str, Any], raw: str) -> None:
    _require_float(kwargs, "threshold", lo=0.0, hi=1.0, raw=raw)
    _require_int(kwargs, "count", lo=1, raw=raw)


def _validate_require_lineage_depth(kwargs: Dict[str, Any], raw: str) -> None:
    _require_int(kwargs, "min", lo=1, raw=raw)


_VALIDATORS = {
    ConstraintType.REQUIRE_APPROVALS: _validate_require_approvals,
    ConstraintType.MAX_RISK_SCORE: _validate_max_risk_score,
    ConstraintType.MAX_MUTATIONS_PER_EPOCH: _validate_max_mutations_per_epoch,
    ConstraintType.MAX_COMPLEXITY_DELTA: _validate_max_complexity_delta,
    ConstraintType.FREEZE_TIER: _validate_freeze_tier,
    ConstraintType.REQUIRE_RULE: _validate_require_rule,
    ConstraintType.MIN_TEST_COVERAGE: _validate_min_test_coverage,
    ConstraintType.MAX_ENTROPY_PER_EPOCH: _validate_max_entropy_per_epoch,
    ConstraintType.ESCALATE_REVIEWERS_ON_RISK: _validate_escalate_reviewers_on_risk,
    ConstraintType.REQUIRE_LINEAGE_DEPTH: _validate_require_lineage_depth,
}


# ---------------------------------------------------------------------------
# Tokenizer and parser
# ---------------------------------------------------------------------------

_FUNC_PATTERN = re.compile(
    r"^\s*(?P<name>[a-z_]+)\s*\((?P<args>[^)]*)\)\s*$",
    re.DOTALL,
)


def _type_coerce_kwargs(constraint_type: ConstraintType, raw_kwargs: Dict[str, str]) -> Dict[str, Any]:
    """Coerce string kwargs to typed values per constraint schema."""
    coerced: Dict[str, Any] = dict(raw_kwargs)

    float_keys = {
        ConstraintType.MAX_RISK_SCORE: ["threshold"],
        ConstraintType.MAX_COMPLEXITY_DELTA: ["delta"],
        ConstraintType.MIN_TEST_COVERAGE: ["threshold"],
        ConstraintType.MAX_ENTROPY_PER_EPOCH: ["ceiling"],
        ConstraintType.ESCALATE_REVIEWERS_ON_RISK: ["threshold"],
    }
    int_keys = {
        ConstraintType.REQUIRE_APPROVALS: ["count"],
        ConstraintType.MAX_MUTATIONS_PER_EPOCH: ["count"],
        ConstraintType.ESCALATE_REVIEWERS_ON_RISK: ["count"],
        ConstraintType.REQUIRE_LINEAGE_DEPTH: ["min"],
    }

    for key in float_keys.get(constraint_type, []):
        if key in coerced:
            try:
                coerced[key] = float(coerced[key])
            except (ValueError, TypeError):
                raise SimulationDSLError(
                    f"Parameter '{key}' must be a float, got {coerced[key]!r}",
                    token=str(coerced[key]),
                )
    for key in int_keys.get(constraint_type, []):
        if key in coerced:
            coerced[key] = int(coerced[key])

    # Normalize severity to uppercase for require_rule
    if constraint_type == ConstraintType.REQUIRE_RULE and "severity" in coerced:
        coerced["severity"] = str(coerced["severity"]).upper()

    return coerced


def parse_constraint(expression: str) -> ConstraintExpression:
    """Parse a single DSL constraint expression string into a ConstraintExpression.

    Args:
        expression: A DSL expression string, e.g.
            'require_approvals(tier=PRODUCTION, count=3)'

    Returns:
        ConstraintExpression with validated, typed kwargs.

    Raises:
        SimulationDSLError: On any parse or validation failure, with token and position.

    Examples:
        >>> parse_constraint('max_risk_score(threshold=0.4)')
        ConstraintExpression(constraint_type=<ConstraintType.MAX_RISK_SCORE: 'max_risk_score'>, ...)

        >>> parse_constraint('freeze_tier(tier=PRODUCTION, reason="audit period")')
        ConstraintExpression(constraint_type=<ConstraintType.FREEZE_TIER: 'freeze_tier'>, ...)
    """
    expression = expression.strip()
    match = _FUNC_PATTERN.match(expression)
    if not match:
        raise SimulationDSLError(
            "Expression must be of the form: constraint_name(key=value, ...)",
            token=expression[:40],
            position=0,
        )

    func_name = match.group("name")
    args_raw = match.group("args").strip()

    try:
        constraint_type = ConstraintType(func_name)
    except ValueError:
        known = sorted(ct.value for ct in ConstraintType)
        raise SimulationDSLError(
            f"Unknown constraint type {func_name!r}. Known types: {known}",
            token=func_name,
            position=expression.index(func_name),
        )

    raw_kwargs = _parse_kwarg_string(args_raw)
    typed_kwargs = _type_coerce_kwargs(constraint_type, raw_kwargs)

    return ConstraintExpression(
        constraint_type=constraint_type,
        kwargs=typed_kwargs,
        raw_expression=expression,
        grammar_version=DSL_GRAMMAR_VERSION,
    )


def parse_policy_block(block: str) -> List[ConstraintExpression]:
    """Parse a multi-line block of DSL constraint expressions.

    Each non-blank, non-comment line is parsed as a separate constraint.
    Lines beginning with '#' are treated as comments and skipped.

    Args:
        block: Multi-line string of DSL expressions.

    Returns:
        List of ConstraintExpression objects in declaration order.

    Raises:
        SimulationDSLError: On any malformed line.
    """
    expressions: List[ConstraintExpression] = []
    for lineno, raw_line in enumerate(block.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            expressions.append(parse_constraint(line))
        except SimulationDSLError as exc:
            raise SimulationDSLError(
                f"Parse error at line {lineno}: {exc}",
                token=exc.token,
                position=exc.position,
            ) from exc
    return expressions


__all__ = [
    "DSL_GRAMMAR_VERSION",
    "SimulationDSLError",
    "ConstraintType",
    "ConstraintExpression",
    "parse_constraint",
    "parse_policy_block",
]
