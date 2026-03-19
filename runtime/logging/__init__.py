# SPDX-License-Identifier: Apache-2.0
"""Structured logging surface for governance and diagnostics."""

from runtime.logging.event_writer import (
    AUDIT_LOG_PATH,
    emit_error,
    emit_governance_diagnostic,
    emit_structured_event,
    emit_warning,
)

__all__ = [
    "AUDIT_LOG_PATH",
    "emit_error",
    "emit_governance_diagnostic",
    "emit_structured_event",
    "emit_warning",
]
