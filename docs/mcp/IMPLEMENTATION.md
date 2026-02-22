# MCP Implementation (Claude-governed co-pilot)

This repository includes a governed MCP integration with four servers and strict tools parity between `.github/mcp_config.json` and `runtime/mcp/tools_registry.py`.

## Key invariants

- `authority_level` is forced to `governor-review` server-side.
- Tier-0 targets are rejected unless a human `elevation_token` is provided.
- Constitutional evaluation is run before queue append.
- Proposal queue entries are append-only and hash-linked.

## Servers

- `aponi-local`
- `ledger-mirror`
- `sandbox-proxy`
- `mcp-proposal-writer`

## Writer endpoints

- `POST /mutation/propose`
- `POST /mutation/analyze`
- `POST /mutation/explain-rejection`
- `POST /mutation/rank`
- `GET /health`

JWT is required for all non-health routes.
