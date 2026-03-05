# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json

import pytest

from runtime.governance.federation.key_registry import get_trusted_public_key, load_trusted_key_registry
from runtime.governance.federation.transport import FederationTransportContractError


def _set_registry(monkeypatch: pytest.MonkeyPatch, path) -> None:
    monkeypatch.setattr("runtime.governance.federation.key_registry._REGISTRY_PATH", path)
    monkeypatch.setattr("runtime.governance.federation.key_registry._CACHE", None)
    monkeypatch.setattr("runtime.governance.federation.key_registry._REGISTRY", None)


def test_registry_loads_trusted_key(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "federation_trusted_keys.json"
    path.write_text(
        json.dumps(
            {
                "trusted_keys": [
                    {
                        "key_id": "federation-root-1",
                        "public_key_pem": "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _set_registry(monkeypatch, path)

    loaded = get_trusted_public_key("federation-root-1")

    assert "BEGIN PUBLIC KEY" in loaded


@pytest.mark.parametrize(
    "payload,error",
    [
        ({}, "federation_key_registry_invalid"),
        ({"trusted_keys": []}, "federation_key_registry_invalid"),
        ({"trusted_keys": [{"public_key_pem": "pem-only"}]}, "federation_key_registry_malformed"),
        ({"trusted_keys": [{"key_id": "id-only"}]}, "federation_key_registry_malformed"),
    ],
)
def test_registry_malformed_rejected(tmp_path, monkeypatch: pytest.MonkeyPatch, payload: dict, error: str) -> None:
    path = tmp_path / "federation_trusted_keys.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    _set_registry(monkeypatch, path)

    with pytest.raises(FederationTransportContractError, match=error):
        load_trusted_key_registry(reload=True)


def test_untrusted_key_id_rejected(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "federation_trusted_keys.json"
    path.write_text(
        json.dumps(
            {
                "trusted_keys": [
                    {
                        "key_id": "trusted",
                        "public_key_pem": "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _set_registry(monkeypatch, path)

    with pytest.raises(FederationTransportContractError, match="federation_key_id_untrusted:unknown"):
        get_trusted_public_key("unknown")


def test_registry_cache_is_reused(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "federation_trusted_keys.json"
    path.write_text(
        json.dumps(
            {
                "trusted_keys": [
                    {
                        "key_id": "trusted",
                        "public_key_pem": "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _set_registry(monkeypatch, path)

    first = load_trusted_key_registry()
    second = load_trusted_key_registry()

    assert first is second
