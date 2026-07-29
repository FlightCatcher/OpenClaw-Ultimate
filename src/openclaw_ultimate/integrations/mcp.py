from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Self, TextIO


class McpError(RuntimeError):
    """MCP 客户端或服务器返回了错误。"""


class McpConfigurationError(McpError):
    """MCP 服务器配置无效。"""


class McpProtocolError(McpError):
    """MCP 服务器返回了无效协议消息。"""


class McpTimeoutError(McpError):
    """MCP 请求超过了允许时间。"""


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    name: str
    command: tuple[str, ...]
    cwd: Path | None = None
    env: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise McpConfigurationError("MCP server name cannot be empty.")

        if not self.command or not self.command[0].strip():
            raise McpConfigurationError(f"MCP server '{self.name}' has no executable command.")


@dataclass(frozen=True, slots=True)
class McpTool:
    name: str
    description: str | None
    input_schema: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class McpToolResult:
    content: tuple[Mapping[str, Any], ...]
    is_error: bool
    structured_content: Any = None


class McpServerRegistry:
    """从本地 JSON 白名单加载允许启动的 MCP 服务。"""

    def __init__(
        self,
        servers: Sequence[McpServerConfig] = (),
    ) -> None:
        self._servers = {server.name: server for server in servers if server.enabled}

        if len(self._servers) != len([server for server in servers if server.enabled]):
            raise McpConfigurationError("MCP server names must be unique.")

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        project_root: Path | None = None,
    ) -> McpServerRegistry:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise McpConfigurationError(
                f"Could not read MCP server config '{path}': {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise McpConfigurationError(f"MCP server config '{path}' is not valid JSON.") from exc

        raw_servers = payload.get("servers") if isinstance(payload, dict) else None

        if not isinstance(raw_servers, list):
            raise McpConfigurationError("MCP server config must contain a 'servers' list.")

        return cls(
            tuple(
                cls._parse_server(
                    item,
                    project_root=project_root,
                )
                for item in raw_servers
                if isinstance(item, dict)
            )
        )

    @staticmethod
    def _parse_server(
        raw: Mapping[str, Any],
        *,
        project_root: Path | None = None,
    ) -> McpServerConfig:
        name = raw.get("name")
        command = raw.get("command")
        cwd = raw.get("cwd")
        environment = raw.get("env", {})
        enabled = raw.get("enabled", True)

        if not isinstance(name, str):
            raise McpConfigurationError("MCP server name must be a string.")

        if not isinstance(command, list) or not all(
            isinstance(part, str) and part.strip() for part in command
        ):
            raise McpConfigurationError(f"MCP server '{name}' command must be a string array.")

        if cwd is not None and not isinstance(cwd, str):
            raise McpConfigurationError(f"MCP server '{name}' cwd must be a string.")

        if not isinstance(environment, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in environment.items()
        ):
            raise McpConfigurationError(f"MCP server '{name}' env must map strings to strings.")

        if not isinstance(enabled, bool):
            raise McpConfigurationError(f"MCP server '{name}' enabled must be boolean.")

        def expand(value: str) -> str:
            if project_root is None:
                return value
            return value.replace("{project_root}", str(project_root.resolve()))

        return McpServerConfig(
            name=name,
            command=tuple(expand(part) for part in command),
            cwd=Path(expand(cwd)) if cwd else None,
            env=MappingProxyType({key: expand(value) for key, value in environment.items()}),
            enabled=enabled,
        )

    def get(
        self,
        name: str,
    ) -> McpServerConfig:
        try:
            return self._servers[name]
        except KeyError as exc:
            raise McpConfigurationError(f"MCP server is not allowlisted: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._servers))

    def __len__(self) -> int:
        return len(self._servers)


class StdioMcpClient:
    """最小 MCP stdio JSON-RPC 客户端。

    命令来自本地白名单配置，始终使用 shell=False。每次调用使用独立进程，
    不把模型输入解释为可执行命令。
    """

    protocol_version = "2025-06-18"

    def __init__(
        self,
        config: McpServerConfig,
        *,
        timeout: float = 30.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self.config = config
        self.timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[Any] = queue.Queue()
        self._request_id = 0
        self._reader: threading.Thread | None = None

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return

        environment = os.environ.copy()
        environment.update(self.config.env)

        try:
            self._process = subprocess.Popen(
                list(self.config.command),
                cwd=str(self.config.cwd) if self.config.cwd else None,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
            )
        except OSError as exc:
            raise McpError(f"Could not start MCP server '{self.config.name}': {exc}") from exc

        if self._process.stdout is None:
            raise McpError("MCP server stdout is unavailable.")

        self._reader = threading.Thread(
            target=self._read_messages,
            args=(self._process.stdout,),
            daemon=True,
            name=f"mcp-{self.config.name}-reader",
        )
        self._reader.start()
        self._request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "vela",
                    "version": "1.0.0",
                },
            },
        )
        self._notify("notifications/initialized", {})

    def list_tools(self) -> tuple[McpTool, ...]:
        result = self._request("tools/list", {})
        raw_tools = result.get("tools")

        if not isinstance(raw_tools, list):
            raise McpProtocolError("MCP tools/list result has no tool list.")

        tools: list[McpTool] = []

        for raw in raw_tools:
            if not isinstance(raw, Mapping):
                continue

            name = raw.get("name")
            schema = raw.get("inputSchema", {})

            if not isinstance(name, str) or not isinstance(schema, Mapping):
                raise McpProtocolError("MCP tool definition is invalid.")

            description = raw.get("description")
            tools.append(
                McpTool(
                    name=name,
                    description=description if isinstance(description, str) else None,
                    input_schema=dict(schema),
                )
            )

        return tuple(tools)

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> McpToolResult:
        if not name.strip():
            raise ValueError("tool name cannot be empty.")

        available = {tool.name for tool in self.list_tools()}

        if name not in available:
            raise McpConfigurationError(
                f"MCP tool '{name}' is not advertised by server '{self.config.name}'."
            )

        result = self._request(
            "tools/call",
            {
                "name": name,
                "arguments": dict(arguments),
            },
        )
        raw_content = result.get("content", [])

        if not isinstance(raw_content, list):
            raise McpProtocolError("MCP tools/call content must be a list.")

        content = tuple(dict(item) for item in raw_content if isinstance(item, Mapping))

        return McpToolResult(
            content=content,
            is_error=result.get("isError") is True,
            structured_content=result.get("structuredContent"),
        )

    def close(self) -> None:
        process = self._process
        self._process = None

        if process is None:
            return

        if process.stdin is not None:
            process.stdin.close()

        if process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def _request(
        self,
        method: str,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": dict(params),
            }
        )

        while True:
            try:
                message = self._messages.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise McpTimeoutError(
                    f"MCP request '{method}' timed out after {self.timeout:.1f} seconds."
                ) from exc

            if isinstance(message, Exception):
                raise McpProtocolError(str(message)) from message

            if not isinstance(message, dict) or message.get("id") != request_id:
                continue

            error = message.get("error")

            if isinstance(error, Mapping):
                raise McpProtocolError(
                    f"MCP server error {error.get('code')}: {error.get('message')}"
                )

            result = message.get("result")

            if not isinstance(result, dict):
                raise McpProtocolError("MCP response result must be an object.")

            return result

    def _notify(
        self,
        method: str,
        params: Mapping[str, Any],
    ) -> None:
        self._write(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": dict(params),
            }
        )

    def _write(
        self,
        message: Mapping[str, Any],
    ) -> None:
        process = self._process

        if process is None or process.stdin is None:
            raise McpError("MCP server is not running.")

        try:
            process.stdin.write(
                json.dumps(
                    message,
                    ensure_ascii=False,
                )
                + "\n"
            )
            process.stdin.flush()
        except OSError as exc:
            raise McpError("Could not write to MCP server.") from exc

    def _read_messages(
        self,
        stream: TextIO,
    ) -> None:
        try:
            for line in stream:
                clean = line.strip()

                if not clean:
                    continue

                try:
                    self._messages.put(json.loads(clean))
                except json.JSONDecodeError as exc:
                    self._messages.put(McpProtocolError(f"MCP server emitted invalid JSON: {exc}"))
        except OSError as exc:
            self._messages.put(McpProtocolError(f"MCP output stream failed: {exc}"))
