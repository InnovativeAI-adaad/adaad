# Control Plane Authentication Requirements

Control-plane write APIs (`/control/*` POST mutations) must enforce the same trust boundary as MCP mutation endpoints.

## Mandatory requirements

- Require JWT validation through `_require_jwt()` before processing write payloads.
- Reject missing/invalid/expired tokens with structured JSON `401` responses (`{"ok": false, "error": "..."}`).
- Apply browser-oriented origin checks when `Origin` or `Referer` headers are present; reject invalid origins with structured `403` responses.
- Enforce nonce replay protection (`X-APONI-Nonce`) for control-plane writes.
- Emit audit log events for authorization failures, including client IP, path, status, and reason.

## Scope

These requirements apply to:

- `/control/queue`
- `/control/queue/cancel`
- `/control/execution`
- Other future control-plane mutation endpoints.

Environment flags (for example command-surface toggles) are defense-in-depth only and are **not** a substitute for cryptographic authentication.

## FastAPI enforcement path note (auditability)

For server-side FastAPI routes, auth and gate checks should be routed through shared dependencies in `app/api/dependencies.py` (`auth_context`, `require_audit_scope`, `require_gate_open`) so future audits can verify a single enforcement path instead of per-endpoint inline logic.
