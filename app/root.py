# SPDX-License-Identifier: Apache-2.0
"""Compatibility shim for application root helpers during rollout."""
import warnings

warnings.warn(
    "app.root is deprecated; import from adaad.core.root instead.",
    DeprecationWarning,
    stacklevel=2,
)

from adaad.core.root import ROOT_DIR, get_root_dir

__all__ = ["ROOT_DIR", "get_root_dir"]
