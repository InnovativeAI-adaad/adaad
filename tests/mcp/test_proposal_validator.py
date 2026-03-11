# SPDX-License-Identifier: Apache-2.0
import pytest
pytestmark = pytest.mark.regression_standard

from unittest import mock

from runtime.mcp.proposal_validator import ProposalValidationError, validate_proposal


def _payload(**overrides):
    base = {
        "agent_id": "claude-proposal-agent",
        "generation_ts": "2026-01-01T00:00:00Z",
        "intent": "improve test coverage",
        "ops": [{"op": "replace", "path": "x", "value": "safe"}],
        "targets": [{"agent_id": "a", "path": "app/foo.py", "target_type": "file", "ops": []}],
        "signature": "sig",
        "nonce": "n",
        "authority_level": "auto-execute",
    }
    base.update(overrides)
    return base


@mock.patch("runtime.mcp.proposal_validator.evaluate_mutation", return_value={"passed": True, "verdicts": []})
def test_valid_proposal_passes(_eval):
    req, _ = validate_proposal(_payload())
    assert req.authority_level == "governor-review"


@mock.patch("runtime.mcp.proposal_validator.evaluate_mutation", return_value={"passed": True, "verdicts": []})
def test_authority_override_low_impact(_eval):
    req, _ = validate_proposal(_payload(authority_level="low-impact"))
    assert req.authority_level == "governor-review"


def test_tier0_requires_elevation():
    with pytest.raises(ProposalValidationError) as exc:
        validate_proposal(_payload(targets=[{"agent_id": "a", "path": "runtime/constitution.py", "target_type": "file", "ops": []}]))
    assert exc.value.status_code == 403
    assert exc.value.code == "tier0_escalation_required"


@mock.patch(
    "runtime.mcp.proposal_validator.evaluate_mutation",
    return_value={"passed": False, "verdicts": [{"severity": "blocking", "ok": False, "rule": "x"}]},
)
def test_blocking_constitution_verdict_rejected(_eval):
    with pytest.raises(ProposalValidationError) as exc:
        validate_proposal(_payload())
    assert exc.value.status_code == 422
    assert exc.value.code == "pre_check_failed"


def test_missing_required_field():
    payload = _payload()
    payload.pop("nonce")
    with pytest.raises(ProposalValidationError) as exc:
        validate_proposal(payload)
    assert exc.value.status_code == 400
