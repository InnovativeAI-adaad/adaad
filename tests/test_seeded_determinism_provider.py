# SPDX-License-Identifier: Apache-2.0
"""Tests for SeededDeterminismProvider uniqueness and replay guarantees."""

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.foundation.determinism import SeededDeterminismProvider, SystemDeterminismProvider


def test_repeated_same_label_produces_unique_ids() -> None:
    provider = SeededDeterminismProvider(seed="test-seed")
    ids = [provider.next_id(label="mcp-proposal", length=32) for _ in range(10)]
    assert len(set(ids)) == 10


def test_repeated_same_label_produces_unique_tokens() -> None:
    provider = SeededDeterminismProvider(seed="test-seed")
    tokens = [provider.next_token(label="mcp-token", length=16) for _ in range(10)]
    assert len(set(tokens)) == 10


def test_replay_identical_sequence_is_deterministic() -> None:
    provider_a = SeededDeterminismProvider(seed="replay-seed")
    provider_b = SeededDeterminismProvider(seed="replay-seed")
    ids_a = [provider_a.next_id(label="mcp-proposal", length=32) for _ in range(5)]
    ids_b = [provider_b.next_id(label="mcp-proposal", length=32) for _ in range(5)]
    assert ids_a == ids_b


def test_different_seeds_produce_different_ids() -> None:
    provider_a = SeededDeterminismProvider(seed="seed-a")
    provider_b = SeededDeterminismProvider(seed="seed-b")
    assert provider_a.next_id(label="x") != provider_b.next_id(label="x")


def test_different_labels_produce_different_ids() -> None:
    provider = SeededDeterminismProvider(seed="seed-a")
    assert provider.next_id(label="alpha") != provider.next_id(label="beta")


def test_unique_tokens_per_call_same_label() -> None:
    provider = SeededDeterminismProvider(seed="token-collision-seed")
    tokens = [provider.next_token(label="mcp-proposal") for _ in range(5)]
    assert len(set(tokens)) == 5


def test_token_replay_determinism() -> None:
    provider_a = SeededDeterminismProvider(seed="token-replay-seed")
    provider_b = SeededDeterminismProvider(seed="token-replay-seed")
    seq_a = [provider_a.next_token(label="session") for _ in range(4)]
    seq_b = [provider_b.next_token(label="session") for _ in range(4)]
    assert seq_a == seq_b


def test_int_replay_determinism() -> None:
    provider_a = SeededDeterminismProvider(seed="int-replay-seed")
    provider_b = SeededDeterminismProvider(seed="int-replay-seed")
    seq_a = [provider_a.next_int(low=1, high=100, label="score") for _ in range(4)]
    seq_b = [provider_b.next_int(low=1, high=100, label="score") for _ in range(4)]
    assert seq_a == seq_b


def test_unique_ints_per_call_same_label_wide_range() -> None:
    provider = SeededDeterminismProvider(seed="int-collision-seed")
    values = [provider.next_int(low=0, high=2**31 - 1, label="budget") for _ in range(5)]
    assert len(set(values)) == 5


def test_call_counters_are_isolated_across_id_token_int() -> None:
    provider = SeededDeterminismProvider(seed="isolation-seed")
    id_0 = provider.next_id(label="x")
    tok_0 = provider.next_token(label="x")
    int_0 = provider.next_int(low=0, high=2**31 - 1, label="x")
    id_1 = provider.next_id(label="x")
    tok_1 = provider.next_token(label="x")
    assert len({id_0, tok_0, id_1, tok_1}) == 4
    assert 0 <= int_0 < 2**31


def test_next_id_raises_on_length_exceeding_digest_width() -> None:
    provider = SeededDeterminismProvider(seed="len-guard")
    with pytest.raises(ValueError, match=r"next_id: invalid length=65; expected 1..64"):
        provider.next_id(label="x", length=65)


def test_next_token_raises_on_length_exceeding_digest_width() -> None:
    provider = SeededDeterminismProvider(seed="len-guard")
    with pytest.raises(ValueError, match=r"next_token: invalid length=65; expected 1..64"):
        provider.next_token(label="x", length=65)


@pytest.mark.parametrize("length", [0, -1])
def test_next_id_raises_on_non_positive_length_seeded(length: int) -> None:
    provider = SeededDeterminismProvider(seed="len-guard")
    with pytest.raises(ValueError, match=rf"next_id: invalid length={length}; expected 1..64"):
        provider.next_id(label="x", length=length)


@pytest.mark.parametrize("length", [0, -1])
def test_next_token_raises_on_non_positive_length_seeded(length: int) -> None:
    provider = SeededDeterminismProvider(seed="len-guard")
    with pytest.raises(ValueError, match=rf"next_token: invalid length={length}; expected 1..64"):
        provider.next_token(label="x", length=length)


@pytest.mark.parametrize("length", [1, 16, 32, 64])
def test_seeded_length_boundaries(length: int) -> None:
    provider = SeededDeterminismProvider(seed="len-boundary")
    assert len(provider.next_id(label="x", length=length)) == length
    assert len(provider.next_token(label="x", length=length)) == length


@pytest.mark.parametrize("length", [0, -1])
def test_next_id_raises_on_non_positive_length_system(length: int) -> None:
    provider = SystemDeterminismProvider()
    with pytest.raises(ValueError, match=rf"next_id: invalid length={length}; expected 1..64"):
        provider.next_id(label="x", length=length)


@pytest.mark.parametrize("length", [0, -1])
def test_next_token_raises_on_non_positive_length_system(length: int) -> None:
    provider = SystemDeterminismProvider()
    with pytest.raises(ValueError, match=rf"next_token: invalid length={length}; expected 1..64"):
        provider.next_token(label="x", length=length)


@pytest.mark.parametrize("length", [1, 16, 32, 64])
def test_system_length_boundaries(length: int) -> None:
    provider = SystemDeterminismProvider()
    assert len(provider.next_id(label="x", length=length)) == length
    assert len(provider.next_token(label="x", length=length)) == length


def test_next_id_raises_on_length_exceeding_digest_width_system() -> None:
    provider = SystemDeterminismProvider()
    with pytest.raises(ValueError, match=r"next_id: invalid length=65; expected 1..64"):
        provider.next_id(label="x", length=65)


def test_next_token_raises_on_length_exceeding_digest_width_system() -> None:
    provider = SystemDeterminismProvider()
    with pytest.raises(ValueError, match=r"next_token: invalid length=65; expected 1..64"):
        provider.next_token(label="x", length=65)
