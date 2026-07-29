from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

ToolHandler = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """提供给模型的工具描述。"""

    name: str
    description: str
    parameters: Mapping[str, Any]


@dataclass(slots=True)
class Tool:
    """一个可以被 Agent 调用的工具。"""

    definition: ToolDefinition
    handler: ToolHandler

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        result = self.handler(**dict(arguments))

        if inspect.isawaitable(result):
            return await result

        return result


class ToolRegistry:
    """保存和管理 Agent 可使用的工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def add(
        self,
        *,
        name: str,
        description: str,
        parameters: Mapping[str, Any],
        handler: ToolHandler,
    ) -> Tool:
        if not name.strip():
            raise ValueError("Tool name cannot be empty.")

        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")

        tool = Tool(
            definition=ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
            ),
            handler=handler,
        )

        self._tools[name] = tool
        return tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(tool.definition for tool in self._tools.values())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
