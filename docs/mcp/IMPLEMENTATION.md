# MCP Implementation (Claude-governed co-pilot)

This repository includes a governed MCP integration with four servers and strict tools parity between `.github/mcp_config.json` and `runtime/mcp/tools_registry.py`.

## Architecture

- `app/agents/claude_proposal_agent.py` provides the `claude-proposal-agent` mutator-compatible role implementation.
- `runtime/mcp/server.py` exposes proposal-writer routes and enforces JWT for all non-health endpoints.
- `runtime/mcp/proposal_validator.py` enforces schema, Tier-0 elevation checks, constitutional pre-checks, and authority override invariants.
- `runtime/mcp/tools_registry.py` is the runtime source of truth for MCP tool names.

## Key invariants

- `authority_level` is forced to `governor-review` server-side.
- Tier-0 targets are rejected unless a human `elevation_token` is provided.
- Constitutional evaluation is run before queue append.
- Proposal queue entries are append-only and hash-linked.
- Tool-name parity is exact (same names, order, and set) between config and runtime registry.

## Servers and tool mapping

- `aponi-local` → `system_intelligence`, `risk_summary`, `evolution_timeline`, `replay_diff`, `policy_simulate`, `mutation_analyze`, `mutation_explain_rejection`, `mutation_rank`
- `ledger-mirror` → `ledger_list`, `ledger_read`
- `sandbox-proxy` → `policy_simulate`, `skill_profiles_list`
- `mcp-proposal-writer` → `mutation_propose`, `mutation_analyze`, `mutation_explain_rejection`, `mutation_rank`

## Writer route mapping

- `GET /health` → liveness and server identity
- `GET /tools/list` → tools exposed for the selected MCP server
- `POST /mutation/propose` → validate and enqueue proposal payloads
- `POST /mutation/analyze` → deterministic fitness/risk prediction
- `POST /mutation/explain-rejection` → guard-failure explanation from lifecycle rejection telemetry
- `POST /mutation/rank` → deterministic ranking over mutation IDs

JWT is required for all non-health routes.


## Orchestrator boot integration

- `mcp-proposal-writer` startup checks run only after Cryovant preconditions pass.
- Startup is validated before the mutation cycle transition decision, so boot fails closed if signing/audit prerequisites are unavailable.
- Orchestrator MCP health checks verify required writer routes are present before mutation work proceeds.

## Control-plane parity with MCP mutation auth

Control-plane write routes must follow MCP mutation authentication guarantees. In practice:

- `/control/queue`, `/control/queue/cancel`, and `/control/execution` require JWT validation for writes.
- Browser-originated requests should pass origin/referer validation and nonce checks.
- Auth failures return structured JSON `401/403` payloads and emit audit logs.

This prevents privilege bypass where control-plane writes would otherwise be protected less strictly than MCP mutation endpoints.

