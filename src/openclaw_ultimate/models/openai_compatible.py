from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from openclaw_ultimate.core.messages import Message, ToolCall
from openclaw_ultimate.core.tools import ToolDefinition
from openclaw_ultimate.models.base import ModelResponse


class OpenAICompatibleError(RuntimeError):
    """OpenAI-Compatible 模型适配器的基础异常。"""


class ModelRequestError(OpenAICompatibleError):
    """模型 HTTP 请求失败。"""


class ModelResponseError(OpenAICompatibleError):
    """模型返回了无法解析的数据。"""


class OpenAICompatibleModel:
    """兼容 OpenAI Chat Completions 格式的模型客户端。

    可用于：
    - LM Studio
    - Ollama OpenAI-compatible endpoint
    - vLLM
    - LocalAI
    - OpenAI Chat Completions endpoint
    - 其他兼容 /v1/chat/completions 的服务
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:1234/v1",
        api_key: str | None = None,
        timeout: float = 60.0,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("model cannot be empty.")

        if not base_url.strip():
            raise ValueError("base_url cannot be empty.")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_headers = dict(extra_headers or {})
        self.extra_body = dict(extra_body or {})
        self._client = client

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
    ) -> ModelResponse:
        payload = self._build_payload(
            messages=messages,
            tools=tools,
        )

        headers = self._build_headers()
        endpoint = f"{self.base_url}/chat/completions"

        try:
            if self._client is not None:
                response = await self._client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout,
                    )

            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:1000]

            raise ModelRequestError(
                f"Model request returned HTTP {exc.response.status_code}: {body}"
            ) from exc

        except httpx.RequestError as exc:
            raise ModelRequestError(f"Could not connect to model endpoint: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ModelResponseError("Model response was not valid JSON.") from exc

        return self._parse_response(data)

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            **self.extra_headers,
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _build_payload(
        self,
        *,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._serialize_message(message) for message in messages],
            **self.extra_body,
        }

        if tools:
            payload["tools"] = [self._serialize_tool(tool) for tool in tools]

        if self.temperature is not None:
            payload["temperature"] = self.temperature

        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens

        return payload

    @staticmethod
    def _serialize_message(
        message: Message,
    ) -> dict[str, Any]:
        serialized: dict[str, Any] = {
            "role": message.role,
            "content": message.content,
        }

        if message.name is not None:
            serialized["name"] = message.name

        if message.tool_call_id is not None:
            serialized["tool_call_id"] = message.tool_call_id

        if message.tool_calls:
            serialized["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(
                            dict(tool_call.arguments),
                            ensure_ascii=False,
                        ),
                    },
                }
                for tool_call in message.tool_calls
            ]

        return serialized

    @staticmethod
    def _serialize_tool(
        tool: ToolDefinition,
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters),
            },
        }

    @classmethod
    def _parse_response(
        cls,
        data: Any,
    ) -> ModelResponse:
        if not isinstance(data, dict):
            raise ModelResponseError("Model response root must be an object.")

        choices = data.get("choices")

        if not isinstance(choices, list) or not choices:
            raise ModelResponseError("Model response does not contain any choices.")

        first_choice = choices[0]

        if not isinstance(first_choice, dict):
            raise ModelResponseError("Model response choice must be an object.")

        message = first_choice.get("message")

        if not isinstance(message, dict):
            raise ModelResponseError("Model response choice has no message.")

        content = message.get("content")

        if content is not None and not isinstance(content, str):
            raise ModelResponseError("Model response content must be a string or null.")

        raw_tool_calls = message.get("tool_calls") or []

        if not isinstance(raw_tool_calls, list):
            raise ModelResponseError("Model tool_calls must be a list.")

        tool_calls = tuple(cls._parse_tool_call(raw_tool_call) for raw_tool_call in raw_tool_calls)

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _parse_tool_call(
        raw_tool_call: Any,
    ) -> ToolCall:
        if not isinstance(raw_tool_call, dict):
            raise ModelResponseError("Tool call must be an object.")

        call_id = raw_tool_call.get("id")
        function = raw_tool_call.get("function")

        if not isinstance(call_id, str) or not call_id:
            raise ModelResponseError("Tool call does not contain a valid id.")

        if not isinstance(function, dict):
            raise ModelResponseError("Tool call does not contain a function object.")

        name = function.get("name")
        raw_arguments = function.get("arguments", "{}")

        if not isinstance(name, str) or not name:
            raise ModelResponseError("Tool call does not contain a valid function name.")

        if isinstance(raw_arguments, dict):
            arguments = raw_arguments

        elif isinstance(raw_arguments, str):
            try:
                parsed_arguments = json.loads(raw_arguments or "{}")
            except json.JSONDecodeError as exc:
                raise ModelResponseError(f"Tool '{name}' returned invalid JSON arguments.") from exc

            if not isinstance(parsed_arguments, dict):
                raise ModelResponseError(f"Tool '{name}' arguments must decode to an object.")

            arguments = parsed_arguments

        else:
            raise ModelResponseError(f"Tool '{name}' arguments must be JSON text or an object.")

        return ToolCall(
            id=call_id,
            name=name,
            arguments=arguments,
        )
