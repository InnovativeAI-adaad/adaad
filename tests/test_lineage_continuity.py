# SPDX-License-Identifier: Apache-2.0

import pytest

from runtime.constitution import validate_lineage_continuity


class MockMutation:
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id


@pytest.mark.parametrize(
    "resolved_chain, expected_error",
    [
        (["a" * 64, "b" * 64, "c" * 64], None),
        (None, "lineage_missing_parent"),
        (["a" * 64, "tampered"], "lineage_tampered_hash"),
        (["0" * 64, "b" * 64], "lineage_missing_genesis"),
    ],
)
def test_validate_lineage_continuity(monkeypatch: pytest.MonkeyPatch, resolved_chain, expected_error) -> None:
    monkeypatch.setattr("security.ledger.lineage_v2.resolve_chain", lambda agent_id: resolved_chain)
    mutation = MockMutation("agent-A")

    if expected_error is None:
        assert validate_lineage_continuity(mutation) is True
        return

    with pytest.raises(RuntimeError, match=expected_error):
        validate_lineage_continuity(mutation)
