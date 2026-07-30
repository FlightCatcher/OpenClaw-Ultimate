"""Small, useful read-only MCP server shipped with VELA v1.0."""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any


def response(request_id: Any, result: dict[str, Any]) -> None:
    print(
        json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "result": result},
            ensure_ascii=False,
        ),
        flush=True,
    )


def error(request_id: Any, code: int, message: str) -> None:
    print(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def workspace_stats() -> dict[str, Any]:
    root = Path.cwd().resolve()
    files = 0
    directories = 0
    total_bytes = 0
    denied = {".git", ".venv", ".openclaw", "__pycache__"}
    for current_root, names, filenames in os.walk(root):
        names[:] = [name for name in names if name not in denied]
        directories += len(names)
        for filename in filenames:
            path = Path(current_root) / filename
            try:
                total_bytes += path.stat().st_size
                files += 1
            except OSError:
                continue
    return {
        "root": str(root),
        "files": files,
        "directories": directories,
        "total_bytes": total_bytes,
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


TOOLS = [
    {
        "name": "workspace_stats",
        "description": "Return read-only statistics for the VELA workspace.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "echo",
        "description": "Echo text to verify the local MCP path.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
]


def main() -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
            request_id = message.get("id")
            method = message.get("method")
            if request_id is None:
                continue
            if method == "initialize":
                response(
                    request_id,
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "vela-local", "version": "1.1.1"},
                    },
                )
            elif method == "tools/list":
                response(request_id, {"tools": TOOLS})
            elif method == "tools/call":
                params = message.get("params", {})
                name = params.get("name")
                arguments = params.get("arguments", {})
                if name == "workspace_stats":
                    value = workspace_stats()
                elif name == "echo":
                    value = {"echo": str(arguments.get("text", ""))}
                else:
                    error(request_id, -32601, f"Unknown tool: {name}")
                    continue
                response(
                    request_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(value, ensure_ascii=False),
                            }
                        ],
                        "structuredContent": value,
                        "isError": False,
                    },
                )
            else:
                error(request_id, -32601, f"Unknown method: {method}")
        except Exception as exc:  # noqa: BLE001 - MCP boundary must return protocol error
            error(None, -32603, f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
