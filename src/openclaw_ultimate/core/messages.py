from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """模型请求执行的一次工具调用。"""

    id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Message:
    """Agent Runtime 内部统一使用的消息格式。"""

    role: Role
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls,
        content: str | None = None,
        tool_calls: Iterable[ToolCall] = (),
    ) -> Message:
        return cls(
            role="assistant",
            content=content,
            tool_calls=tuple(tool_calls),
        )

    @classmethod
    def tool(
        cls,
        *,
        name: str,
        tool_call_id: str,
        content: str,
    ) -> Message:
        return cls(
            role="tool",
            name=name,
            tool_call_id=tool_call_id,
            content=content,
        )
