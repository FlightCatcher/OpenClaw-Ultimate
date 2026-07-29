from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from openclaw_ultimate.integrations.mcp import (
    McpConfigurationError,
    McpServerConfig,
    McpServerRegistry,
    StdioMcpClient,
)


def test_registry_loads_only_enabled_allowlisted_servers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "servers.json"
    path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "enabled",
                        "command": ["python", "-m", "server"],
                    },
                    {
                        "name": "disabled",
                        "enabled": False,
                        "command": ["python", "-m", "other"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    registry = McpServerRegistry.load(path)

    assert registry.names() == ("enabled",)

    with pytest.raises(McpConfigurationError, match="not allowlisted"):
        registry.get("disabled")


def test_registry_resolves_relative_config_against_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_root = tmp_path / "project"
    config_path = config_root / "configs" / "mcp.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "local",
                        "command": ["python", "server.py"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    unrelated_root = tmp_path / "unrelated"
    unrelated_root.mkdir()
    monkeypatch.chdir(unrelated_root)

    registry = McpServerRegistry.load(
        Path("configs/mcp.json"),
        project_root=config_root,
    )

    assert registry.names() == ("local",)


def test_stdio_mcp_client_lists_and_calls_tools(
    tmp_path: Path,
) -> None:
    server_path = tmp_path / "fake_mcp.py"
    server_path.write_text(
        """
import json
import sys

for line in sys.stdin:
    message = json.loads(line)
    request_id = message.get("id")
    method = message.get("method")

    if request_id is None:
        continue

    if method == "initialize":
        result = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake", "version": "1"},
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "echo",
                    "description": "Echo text",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                }
            ]
        }
    elif method == "tools/call":
        text = message["params"]["arguments"]["text"]
        result = {
            "content": [{"type": "text", "text": text}],
            "isError": False,
            "structuredContent": {"echo": text},
        }
    else:
        result = {}

    print(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        ),
        flush=True,
    )
""".strip(),
        encoding="utf-8",
    )
    config = McpServerConfig(
        name="fake",
        command=(sys.executable, str(server_path)),
    )

    # Windows process startup can exceed three seconds on a busy local AI
    # workstation even though the stdio protocol is healthy.
    with StdioMcpClient(config, timeout=10) as client:
        tools = client.list_tools()
        result = client.call_tool(
            "echo",
            {"text": "hello"},
        )

    assert tools[0].name == "echo"
    assert result.is_error is False
    assert result.structured_content == {"echo": "hello"}


def test_stdio_mcp_client_rejects_unadvertised_tool(
    tmp_path: Path,
) -> None:
    server_path = tmp_path / "fake_mcp.py"
    server_path.write_text(
        """
import json
import sys

for line in sys.stdin:
    message = json.loads(line)
    if message.get("id") is None:
        continue
    method = message.get("method")
    result = (
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake", "version": "1"},
        }
        if method == "initialize"
        else {"tools": []}
    )
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
""".strip(),
        encoding="utf-8",
    )

    with (
        StdioMcpClient(
            McpServerConfig(
                name="fake",
                command=(sys.executable, str(server_path)),
            ),
            timeout=3,
        ) as client,
        pytest.raises(McpConfigurationError, match="not advertised"),
    ):
        client.call_tool("missing", {})
