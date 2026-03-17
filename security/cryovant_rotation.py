# SPDX-License-Identifier: Apache-2.0
"""Key rotation metadata handling for Cryovant migration."""

from security.cryovant_legacy import (
    DEFAULT_ROTATION_INTERVAL_SECONDS,
    ROTATION_METADATA_PATH,
    _load_rotation_metadata,
    _maybe_rotate_keys,
    _persist_rotation_metadata,
    _rotation_interval_seconds,
)

__all__ = [
    "DEFAULT_ROTATION_INTERVAL_SECONDS",
    "ROTATION_METADATA_PATH",
    "_load_rotation_metadata",
    "_maybe_rotate_keys",
    "_persist_rotation_metadata",
    "_rotation_interval_seconds",
]
