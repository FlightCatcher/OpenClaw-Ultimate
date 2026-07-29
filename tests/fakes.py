from __future__ import annotations

from collections import deque
from typing import Iterable, Sequence

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.tools import ToolDefinition
from openclaw_ultimate.models.base import ModelResponse


class FakeModel:
    """测试 Agent Runtime 时使用的假模型。"""

    def __init__(
        self,
        responses: Iterable[ModelResponse],
    ) -> None:
        self._responses = deque(responses)
        self.calls: list[
            tuple[
                tuple[Message, ...],
                tuple[ToolDefinition, ...],
            ]
        ] = []

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
    ) -> ModelResponse:
        self.calls.append(
            (
                tuple(messages),
                tuple(tools),
            )
        )

        if not self._responses:
            raise RuntimeError("FakeModel has no responses left.")

        return self._responses.popleft()
