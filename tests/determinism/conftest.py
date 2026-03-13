# SPDX-License-Identifier: Apache-2.0
"""conftest.py — test fixtures for tests/determinism/

Provides autouse fixtures that inject replay-proof HMAC test secrets so
the keyring loader resolves without placeholder-secret RuntimeErrors in
CI and dev environments where real secrets are not provisioned.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Replay proof HMAC secret injection
#
# The production keyring (security/replay_proof_keyring.json) resolves the
# HMAC secret for "proof-key" via env:ADAAD_REPLAY_PROOF_HMAC_SECRET_PROOF_KEY.
# Tests that call ReplayProofBuilder.build_bundle() need that var set to a
# deterministic test value; without it _load_hmac_replay_proof_keyring() raises
# RuntimeError("replay_proof_keyring_placeholder_secret:proof-key:hmac_secret").
# ---------------------------------------------------------------------------

_TEST_HMAC_SECRET = "adaad-replay-proof-dev-secret:proof-key"


@pytest.fixture(autouse=True)
def _inject_replay_proof_hmac_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject deterministic HMAC + ed25519 test secrets for the replay keyring.

    autouse=True — applies to every test in tests/determinism/ without needing
    explicit fixture requests.

    Secrets injected:
      ADAAD_REPLAY_PROOF_HMAC_SECRET_PROOF_KEY         — "proof-key" HMAC entry
      ADAAD_REPLAY_PROOF_PRIVATE_KEY_REPLAY_PROOF_ED25519_DEV — ed25519 dev key
    """
    monkeypatch.setenv("ADAAD_REPLAY_PROOF_HMAC_SECRET_PROOF_KEY", _TEST_HMAC_SECRET)
    # Base64-encoded 32-byte deterministic test private key (not a real secret)
    monkeypatch.setenv(
        "ADAAD_REPLAY_PROOF_PRIVATE_KEY_REPLAY_PROOF_ED25519_DEV",
        "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
    )
