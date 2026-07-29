from __future__ import annotations

import asyncio
import json

import pytest

from openclaw_ultimate.core.messages import ToolCall
from openclaw_ultimate.core.runtime import (
    Agent,
    AgentRuntime,
    RuntimeLimitError,
)
from openclaw_ultimate.models.base import ModelResponse
from tests.fakes import FakeModel


def test_runtime_returns_direct_model_response() -> None:
    model = FakeModel(
        [
            ModelResponse(
                content="你好，我是 OpenClaw-Ultimate。",
            )
        ]
    )

    agent = Agent(
        name="main",
        model=model,
        system_prompt="你是一个测试助手。",
    )

    result = asyncio.run(
        AgentRuntime().run(
            agent,
            "你好",
        )
    )

    assert result.output == "你好，我是 OpenClaw-Ultimate。"
    assert result.steps == 1
    assert result.messages[0].role == "system"
    assert result.messages[1].role == "user"
    assert result.messages[2].role == "assistant"


def test_runtime_executes_tool_and_continues_model_loop() -> None:
    model = FakeModel(
        [
            ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="call-1",
                        name="add",
                        arguments={
                            "a": 2,
                            "b": 3,
                        },
                    ),
                )
            ),
            ModelResponse(
                content="计算结果是 5。",
            ),
        ]
    )

    agent = Agent(
        name="calculator-agent",
        model=model,
    )

    agent.tools.add(
        name="add",
        description="计算两个数字的和。",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        handler=lambda a, b: a + b,
    )

    result = asyncio.run(
        AgentRuntime().run(
            agent,
            "2 加 3 等于多少？",
        )
    )

    assert result.output == "计算结果是 5。"
    assert result.steps == 2
    assert len(model.calls) == 2

    tool_messages = [message for message in result.messages if message.role == "tool"]

    assert len(tool_messages) == 1

    tool_payload = json.loads(tool_messages[0].content or "{}")

    assert tool_payload == {
        "ok": True,
        "result": 5,
    }


def test_runtime_returns_tool_error_to_model() -> None:
    model = FakeModel(
        [
            ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="call-missing",
                        name="missing_tool",
                        arguments={},
                    ),
                )
            ),
            ModelResponse(
                content="工具不存在，无法完成操作。",
            ),
        ]
    )

    agent = Agent(
        name="error-agent",
        model=model,
    )

    result = asyncio.run(
        AgentRuntime().run(
            agent,
            "调用不存在的工具",
        )
    )

    tool_message = next(message for message in result.messages if message.role == "tool")

    payload = json.loads(tool_message.content or "{}")

    assert payload["ok"] is False
    assert "Unknown tool" in payload["error"]
    assert result.output == "工具不存在，无法完成操作。"


def test_runtime_stops_after_maximum_steps() -> None:
    repeated_call = ModelResponse(
        tool_calls=(
            ToolCall(
                id="loop-call",
                name="echo",
                arguments={"text": "hello"},
            ),
        )
    )

    model = FakeModel(
        [
            repeated_call,
            repeated_call,
        ]
    )

    agent = Agent(
        name="loop-agent",
        model=model,
        max_steps=2,
    )

    agent.tools.add(
        name="echo",
        description="原样返回文本。",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
        handler=lambda text: text,
    )

    with pytest.raises(RuntimeLimitError):
        asyncio.run(
            AgentRuntime().run(
                agent,
                "不断调用 echo",
            )
        )
