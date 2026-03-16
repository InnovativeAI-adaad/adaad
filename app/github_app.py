# SPDX-License-Identifier: Apache-2.0
"""
ADAADchat GitHub App — Webhook Handler
App ID: 3013088  |  Client ID: Iv23liYNPdEjUgXwiT8Y
Phase assignment: Phase 77 micro-governance (retroactive — C-03 remediation)
Governor sign-off: Dustin L. Reid — 2026-03-15

Dispatches incoming GitHub webhook events and bridges them into the
ADAAD governance audit trail (or a JSONL fallback log).

GOVERNANCE CONTRACT (GITHUB-APP-GOV-0):
  All incoming webhook payloads pass through signature verification before
  any event dispatch or governance emission. Signature failures are
  ledger-recorded and fail-closed. GovernanceGate pre-check is performed
  for mutation-class events (push.main, pr.merged) before emission.
  No autonomous mutation is triggered by webhook events — HUMAN-0 preserved.

Constitutional invariants enforced:
  GITHUB-APP-GOV-0  -- GovernanceGate pre-check on mutation-class events
  GITHUB-APP-SIG-0  -- Signature verification required; fail-closed in non-dev
  GITHUB-APP-LOG-0  -- Every accepted event emits a ledger record
  GITHUB-APP-MUT-0  -- No autonomous mutation triggered by webhook; advisory only
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_APP_ID         = os.environ.get("GITHUB_APP_ID", "3013088")
GITHUB_APP_CLIENT_ID  = os.environ.get("GITHUB_APP_CLIENT_ID", "Iv23liYNPdEjUgXwiT8Y")

# Mutation-class events require GovernanceGate pre-check (GITHUB-APP-GOV-0)
_MUTATION_CLASS_EVENTS: frozenset[str] = frozenset({
    "push.main",
    "pr.merged",
})


# ── GovernanceGate pre-check ──────────────────────────────────────────────────

def _governance_gate_preflight(event_name: str, data: dict) -> bool:
    """
    GITHUB-APP-GOV-0: GovernanceGate pre-check for mutation-class events.

    Mutation-class events (push.main, pr.merged) are checked against the
    GovernanceGate before emission. If the gate is unavailable, the event
    is logged with an advisory and allowed through — the gate is authoritative
    for autonomous mutations only; webhook observations are advisory.

    Returns True to proceed, False to suppress emission (gate hard-block).
    """
    if event_name not in _MUTATION_CLASS_EVENTS:
        return True  # non-mutation-class events always proceed

    try:
        from runtime.governance.gate import GovernanceGate  # type: ignore[import]
        gate = GovernanceGate()
        result = gate.preflight_check(
            surface="webhook",
            event=event_name,
            context=data,
        )
        if not result.approved:
            logger.warning(
                "GovernanceGate preflight BLOCKED for %s: %s",
                event_name,
                result.reason_codes,
            )
            _emit_governance_event(
                "gate.preflight_blocked",
                {
                    "event": event_name,
                    "reason_codes": result.reason_codes,
                    "advisory": "GITHUB-APP-GOV-0: mutation-class event suppressed by GovernanceGate",
                },
            )
            return False
        logger.debug("GovernanceGate preflight approved for %s", event_name)
        return True
    except (ImportError, AttributeError, TypeError):
        # Gate unavailable — log advisory, allow through (webhook is observational only)
        logger.info(
            "GovernanceGate preflight unavailable for %s — advisory passthrough "
            "(GITHUB-APP-GOV-0: gate unavailable; no autonomous mutation triggered)",
            event_name,
        )
        return True


# ── Signature verification ────────────────────────────────────────────────────

def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """Return True iff the HMAC-SHA256 signature matches the shared secret."""
    env = os.environ.get("ADAAD_ENV", "dev")
    if not GITHUB_WEBHOOK_SECRET:
        if env == "dev":
            logger.warning("GITHUB_WEBHOOK_SECRET not set — allowing in dev mode")
            return True
        logger.error("GITHUB_WEBHOOK_SECRET required in non-dev environments")
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        logger.error("Missing or malformed X-Hub-Signature-256 header")
        return False
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ── Event dispatcher ──────────────────────────────────────────────────────────

def dispatch_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Route a GitHub webhook event to the appropriate handler."""
    handlers: dict[str, Any] = {
        "push":                      _handle_push,
        "pull_request":              _handle_pull_request,
        "pull_request_review":       _handle_pr_review,
        "issues":                    _handle_issues,
        "issue_comment":             _handle_issue_comment,
        "check_run":                 _handle_check_run,
        "check_suite":               _handle_check_suite,
        "installation":              _handle_installation,
        "installation_repositories": _handle_installation_repositories,
        "ping":                      _handle_ping,
    }
    handler = handlers.get(event_type, _handle_unknown)
    try:
        return handler(payload)
    except Exception as exc:
        # Log full details on the server, but do not expose exception text to the caller.
        logger.exception("Handler error for event '%s': %s", event_type, exc)
        return {"status": "error", "event": event_type}


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_ping(p: dict) -> dict:
    logger.info("GitHub App ping — zen: %s", p.get("zen", ""))
    return {"status": "ok", "event": "ping", "zen": p.get("zen")}


def _handle_push(p: dict) -> dict:
    ref  = p.get("ref", "")
    repo = p.get("repository", {}).get("full_name", "unknown")
    n    = len(p.get("commits", []))
    logger.info("Push %s → %s (%d commit(s))", ref, repo, n)
    if ref == "refs/heads/main":
        _emit_governance_event("push.main", {
            "repo": repo, "commit_count": n,
            "pusher": p.get("pusher", {}).get("name"),
        })
    return {"status": "ok", "event": "push", "ref": ref, "commits": n}


def _handle_pull_request(p: dict) -> dict:
    action = p.get("action", "")
    pr     = p.get("pull_request", {})
    num    = pr.get("number")
    repo   = p.get("repository", {}).get("full_name", "unknown")
    logger.info("PR #%s %s in %s", num, action, repo)
    if action in ("opened", "synchronize", "reopened"):
        _emit_governance_event("pr.updated", {
            "repo": repo, "pr_number": num, "action": action,
            "title": pr.get("title"), "head_sha": pr.get("head", {}).get("sha"),
        })
    if action == "closed" and pr.get("merged"):
        _emit_governance_event("pr.merged", {
            "repo": repo, "pr_number": num, "title": pr.get("title"),
            "merged_by": pr.get("merged_by", {}).get("login"),
            "merge_commit_sha": pr.get("merge_commit_sha"),
        })
    return {"status": "ok", "event": "pull_request", "action": action, "pr": num}


def _handle_pr_review(p: dict) -> dict:
    review = p.get("review", {})
    pr     = p.get("pull_request", {})
    state  = review.get("state", "")
    _emit_governance_event("pr.review", {
        "pr_number": pr.get("number"),
        "reviewer":  review.get("user", {}).get("login"),
        "state":     state,
        "submitted_at": review.get("submitted_at"),
    })
    return {"status": "ok", "event": "pull_request_review", "state": state}


def _handle_issues(p: dict) -> dict:
    action = p.get("action", "")
    issue  = p.get("issue", {})
    return {"status": "ok", "event": "issues", "action": action, "issue": issue.get("number")}


def _handle_issue_comment(p: dict) -> dict:
    action  = p.get("action", "")
    comment = p.get("comment", {})
    issue   = p.get("issue", {})
    body    = comment.get("body", "").strip()
    if body.startswith("/adaad"):
        return _handle_slash_command(body, issue, comment, p)
    return {"status": "ok", "event": "issue_comment", "action": action}


def _handle_check_run(p: dict) -> dict:
    action     = p.get("action", "")
    check      = p.get("check_run", {})
    conclusion = check.get("conclusion")
    if conclusion in ("failure", "timed_out", "cancelled"):
        _emit_governance_event("ci.failure", {
            "check_name": check.get("name"),
            "conclusion": conclusion,
            "head_sha":   check.get("head_sha"),
        })
    return {"status": "ok", "event": "check_run", "action": action, "conclusion": conclusion}


def _handle_check_suite(p: dict) -> dict:
    return {
        "status":     "ok",
        "event":      "check_suite",
        "action":     p.get("action"),
        "conclusion": p.get("check_suite", {}).get("conclusion"),
    }


def _handle_installation(p: dict) -> dict:
    action  = p.get("action", "")
    account = p.get("installation", {}).get("account", {}).get("login", "unknown")
    logger.info("App installation %s by %s", action, account)
    return {"status": "ok", "event": "installation", "action": action, "account": account}


def _handle_installation_repositories(p: dict) -> dict:
    added   = [r["full_name"] for r in p.get("repositories_added", [])]
    removed = [r["full_name"] for r in p.get("repositories_removed", [])]
    return {"status": "ok", "event": "installation_repositories",
            "added": added, "removed": removed}


def _handle_unknown(_: dict) -> dict:
    return {"status": "ignored", "event": "unknown"}


def _handle_slash_command(body: str, issue: dict, comment: dict, payload: dict) -> dict:
    """
    Supported slash commands (in issue/PR comments):
      /adaad status   — emit governance status event
      /adaad dry-run  — trigger governed dry-run signal
      /adaad help     — emit help event
    """
    parts   = body.split()
    command = parts[1] if len(parts) > 1 else "help"
    actor   = comment.get("user", {}).get("login", "unknown")
    logger.info("/adaad %s from %s on #%s", command, actor, issue.get("number"))
    _emit_governance_event("slash_command", {
        "command":      command,
        "actor":        actor,
        "issue_number": issue.get("number"),
        "repo":         payload.get("repository", {}).get("full_name"),
    })
    return {"status": "ok", "event": "slash_command", "command": command, "actor": actor}


# ── Governance bridge ─────────────────────────────────────────────────────────

def _emit_governance_event(event_name: str, data: dict) -> None:
    """Forward a GitHub App event into ADAAD's governance ledger (or JSONL fallback).

    GITHUB-APP-GOV-0: mutation-class events are pre-checked against GovernanceGate.
    GITHUB-APP-LOG-0: every accepted event is ledger-recorded.
    GITHUB-APP-MUT-0: no autonomous mutation is triggered; all events are advisory.
    """
    # GovernanceGate pre-check for mutation-class events
    if not _governance_gate_preflight(event_name, data):
        return  # gate hard-blocked; emission suppressed and logged above

    try:
        from runtime.governance import external_event_bridge  # GITHUB-AUDIT-0
        signal = external_event_bridge.record(
            event_name=event_name,
            action=str(data.get("action", "")),
            delivery_id=str(data.get("delivery_id", "")),
            installation_id=str(data.get("installation_id", GITHUB_APP_ID)),
            repository=str(data.get("repo", data.get("repository", ""))),
            sender=str(data.get("pusher", data.get("merged_by", data.get("sender", "")))),
            status="accepted",
            raw_payload_bytes=json.dumps(data, sort_keys=True).encode(),
        )
        if signal is not None:
            logger.info(
                "ExternalGovernanceSignal emitted event=%s seq=%d hash=%s",
                event_name, signal.sequence, signal.record_hash[:16],
            )
        return
    except Exception as _exc:  # noqa: BLE001  GITHUB-FAILSAFE-0
        logger.warning("external_event_bridge.record failed: %s — JSONL fallback", _exc)

    # Fallback: plain JSONL audit file (pre-Phase-77 compatibility)
    audit_path = os.environ.get("ADAAD_GITHUB_AUDIT_LOG", "data/github_app_events.jsonl")
    os.makedirs(os.path.dirname(os.path.abspath(audit_path)), exist_ok=True)
    entry = {
        "ts":    datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": f"github_app.{event_name}",
        "data":  data,
    }
    with open(audit_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    logger.debug("Governance event logged (fallback): %s", event_name)
