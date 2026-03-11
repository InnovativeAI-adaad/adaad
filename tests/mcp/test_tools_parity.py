import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0
import json

from runtime.mcp.tools_registry import SERVER_TOOLS, tools_list_response


def test_tools_parity_and_structure():
    config = json.loads(open('.github/mcp_config.json', encoding='utf-8').read())
    servers = config["mcpServers"]
    assert set(servers.keys()) == set(SERVER_TOOLS.keys())
    for server, expected in SERVER_TOOLS.items():
        tools = servers[server]["tools"]
        assert tools and all(isinstance(name, str) for name in tools)
        assert tools == expected
        assert len(tools) == len(set(tools))
        resp = tools_list_response(server)
        assert "tools" in resp and isinstance(resp["tools"], list)
        assert [item["name"] for item in resp["tools"]] == expected
