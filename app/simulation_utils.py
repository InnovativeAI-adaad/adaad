# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import hashlib
import json
import os
from collections import OrderedDict
from dataclasses import is_dataclass, asdict
from typing import Any, Dict


class LRUCache(OrderedDict[str, float]):
    """Small deterministic LRU cache for simulation scores."""

    def __init__(self, maxsize: int = 2048):
        super().__init__()
        self.maxsize = maxsize

    def get(self, key: str) -> float | None:  # type: ignore[override]
        if key not in self:
            return None
        self.move_to_end(key)
        return super().__getitem__(key)

    def set(self, key: str, value: float) -> None:
        self[key] = value
        self.move_to_end(key)
        if len(self) > self.maxsize:
            self.popitem(last=False)


def clone_dna_for_simulation(dna: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministically clone DNA with a structural fast path and fail-closed semantics."""

    if all(isinstance(v, (str, int, float, bool)) or v is None for v in dna.values()):
        return dict(dna)

    memo: dict[int, Any] = {}

    def _clone_value(value: Any) -> Any:
        if isinstance(value, (dict, list, tuple)):
            cached = memo.get(id(value))
            if cached is not None:
                return cached
        if isinstance(value, dict):
            cloned_dict: dict[Any, Any] = {}
            memo[id(value)] = cloned_dict
            for k, v in value.items():
                cloned_dict[k] = _clone_value(v)
            return cloned_dict
        if isinstance(value, list):
            cloned_list: list[Any] = []
            memo[id(value)] = cloned_list
            cloned_list.extend(_clone_value(v) for v in value)
            return cloned_list
        if isinstance(value, tuple):
            placeholder: list[Any] = []
            memo[id(value)] = placeholder
            placeholder.extend(_clone_value(v) for v in value)
            cloned_tuple = tuple(placeholder)
            memo[id(value)] = cloned_tuple
            return cloned_tuple
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        raise TypeError(f"unsupported_dna_type:{type(value).__name__}")

    def _env_flag(name: str) -> bool:
        return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

    try:
        cloned = _clone_value(dna)
        if not isinstance(cloned, dict):
            raise TypeError("unsupported_root_type")
        return cloned
    except TypeError as exc:
        allow_unsafe_deepcopy = _env_flag("ADAAD_SIMULATION_ALLOW_UNSUPPORTED_DNA_DEEPCOPY") and _env_flag("CRYOVANT_DEV_MODE")
        if allow_unsafe_deepcopy:
            return copy.deepcopy(dna)
        raise TypeError(str(exc)) from None


def _normalize_for_hash(value: Any) -> Any:
    def _normalize_key(key: Any) -> str:
        key_type = type(key).__name__
        if isinstance(key, (str, int, float, bool)) or key is None:
            normalized_key_value = str(key)
        else:
            normalized_key_payload = _normalize_for_hash(key)
            try:
                normalized_key_value = json.dumps(
                    normalized_key_payload,
                    separators=(",", ":"),
                )
            except TypeError:
                normalized_key_value = repr(normalized_key_payload)
        return f"{key_type}:{normalized_key_value}"

    if isinstance(value, dict):
        normalized_items = sorted(value.items(), key=lambda item: _normalize_key(item[0]))
        return {_normalize_key(k): _normalize_for_hash(v) for k, v in normalized_items}
    if isinstance(value, list):
        return [_normalize_for_hash(v) for v in value]
    if isinstance(value, tuple):
        return {"__type__": "__adaad_runtime_sim_tuple_v1__", "items": [_normalize_for_hash(v) for v in value]}
    if is_dataclass(value):
        return _normalize_for_hash(asdict(value))
    if hasattr(value, "__dict__"):
        return _normalize_for_hash(vars(value))
    return value


def stable_hash(payload: Any) -> str:
    normalized = _normalize_for_hash(payload)
    serialized = json.dumps(normalized, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
