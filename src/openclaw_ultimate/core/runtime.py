from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.tools import ToolRegistry
from openclaw_ultimate.models.base import ModelClient


class RuntimeLimitError(RuntimeError):
    """Agent 在规定步骤内没有完成任务。"""


@dataclass(slots=True)
class Agent:
    """一个可以被 Runtime 执行的 Agent。"""

    name: str
    model: ModelClient
    system_prompt: str = "You are a helpful AI assistant."
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    max_steps: int = 8

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Agent name cannot be empty.")

        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1.")


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    """一次 Agent 运行的最终结果。"""

    output: str
    messages: tuple[Message, ...]
    steps: int


class AgentRuntime:
    """负责执行模型响应、工具调用和消息循环。"""

    async def run(
        self,
        agent: Agent,
        user_input: str,
        *,
        history: Iterable[Message] = (),
    ) -> RuntimeResult:
        if not user_input.strip():
            raise ValueError("user_input cannot be empty.")

        messages = list(history)

        if not any(message.role == "system" for message in messages):
            messages.insert(0, Message.system(agent.system_prompt))

        messages.append(Message.user(user_input))

        for step in range(1, agent.max_steps + 1):
            response = await agent.model.complete(
                messages=tuple(messages),
                tools=agent.tools.definitions(),
            )

            assistant_message = Message.assistant(
                content=response.content,
                tool_calls=response.tool_calls,
            )
            messages.append(assistant_message)

            if not response.tool_calls:
                return RuntimeResult(
                    output=response.content or "",
                    messages=tuple(messages),
                    steps=step,
                )

            for tool_call in response.tool_calls:
                tool_result = await self._execute_tool_call(
                    agent=agent,
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                )

                messages.append(
                    Message.tool(
                        name=tool_call.name,
                        tool_call_id=tool_call.id,
                        content=tool_result,
                    )
                )

        raise RuntimeLimitError(
            f"Agent '{agent.name}' exceeded "
            f"the maximum of {agent.max_steps} steps."
        )

    async def _execute_tool_call(
        self,
        *,
        agent: Agent,
        tool_name: str,
        arguments: Any,
    ) -> str:
        if not isinstance(arguments, dict):
            return self._json_dump(
                {
                    "ok": False,
                    "error": "Tool arguments must be an object.",
                }
            )

        try:
            tool = agent.tools.get(tool_name)
            result = await tool.invoke(arguments)

            return self._json_dump(
                {
                    "ok": True,
                    "result": result,
                }
            )

        except Exception as exc:
            return self._json_dump(
                {
                    "ok": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )

    @staticmethod
    def _json_dump(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
