# SPDX-License-Identifier: Apache-2.0
"""Tests for AGM event envelope determinism."""

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.agm_event import AGMEventEnvelope, AGMEventValidationError, ScoringEvent, create_event_envelope, validate_event_envelope
from runtime.governance.foundation.determinism import SeededDeterminismProvider, SystemDeterminismProvider


def _scoring_event() -> ScoringEvent:
    return ScoringEvent(mutation_id="m-001", score=0.91)


def test_envelope_event_id_is_deterministic_under_seeded_provider() -> None:
    provider_a = SeededDeterminismProvider(seed="replay-test")
    provider_b = SeededDeterminismProvider(seed="replay-test")
    envelope_a = create_event_envelope(_scoring_event(), provider=provider_a)
    envelope_b = create_event_envelope(_scoring_event(), provider=provider_b)
    assert envelope_a.event_id == envelope_b.event_id


def test_envelope_emitted_at_is_deterministic_under_seeded_provider() -> None:
    provider_a = SeededDeterminismProvider(seed="replay-ts")
    provider_b = SeededDeterminismProvider(seed="replay-ts")
    envelope_a = create_event_envelope(_scoring_event(), provider=provider_a)
    envelope_b = create_event_envelope(_scoring_event(), provider=provider_b)
    assert envelope_a.emitted_at == envelope_b.emitted_at
    assert envelope_a.emitted_at.endswith("Z")


def test_two_envelopes_same_provider_have_unique_ids() -> None:
    provider = SeededDeterminismProvider(seed="collision-seed")
    envelope_a = create_event_envelope(_scoring_event(), provider=provider)
    envelope_b = create_event_envelope(_scoring_event(), provider=provider)
    assert envelope_a.event_id != envelope_b.event_id


def test_validate_rejects_non_hex_event_id() -> None:
    bad = AGMEventEnvelope(
        schema_version="1.0",
        event_id="not-a-hex-id-and-not-32-chars!!",
        event_type="scoring_event",
        emitted_at="2026-01-01T00:00:00Z",
        payload={"mutation_id": "m-001", "score": 0.9},
        signature="",
        signing_key_id="",
        signature_algorithm="",
    )
    with pytest.raises(AGMEventValidationError, match="invalid:event_id_format"):
        validate_event_envelope(bad, require_signature=False)


def test_validate_rejects_short_event_id() -> None:
    bad = AGMEventEnvelope(
        schema_version="1.0",
        event_id="deadbeef",
        event_type="scoring_event",
        emitted_at="2026-01-01T00:00:00Z",
        payload={"mutation_id": "m-001", "score": 0.9},
        signature="",
        signing_key_id="",
        signature_algorithm="",
    )
    with pytest.raises(AGMEventValidationError, match="invalid:event_id_format"):
        validate_event_envelope(bad, require_signature=False)


def test_seeded_provider_produces_valid_event_id_format() -> None:
    provider = SeededDeterminismProvider(seed="format-check")
    for _ in range(20):
        envelope = create_event_envelope(_scoring_event(), provider=provider)
        assert len(envelope.event_id) == 32
        assert envelope.event_id == envelope.event_id.lower()
        assert all(char in "0123456789abcdef" for char in envelope.event_id)


def test_validate_accepts_well_formed_emitted_at() -> None:
    envelope = AGMEventEnvelope(
        schema_version="1.0",
        event_id="a" * 32,
        event_type="scoring_event",
        emitted_at="2026-01-15T08:30:00Z",
        payload={"mutation_id": "m-001", "score": 0.9},
        signature="",
        signing_key_id="",
        signature_algorithm="",
    )
    validate_event_envelope(envelope, require_signature=False)


def test_validate_rejects_garbage_string_ending_in_z() -> None:
    bad = AGMEventEnvelope(
        schema_version="1.0",
        event_id="a" * 32,
        event_type="scoring_event",
        emitted_at="not-a-real-timestampZ",
        payload={"mutation_id": "m-001", "score": 0.9},
        signature="",
        signing_key_id="",
        signature_algorithm="",
    )
    with pytest.raises(AGMEventValidationError, match="invalid:emitted_at"):
        validate_event_envelope(bad, require_signature=False)


def test_validate_rejects_emitted_at_missing_z_suffix() -> None:
    bad = AGMEventEnvelope(
        schema_version="1.0",
        event_id="a" * 32,
        event_type="scoring_event",
        emitted_at="2026-01-15T08:30:00+00:00",
        payload={"mutation_id": "m-001", "score": 0.9},
        signature="",
        signing_key_id="",
        signature_algorithm="",
    )
    with pytest.raises(AGMEventValidationError, match="invalid:emitted_at"):
        validate_event_envelope(bad, require_signature=False)


def test_create_event_envelope_rejects_system_provider_in_strict_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    with pytest.raises(RuntimeError, match="strict_replay_requires_deterministic_provider"):
        create_event_envelope(_scoring_event(), provider=SystemDeterminismProvider())


def test_create_event_envelope_accepts_seeded_provider_in_strict_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    provider = SeededDeterminismProvider(seed="strict-create-test")
    envelope = create_event_envelope(_scoring_event(), provider=provider)
    assert len(envelope.event_id) == 32
