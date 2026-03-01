# Determinism Contract Specification

## Goal

Guarantee replay-equivalent governance outcomes under strict and governance-critical runtime profiles.

## Provider Contract

Deterministic providers must implement:

- stable UTC clock surface
- stable token/id generation for identical seed and labels
- bounded deterministic integer generation for identical seed and labels

## Enforcement Contract

`require_replay_safe_provider(...)` MUST reject non-deterministic providers when:

- replay mode is `strict`
- recovery tier is `governance`
- recovery tier is `critical`
- recovery tier is `audit` (legacy alias)

## Caller Contract

All governance-critical call sites that can produce timestamps, IDs, or tokens must:

1. Resolve provider from deterministic foundation.
2. Invoke replay-safe provider guard before generating material.
3. Pass replay mode and recovery tier explicitly.

## Test Invariants

- strict mode + non-deterministic provider => rejected
- governance tier + non-deterministic provider => rejected
- critical tier + non-deterministic provider => rejected
- deterministic provider produces identical values across repeated runs with same seed/label inputs
