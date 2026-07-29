from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from openclaw_ultimate.core.messages import Message, ToolCall
from openclaw_ultimate.core.tools import ToolDefinition


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """语言模型返回给 Runtime 的标准化响应。"""

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


class ModelClient(Protocol):
    """所有模型适配器都必须实现的接口。"""

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
    ) -> ModelResponse: ...


# 兼容早期版本的名称。
ModelProvider = ModelClient


__all__ = [
    "ModelClient",
    "ModelProvider",
    "ModelResponse",
]
