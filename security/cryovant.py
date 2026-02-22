# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Cryovant gatekeeper enforcing environment and lineage validation.
"""

import hashlib
import hmac
import json
import os
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.agents.discovery import iter_agent_dirs, resolve_agent_id
from runtime import metrics
from security import SECURITY_ROOT
from security.ledger import journal

ELEMENT_ID = "Water"

KEYS_DIR = SECURITY_ROOT / "keys"
LEDGER_DIR = SECURITY_ROOT / "ledger"
ROTATION_METADATA_PATH = KEYS_DIR / "rotation.json"
DEFAULT_ROTATION_INTERVAL_SECONDS = 60 * 60 * 24 * 30

_HMAC_SIGNATURE_PREFIX = "sha256:"
_ARTIFACT_HMAC_CONFIG: Dict[str, Dict[str, str]] = {
    "replay_proof": {
        "specific_env_prefix": "ADAAD_REPLAY_PROOF_KEY_",
        "generic_env_var": "ADAAD_REPLAY_PROOF_SIGNING_KEY",
        "fallback_namespace": "adaad-replay-proof-dev-secret",
    },
    "policy_artifact": {
        "specific_env_prefix": "ADAAD_POLICY_ARTIFACT_KEY_",
        "generic_env_var": "ADAAD_POLICY_ARTIFACT_SIGNING_KEY",
        "fallback_namespace": "adaad-policy-artifact-dev-secret",
    },
    "rollback_certificate": {
        "specific_env_prefix": "CRYOVANT_ROLLBACK_SIGNING_KEY_",
        "generic_env_var": "CRYOVANT_ROLLBACK_SIGNING_KEY",
        "fallback_namespace": "cryovant-rollback-certificate",
    },
}


def dev_mode() -> bool:
    return os.environ.get("CRYOVANT_DEV_MODE", "0").lower() in {"1", "true", "yes", "on"}




def env_mode() -> str:
    mode = os.environ.get("ADAAD_ENV", "prod").strip().lower()
    if mode in {"dev", "prod"}:
        return mode
    return "prod"


def _keys_configured() -> bool:
    try:
        return KEYS_DIR.exists() and any(KEYS_DIR.iterdir())
    except OSError:
        return False


def _legacy_static_signature_allowed(signature: str) -> bool:
    return signature.startswith("cryovant-static-")


def _resolve_hmac_secret(*, key_id: str, specific_env_prefix: str, generic_env_var: str, fallback_namespace: str) -> str:
    specific_env = f"{specific_env_prefix}{key_id.upper().replace('-', '_')}"
    specific = os.environ.get(specific_env, "").strip()
    if specific:
        return specific
    generic = os.environ.get(generic_env_var, "").strip()
    if generic:
        return generic
    return f"{fallback_namespace}:{key_id}"


def sign_hmac_digest(
    *,
    key_id: str,
    signed_digest: str,
    specific_env_prefix: str,
    generic_env_var: str,
    fallback_namespace: str,
    hmac_secret: str | None = None,
) -> str:
    """Build deterministic HMAC-style digest signature for sealed artifacts."""

    secret = hmac_secret or _resolve_hmac_secret(
        key_id=key_id,
        specific_env_prefix=specific_env_prefix,
        generic_env_var=generic_env_var,
        fallback_namespace=fallback_namespace,
    )
    return _HMAC_SIGNATURE_PREFIX + hashlib.sha256(f"{secret}:{signed_digest}".encode("utf-8")).hexdigest()


def _canonical_signature(signature: str) -> str:
    if not isinstance(signature, str):
        return ""
    candidate = signature.strip()
    if not candidate:
        return ""
    if candidate.startswith(_HMAC_SIGNATURE_PREFIX):
        return _HMAC_SIGNATURE_PREFIX + candidate[len(_HMAC_SIGNATURE_PREFIX) :].lower()
    return _HMAC_SIGNATURE_PREFIX + candidate.lower()


def verify_hmac_digest_signature(
    *,
    key_id: str,
    signed_digest: str,
    signature: str,
    specific_env_prefix: str,
    generic_env_var: str,
    fallback_namespace: str,
    hmac_secret: str | None = None,
) -> bool:
    expected = sign_hmac_digest(
        key_id=key_id,
        signed_digest=signed_digest,
        specific_env_prefix=specific_env_prefix,
        generic_env_var=generic_env_var,
        fallback_namespace=fallback_namespace,
        hmac_secret=hmac_secret,
    )
    return hmac.compare_digest(_canonical_signature(signature), expected)


def sign_artifact_hmac_digest(*, artifact_type: str, key_id: str, signed_digest: str, hmac_secret: str | None = None) -> str:
    config = _ARTIFACT_HMAC_CONFIG.get(artifact_type)
    if not config:
        raise ValueError(f"unknown_artifact_type:{artifact_type}")
    return sign_hmac_digest(
        key_id=key_id,
        signed_digest=signed_digest,
        specific_env_prefix=config["specific_env_prefix"],
        generic_env_var=config["generic_env_var"],
        fallback_namespace=config["fallback_namespace"],
        hmac_secret=hmac_secret,
    )


def verify_artifact_hmac_digest_signature(
    *, artifact_type: str, key_id: str, signed_digest: str, signature: str, hmac_secret: str | None = None
) -> bool:
    config = _ARTIFACT_HMAC_CONFIG.get(artifact_type)
    if not config:
        return False
    return verify_hmac_digest_signature(
        key_id=key_id,
        signed_digest=signed_digest,
        signature=signature,
        specific_env_prefix=config["specific_env_prefix"],
        generic_env_var=config["generic_env_var"],
        fallback_namespace=config["fallback_namespace"],
        hmac_secret=hmac_secret,
    )


def verify_payload_signature(
    payload: bytes,
    signature: str,
    key_id: str,
    *,
    specific_env_prefix: str = "ADAAD_SIGNING_KEY_",
    generic_env_var: str = "ADAAD_SIGNING_KEY",
    fallback_namespace: str = "adaad-signing-dev-secret",
) -> bool:
    """Verify payload-coupled signatures using deterministic static or HMAC formats."""

    if not signature:
        return False
    payload_text = payload.decode("utf-8", errors="ignore")
    if payload_text.startswith("sha256:") and len(payload_text) == len("sha256:") + 64:
        signed_digest = payload_text
    else:
        signed_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if signature in {f"cryovant-static-{signed_digest}", f"cryovant-static-{signed_digest.split(':', 1)[1]}"}:
        return True
    if verify_hmac_digest_signature(
        key_id=key_id,
        signed_digest=signed_digest,
        signature=signature,
        specific_env_prefix=specific_env_prefix,
        generic_env_var=generic_env_var,
        fallback_namespace=fallback_namespace,
    ):
        return True
    try:
        return verify_signature(signature)
    except (FileNotFoundError, ValueError, OSError):
        return False


def verify_session(token: str) -> bool:
    """Validate a Cryovant session token.

    Deprecated: production session verification is not yet implemented. This
    helper only supports explicit development token override via
    ``CRYOVANT_DEV_TOKEN`` and returns ``False`` otherwise.
    """
    import warnings

    warnings.warn(
        "verify_session is not production-ready and always returns False "
        "unless CRYOVANT_DEV_TOKEN is set. Do not use for access control.",
        DeprecationWarning,
        stacklevel=2,
    )
    dev_token = os.environ.get("CRYOVANT_DEV_TOKEN", "").strip()
    if dev_token and token == dev_token:
        return True
    return False


def _dev_signature_allowed(signature: str) -> bool:
    if not signature.startswith("cryovant-dev-"):
        return False
    # Defense in depth: require explicit dev environment *and* dev-mode opt-in.
    return env_mode() == "dev" and dev_mode()


def verify_signature(signature: str) -> bool:
    """Verify HMAC-SHA-256 signature against key material in ``KEYS_DIR``.

    Signature format: ``<key_id>:<sha256_hex>`` where digest is calculated as
    ``HMAC_SHA256(key_bytes, b"cryovant")``.
    """

    raw = str(signature or "").strip()
    if not KEYS_DIR.exists():
        raise FileNotFoundError(f"keys_dir_missing:{KEYS_DIR}")
    if ":" not in raw:
        raise ValueError("invalid_signature_format")
    key_id, provided = raw.split(":", 1)
    key_id = key_id.strip()
    provided = provided.strip().lower()
    if not key_id or len(provided) != 64 or any(ch not in "0123456789abcdef" for ch in provided):
        raise ValueError("invalid_signature_format")

    key_path = None
    for suffix in (".key", ".pem", ".txt"):
        candidate = KEYS_DIR / f"{key_id}{suffix}"
        if candidate.exists():
            key_path = candidate
            break
    if key_path is None:
        raise FileNotFoundError(f"key_missing:{key_id}")

    key_material = key_path.read_bytes().strip()
    if not key_material:
        raise ValueError(f"key_empty:{key_id}")

    expected = hmac.new(key_material, b"cryovant", hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, expected)


def _valid_signature(
    signature: str,
    *,
    agent_dir: Path | None = None,
    lineage_hash: str | None = None,
) -> bool:
    """Validate certificate signatures with HMAC-first + legacy fallback.

    When ``lineage_hash`` is provided, it is treated as authoritative and
    ``agent_dir`` is not re-hashed. Callers passing both must ensure the hash
    matches the referenced agent state.
    """
    if not signature:
        return False

    if agent_dir is not None or lineage_hash:
        resolved_lineage_hash = lineage_hash or (compute_lineage_hash(agent_dir) if agent_dir is not None else "")
        signed_digest = f"sha256:{resolved_lineage_hash}"
        if verify_payload_signature(
            payload=signed_digest.encode("utf-8"),
            signature=signature,
            key_id="agent-certificate",
        ):
            return True

    if _legacy_static_signature_allowed(signature) or _dev_signature_allowed(signature):
        metrics.log(
            event_type="cryovant_legacy_signature_accepted",
            payload={"signature_prefix": signature[:24], "env_mode": env_mode()},
            level="WARNING",
            element_id=ELEMENT_ID,
        )
        return True

    return False


def signature_valid(signature: str) -> bool:
    """
    Public validation helper that accepts either a real signature or explicitly
    dev-gated cryovant-dev-* signatures.
    """
    keys_configured = _keys_configured()
    if not keys_configured:
        metrics.log(
            event_type="cryovant_signature_verification_without_keys",
            payload={"env_mode": env_mode(), "signature_prefix": signature[:24]},
            level="CRITICAL",
            element_id=ELEMENT_ID,
        )
        if env_mode() != "dev":
            return False

    try:
        verified = verify_signature(signature)
    except (FileNotFoundError, ValueError, OSError):
        verified = False

    if verified:
        return True

    if _dev_signature_allowed(signature):
        metrics.log(
            event_type="cryovant_dev_signature_accepted",
            payload={"env_mode": env_mode(), "signature_prefix": signature[:24], "dev_mode": dev_mode()},
            level="WARNING",
            element_id=ELEMENT_ID,
        )
        return True

    return False


def dev_signature_allowed(signature: str) -> bool:
    """
    Public helper exposing dev signature acceptance rules for callers that want to
    differentiate between verified and dev-signed flows.
    """
    return _dev_signature_allowed(signature)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, JSONDecodeError, TypeError):
        return {}


def _rotation_interval_seconds(metadata: Dict[str, Any]) -> int:
    env_value = os.environ.get("CRYOVANT_KEY_ROTATION_INTERVAL_SECONDS", "").strip()
    if env_value:
        try:
            return max(0, int(env_value))
        except ValueError:
            pass
    try:
        return max(0, int(metadata.get("interval_seconds", DEFAULT_ROTATION_INTERVAL_SECONDS)))
    except (TypeError, ValueError):
        return DEFAULT_ROTATION_INTERVAL_SECONDS


def _load_rotation_metadata() -> Dict[str, Any]:
    metadata = _read_json(ROTATION_METADATA_PATH)
    interval_seconds = _rotation_interval_seconds(metadata)
    metadata.setdefault("interval_seconds", interval_seconds)
    metadata.setdefault("last_rotation_ts", 0)
    metadata.setdefault("last_rotation_iso", "")
    return metadata


def _persist_rotation_metadata(metadata: Dict[str, Any]) -> None:
    ROTATION_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    ROTATION_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _maybe_rotate_keys(app_agents_dir: Path, agent_count: int) -> bool:
    """
    Track key rotation metadata and emit rotation events when the interval elapses.
    """
    metadata = _load_rotation_metadata()
    interval_seconds = _rotation_interval_seconds(metadata)
    now = time.time()
    last_rotation = metadata.get("last_rotation_ts") or 0
    due = last_rotation <= 0 or (interval_seconds and now - float(last_rotation) >= interval_seconds)
    if not due:
        return False
    try:
        metadata.update(
            {
                "interval_seconds": interval_seconds,
                "last_rotation_ts": int(now),
                "last_rotation_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            }
        )
        _persist_rotation_metadata(metadata)
        journal.record_rotation_event(
            action="key_rotation",
            payload={
                "interval_seconds": interval_seconds,
                "last_rotation_ts": metadata["last_rotation_ts"],
                "last_rotation_iso": metadata["last_rotation_iso"],
                "keys_dir": str(KEYS_DIR),
                "agents_dir": str(app_agents_dir),
                "agent_count": agent_count,
            },
        )
        metrics.log(
            event_type="key_rotation",
            payload={
                "interval_seconds": interval_seconds,
                "last_rotation_ts": metadata["last_rotation_ts"],
                "last_rotation_iso": metadata["last_rotation_iso"],
                "agents_dir": str(app_agents_dir),
                "agent_count": agent_count,
            },
            level="INFO",
            element_id=ELEMENT_ID,
        )
        return True
    except (OSError, TypeError, ValueError) as exc:
        journal.record_rotation_failure(
            action="key_rotation_failed",
            payload={
                "reason_code": "rotation_metadata_persist_failed",
                "operation_class": "governance-critical",
                "interval_seconds": interval_seconds,
                "last_rotation_ts": metadata.get("last_rotation_ts"),
                "error": str(exc),
                "error_type": type(exc).__name__,
                "keys_dir": str(KEYS_DIR),
                "agents_dir": str(app_agents_dir),
            },
        )
        metrics.log(
            event_type="key_rotation_failed",
            payload={
                "reason_code": "rotation_metadata_persist_failed",
                "operation_class": "governance-critical",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "keys_dir": str(KEYS_DIR),
                "agents_dir": str(app_agents_dir),
            },
            level="ERROR",
            element_id=ELEMENT_ID,
        )
        return False

def compute_lineage_hash(agent_dir: Path) -> str:
    """
    Compute a stable hash over agent metadata triplet.
    """
    meta = _read_json(agent_dir / "meta.json")
    dna = _read_json(agent_dir / "dna.json")
    certificate = _read_json(agent_dir / "certificate.json")
    bundle = {"certificate.json": certificate, "dna.json": dna, "meta.json": meta}
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evolve_certificate(agent_id: str, agent_dir: Path, mutation_dir: Path, capabilities_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update the agent certificate with lineage hash and signature.
    """
    certificate_path = agent_dir / "certificate.json"
    existing_cert = _read_json(certificate_path)
    meta = _read_json(agent_dir / "meta.json")
    dna = _read_json(agent_dir / "dna.json")
    base_certificate: Dict[str, Any] = {
        "issuer": "cryovant-dev",
        "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "issued_from": str(mutation_dir),
        "capabilities_snapshot": capabilities_snapshot,
    }
    for key, value in existing_cert.items():
        if key not in base_certificate:
            base_certificate[key] = value

    bundle = {"certificate.json": base_certificate, "dna.json": dna, "meta.json": meta}
    lineage_hash = hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    signature = existing_cert.get("signature")
    if not _valid_signature(signature or "", agent_dir=agent_dir, lineage_hash=lineage_hash):
        signature = f"cryovant-dev-{lineage_hash[:12]}"

    certificate = {**base_certificate, "lineage_hash": lineage_hash, "signature": signature}
    certificate_path.write_text(json.dumps(certificate, indent=2), encoding="utf-8")
    journal.write_entry(
        agent_id=agent_id,
        action="certificate_evolved",
        payload={"mutation_dir": str(mutation_dir), "lineage_hash": lineage_hash},
    )
    metrics.log(
        event_type="certificate_evolved",
        payload={"agent": agent_id, "mutation_dir": str(mutation_dir), "lineage_hash": lineage_hash},
        level="INFO",
        element_id=ELEMENT_ID,
    )
    return certificate


def validate_environment() -> bool:
    """
    Ensure ledger and keys directories exist and ledger is writable.
    """
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(KEYS_DIR), 0o700)
    except OSError:
        pass

    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    probe = LEDGER_DIR / ".write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        metrics.log(
            event_type="cryovant_environment_invalid",
            payload={
                "reason_code": "ledger_probe_write_failed",
                "operation_class": "boot-critical",
                "ledger_dir": str(LEDGER_DIR),
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            level="ERROR",
            element_id=ELEMENT_ID,
        )
        return False

    try:
        ledger_file = journal.ensure_ledger()
        journal.write_entry(agent_id="system", action="env_check", payload={"check": "environment_ok"})
    except (OSError, TypeError, ValueError) as exc:  # pragma: no cover - defensive logging
        metrics.log(
            event_type="cryovant_environment_error",
            payload={
                "reason_code": "ledger_bootstrap_failed",
                "operation_class": "boot-critical",
                "ledger_dir": str(LEDGER_DIR),
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            level="ERROR",
            element_id=ELEMENT_ID,
        )
        raise RuntimeError("cryovant_bootstrap_failed:ledger_bootstrap_failed") from exc

    metrics.log(
        event_type="cryovant_environment_valid",
        payload={"ledger_dir": str(LEDGER_DIR), "ledger_file": str(ledger_file), "keys_dir": str(KEYS_DIR)},
        level="INFO",
        element_id=ELEMENT_ID,
    )
    return True


def certify_agents(app_agents_dir: Path) -> Tuple[bool, List[str]]:
    """
    Validate that each agent contains the required metadata triplet and signed certificate.
    """
    missing: List[str] = []
    signature_failures: List[str] = []
    agents_root = Path(app_agents_dir)
    if not agents_root.exists():
        metrics.log(event_type="cryovant_no_agents_dir", payload={"path": str(app_agents_dir)}, level="ERROR", element_id=ELEMENT_ID)
        return False, [f"missing agents directory: {app_agents_dir}"]

    agent_dirs = list(iter_agent_dirs(agents_root))
    rotation_performed = _maybe_rotate_keys(agents_root, len(agent_dirs))
    if not agent_dirs:
        metrics.log(event_type="cryovant_certified", payload={"agents_dir": str(app_agents_dir), "agents": 0}, level="INFO", element_id=ELEMENT_ID)
        return True, []

    lineage_hash_cache: Dict[Path, str] = {}

    for candidate in agent_dirs:
        agent_id = resolve_agent_id(candidate, agents_root)
        meta = candidate / "meta.json"
        dna = candidate / "dna.json"
        cert = candidate / "certificate.json"
        for required in (meta, dna, cert):
            if not required.exists():
                missing.append(f"{agent_id}:{required.name}")
        if cert.exists():
            certificate = _read_json(cert)
            signature = certificate.get("signature", "")

            if candidate not in lineage_hash_cache:
                lineage_hash_cache[candidate] = compute_lineage_hash(candidate)
            computed_lineage_hash = lineage_hash_cache[candidate]

            lineage_hash = certificate.get("lineage_hash")
            if not lineage_hash and _valid_signature(signature, agent_dir=candidate, lineage_hash=computed_lineage_hash):
                lineage_hash = computed_lineage_hash
                certificate["lineage_hash"] = lineage_hash
                cert.write_text(json.dumps(certificate, indent=2), encoding="utf-8")
                journal.write_entry(agent_id=agent_id, action="certificate_evolved", payload={"lineage_hash": lineage_hash})
            if not _valid_signature(signature, agent_dir=candidate, lineage_hash=computed_lineage_hash):
                signature_failures.append(agent_id)
    if missing or signature_failures:
        errors = missing + [f"{name}:invalid_signature" for name in signature_failures]
        metrics.log(event_type="cryovant_certify_failed", payload={"missing": errors}, level="ERROR", element_id=ELEMENT_ID)
        for agent in signature_failures:
            journal.write_entry(agent_id=agent, action="certify_failed", payload={"reason": "invalid_signature"})
        if rotation_performed:
            metrics.log(
                event_type="rotation_revalidation_failed",
                payload={"errors": errors, "agents_dir": str(app_agents_dir), "agent_count": len(agent_dirs)},
                level="ERROR",
                element_id=ELEMENT_ID,
            )
        return False, errors

    for candidate in agent_dirs:
        agent_id = resolve_agent_id(candidate, agents_root)
        certificate = _read_json(candidate / "certificate.json")
        payload = {"path": str(candidate), "lineage_hash": certificate.get("lineage_hash")}
        journal.write_entry(agent_id=agent_id, action="certified", payload=payload)

    if rotation_performed:
        metrics.log(
            event_type="rotation_revalidation_ok",
            payload={"agents_dir": str(app_agents_dir), "agent_count": len(agent_dirs)},
            level="INFO",
            element_id=ELEMENT_ID,
        )
    metrics.log(event_type="cryovant_certified", payload={"agents_dir": str(app_agents_dir), "agents": len(agent_dirs)}, level="INFO", element_id=ELEMENT_ID)
    return True, []


def validate_ancestry(agent_id: Optional[str]) -> bool:
    """
    Ensure the agent lineage is known before mutation cycles proceed.
    """
    entries = journal.read_entries(limit=200)
    known_ids = {entry.get("agent_id") for entry in entries}
    if not agent_id:
        metrics.log(event_type="cryovant_invalid_agent_id", payload={}, level="ERROR", element_id=ELEMENT_ID)
        journal.write_entry(agent_id="unknown", action="ancestry_failed", payload={"reason": "missing_id"})
        return False

    if not known_ids:
        if os.environ.get("ADAAD_ALLOW_GENESIS", "0") == "1":
            journal.write_entry(
                agent_id=agent_id,
                action="ancestry_validated",
                payload={"reason": "genesis_override_allowed"},
            )
            metrics.log(
                event_type="cryovant_genesis_override_allowed",
                payload={"agent_id": agent_id, "reason": "genesis_override_allowed"},
                level="WARNING",
                element_id=ELEMENT_ID,
            )
            return True

        journal.write_entry(
            agent_id=agent_id,
            action="ancestry_failed",
            payload={"reason": "empty_journal_denied"},
        )
        metrics.log(
            event_type="cryovant_empty_journal_denied",
            payload={"agent_id": agent_id, "reason": "empty_journal_denied"},
            level="ERROR",
            element_id=ELEMENT_ID,
        )
        return False

    if known_ids and agent_id not in known_ids:
        metrics.log(
            event_type="cryovant_unknown_ancestry",
            payload={"agent_id": agent_id, "known": list(known_ids), "reason": "unknown_ancestry"},
            level="ERROR",
            element_id=ELEMENT_ID,
        )
        journal.write_entry(
            agent_id=agent_id,
            action="ancestry_failed",
            payload={"known": list(known_ids), "reason": "unknown_ancestry"},
        )
        return False

    journal.write_entry(agent_id=agent_id, action="ancestry_validated", payload={})
    metrics.log(event_type="cryovant_ancestry_valid", payload={"agent_id": agent_id}, level="INFO", element_id=ELEMENT_ID)
    return True
