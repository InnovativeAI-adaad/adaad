# Whale.Dic Cache Controls & Fallback Runbook

## Scope

Operational controls for the Whale.Dic integration cache used to normalize equivalent query keys,
apply deterministic TTL invalidation, and preserve bounded memory behavior for mobile constraints.

Implementation anchor: `ui/features/whaledic_cache.py`.

## Controls

- **Key normalization:** `WhaleDicIntegrationCache.normalize_key()` lowercases, trims, and collapses
  whitespace so equivalent queries map to the same cache key.
- **TTL invalidation:** entries are stale when `now_ms - created_ms >= ttl_ms`.
- **Offline read-through:** set `offline_read_through=True` to serve stale entries when loaders fail or
  network is intentionally unavailable.
- **Bounded size / eviction:** `max_entries` enforces LRU eviction (`oldest` removed first) to preserve
  mobile memory budgets.
- **Deterministic replay/testing:** use explicit `now_ms` and `snapshot()` for replay-stable assertions.

## Suggested policy profiles

- **Live mode:** `ttl_ms=30_000`, `max_entries=64`, `offline_read_through=False`
- **Low-connectivity mode:** `ttl_ms=60_000`, `max_entries=64`, `offline_read_through=True`
- **Replay/testing mode:** fixed `now_ms` inputs from harness and `snapshot()` equality assertions

## Fallback behavior

1. Attempt cache hit via normalized key.
2. If hit is fresh → return `source="cache"`.
3. If stale and offline read-through is enabled → return `source="stale_cache"`.
4. Otherwise execute loader and refresh cache (`source="loader"`).
5. If cache capacity exceeded, evict least-recently-used entry.

## Verification checklist

- `tests/test_whaledic_cache.py::test_normalization_and_hit_miss_behavior`
- `tests/test_whaledic_cache.py::test_stale_invalidation_without_offline_read_through`
- `tests/test_whaledic_cache.py::test_offline_read_through_returns_stale_value`
- `tests/test_whaledic_cache.py::test_lru_eviction_for_mobile_constraints`
- `tests/test_whaledic_cache.py::test_deterministic_snapshots_for_replay_and_testing_modes`
