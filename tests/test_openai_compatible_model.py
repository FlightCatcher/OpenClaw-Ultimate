from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.tools import ToolDefinition
from openclaw_ultimate.models.openai_compatible import (
    ModelRequestError,
    ModelResponseError,
    OpenAICompatibleModel,
)


def test_complete_parses_text_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "你好，我是本地模型。",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)

    async def run_test():
        async with httpx.AsyncClient(transport=transport) as client:
            model = OpenAICompatibleModel(
                model="local-model",
                base_url="http://testserver/v1",
                api_key="test-key",
                temperature=0.2,
                client=client,
            )

            return await model.complete(
                messages=[
                    Message.system("你是一个助手。"),
                    Message.user("你好"),
                ],
                tools=[],
            )

    result = asyncio.run(run_test())

    assert result.content == "你好，我是本地模型。"
    assert result.tool_calls == ()

    assert captured["url"] == ("http://testserver/v1/chat/completions")
    assert captured["authorization"] == "Bearer test-key"

    payload = captured["payload"]

    assert isinstance(payload, dict)
    assert payload["model"] == "local-model"
    assert payload["temperature"] == 0.2
    assert payload["messages"][1] == {
        "role": "user",
        "content": "你好",
    }


def test_complete_serializes_tools_and_parses_tool_call() -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-add-1",
                                    "type": "function",
                                    "function": {
                                        "name": "add",
                                        "arguments": ('{"a": 10, "b": 20}'),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    async def run_test():
        async with httpx.AsyncClient(transport=transport) as client:
            model = OpenAICompatibleModel(
                model="tool-model",
                base_url="http://testserver/v1",
                client=client,
            )

            return await model.complete(
                messages=[Message.user("10 加 20")],
                tools=[
                    ToolDefinition(
                        name="add",
                        description="计算两个数字之和。",
                        parameters={
                            "type": "object",
                            "properties": {
                                "a": {"type": "number"},
                                "b": {"type": "number"},
                            },
                            "required": ["a", "b"],
                        },
                    )
                ],
            )

    result = asyncio.run(run_test())

    assert result.content is None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call-add-1"
    assert result.tool_calls[0].name == "add"
    assert result.tool_calls[0].arguments == {
        "a": 10,
        "b": 20,
    }

    tools = captured_payload["tools"]

    assert isinstance(tools, list)
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "add"


def test_complete_raises_for_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            text="model server failed",
        )

    transport = httpx.MockTransport(handler)

    async def run_test():
        async with httpx.AsyncClient(transport=transport) as client:
            model = OpenAICompatibleModel(
                model="broken-model",
                base_url="http://testserver/v1",
                client=client,
            )

            await model.complete(
                messages=[Message.user("hello")],
                tools=[],
            )

    with pytest.raises(
        ModelRequestError,
        match="HTTP 500",
    ):
        asyncio.run(run_test())


def test_complete_rejects_invalid_tool_arguments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "bad-call",
                                    "type": "function",
                                    "function": {
                                        "name": "add",
                                        "arguments": "{invalid-json",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    async def run_test():
        async with httpx.AsyncClient(transport=transport) as client:
            model = OpenAICompatibleModel(
                model="bad-tool-model",
                base_url="http://testserver/v1",
                client=client,
            )

            await model.complete(
                messages=[Message.user("hello")],
                tools=[],
            )

    with pytest.raises(
        ModelResponseError,
        match="invalid JSON arguments",
    ):
        asyncio.run(run_test())
