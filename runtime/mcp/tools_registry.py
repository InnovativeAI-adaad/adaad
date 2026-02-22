# SPDX-License-Identifier: Apache-2.0
"""Deterministic MCP tools registry shared by config parity checks and runtime handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

CONFIG_PATH = Path(".github/mcp_config.json")


def _load_tools_from_config() -> Dict[str, List[str]]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    servers = config.get("mcpServers") if isinstance(config.get("mcpServers"), dict) else {}
    loaded: Dict[str, List[str]] = {}
    for server_name, payload in servers.items():
        tool_names = payload.get("tools") if isinstance(payload, dict) else []
        if isinstance(server_name, str) and isinstance(tool_names, list):
            loaded[server_name] = [str(name) for name in tool_names]
    return loaded


SERVER_TOOLS: Dict[str, List[str]] = _load_tools_from_config()


def list_tools(server_name: str) -> list[dict[str, str]]:
    names = SERVER_TOOLS.get(server_name, [])
    return [{"name": name} for name in names]


def tools_list_response(server_name: str) -> dict:
    return {"tools": list_tools(server_name)}


__all__ = ["SERVER_TOOLS", "list_tools", "tools_list_response"]
