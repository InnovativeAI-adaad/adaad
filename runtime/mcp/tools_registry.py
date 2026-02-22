# SPDX-License-Identifier: Apache-2.0
"""Deterministic MCP tools registry shared by config parity checks and runtime handlers."""

from __future__ import annotations

from typing import Dict, List

SERVER_TOOLS: Dict[str, List[str]] = {
    "aponi-local": [
        "system_intelligence",
        "risk_summary",
        "evolution_timeline",
        "replay_diff",
        "policy_simulate",
        "mutation_analyze",
        "mutation_explain_rejection",
        "mutation_rank",
    ],
    "ledger-mirror": ["ledger_list", "ledger_read"],
    "sandbox-proxy": ["policy_simulate", "skill_profiles_list"],
    "mcp-proposal-writer": [
        "mutation_propose",
        "mutation_analyze",
        "mutation_explain_rejection",
        "mutation_rank",
    ],
}


def list_tools(server_name: str) -> list[dict[str, str]]:
    names = SERVER_TOOLS.get(server_name, [])
    return [{"name": name} for name in names]


def tools_list_response(server_name: str) -> dict:
    return {"tools": list_tools(server_name)}


__all__ = ["SERVER_TOOLS", "list_tools", "tools_list_response"]
