# SPDX-License-Identifier: Apache-2.0
"""GitHub webhook handler — governed shim (Phase 77 consolidation).

This module previously contained a duplicate, ungoverned webhook implementation.
It has been consolidated into ``app.github_app`` as part of Track A / Phase 77
(dual-handler audit finding C-03 remnant closure).

All event dispatch, signature verification, and ledger emission now route
through ``app.github_app``, which enforces:

  GITHUB-APP-GOV-0  — GovernanceGate pre-check on mutation-class events
  GITHUB-APP-SIG-0  — HMAC-SHA256 signature verification; fail-closed
  GITHUB-APP-LOG-0  — every accepted event emits a ledger record
  GITHUB-APP-MUT-0  — no autonomous mutation triggered; advisory only

Public API (preserved for backwards-compatibility)
──────────────────────────────────────────────────
  verify_webhook_signature(payload_bytes, sig_header) → bool
  handle_webhook(payload_bytes, event_type, signature, delivery_id) → (int, dict)
  handle_push(payload)          → dict
  handle_pull_request(payload)  → dict
  handle_check_run(payload)     → dict
  handle_workflow_run(payload)  → dict
  handle_installation(payload)  → dict
  EVENT_HANDLERS                → dict
  HANDLED_EVENTS                → set

Constitutional invariants:
  WEBHOOK-SHIM-DELEG-0  This module never re-implements signature verification
                         or ledger emission; it delegates 100% to app.github_app.
  WEBHOOK-SHIM-COMPAT-0 The public API surface is preserved for import
                         compatibility only; no governance logic lives here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.github_app import dispatch_event, verify_webhook_signature

logger = logging.getLogger("adaad.github_webhook")

HANDLED_EVENTS = {
    "push", "pull_request", "pull_request_review",
    "check_run", "check_suite", "workflow_run",
    "installation", "repository",
}

EVENT_HANDLERS: dict[str, Any] = {}


def handle_push(payload: dict) -> dict:
    return dispatch_event("push", payload)


def handle_pull_request(payload: dict) -> dict:
    return dispatch_event("pull_request", payload)


def handle_check_run(payload: dict) -> dict:
    return dispatch_event("check_run", payload)


def handle_workflow_run(payload: dict) -> dict:
    return dispatch_event("workflow_run", payload)


def handle_installation(payload: dict) -> dict:
    return dispatch_event("installation", payload)


EVENT_HANDLERS.update({
    "push": handle_push,
    "pull_request": handle_pull_request,
    "check_run": handle_check_run,
    "workflow_run": handle_workflow_run,
    "installation": handle_installation,
})


def handle_webhook(
    payload_bytes: bytes,
    event_type: str,
    signature: str,
    delivery_id: str | None = None,
) -> tuple[int, dict]:
    """Verify signature then route to governed dispatch_event."""
    if not verify_webhook_signature(payload_bytes, signature):
        logger.warning("webhook_signature_invalid delivery=%s", delivery_id)
        return 401, {"error": "invalid_signature"}
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return 400, {"error": "invalid_json"}
    if event_type not in HANDLED_EVENTS:
        return 200, {"status": "ignored", "event": event_type}
    return 200, dispatch_event(event_type, payload)


__all__ = [
    "HANDLED_EVENTS", "EVENT_HANDLERS", "verify_webhook_signature",
    "handle_webhook", "handle_push", "handle_pull_request",
    "handle_check_run", "handle_workflow_run", "handle_installation",
]
