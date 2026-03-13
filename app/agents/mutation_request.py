# SPDX-License-Identifier: Apache-2.0
"""Compatibility shim; import from adaad.agents.mutation_request instead."""
import warnings

warnings.warn(
    "app.agents is deprecated; import from adaad.agents instead.",
    DeprecationWarning,
    stacklevel=2,
)

from adaad.agents.mutation_request import *  # noqa: F401,F403
