"""Agent Runtime 的公共兼容入口。

新版接口：
    runtime = AgentRuntime()
    result = await runtime.run(agent, "hello")

旧版兼容接口：
    runtime = AgentRuntime(model)
    result = runtime.respond("hello")
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.runtime import (
    Agent,
    AgentRuntime as CoreAgentRuntime,
    RuntimeLimitError,
    RuntimeResult,
)
from openclaw_ultimate.models.base import ModelResponse


class AgentRuntime(CoreAgentRuntime):
    """兼容新旧两套调用方式的 Agent Runtime。"""

    def __init__(self, model: Any | None = None) -> None:
        self._legacy_model = model

    def respond(self, user_input: str) -> str:
        """兼容早期版本的同步文本接口。"""

        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input cannot be empty.")

        if self._legacy_model is None:
            raise RuntimeError(
                "Legacy respond() requires a model: "
                "AgentRuntime(model).respond(text)"
            )

        result = self._invoke_legacy_model(user_input)

        if inspect.isawaitable(result):
            result = self._run_awaitable(result)

        return self._normalize_legacy_result(result)

    def _invoke_legacy_model(self, user_input: str) -> Any:
        model = self._legacy_model

        # 常见的新旧模型方法名称。
        method_names = (
            "respond",
            "reply",
            "generate",
            "generate_response",
            "chat",
            "ask",
            "invoke",
            "run",
            "predict",
        )

        for method_name in method_names:
            method = getattr(model, method_name, None)

            if callable(method):
                return self._call_legacy_method(
                    method,
                    user_input,
                )

        complete = getattr(model, "complete", None)

        if callable(complete):
            try:
                return complete(user_input)
            except TypeError:
                return complete(
                    messages=(Message.user(user_input),),
                    tools=(),
                )

        if callable(model):
            return model(user_input)

        # 最后兼容简单测试类：
        # 自动寻找类中唯一的公开方法。
        public_methods: list[Any] = []

        for name in type(model).__dict__:
            if name.startswith("_"):
                continue

            method = getattr(model, name, None)

            if callable(method):
                public_methods.append(method)

        if len(public_methods) == 1:
            return self._call_legacy_method(
                public_methods[0],
                user_input,
            )

        available = [
            name
            for name in type(model).__dict__
            if not name.startswith("_")
        ]

        raise TypeError(
            "Could not determine how to call the legacy model. "
            f"Available public attributes: {available}"
        )

    @staticmethod
    def _call_legacy_method(
        method: Any,
        user_input: str,
    ) -> Any:
        """兼容位置参数和关键字参数两种调用方式。"""

        try:
            return method(user_input)
        except TypeError as positional_error:
            for keyword in (
                "prompt",
                "text",
                "message",
                "user_input",
                "input",
            ):
                try:
                    return method(**{keyword: user_input})
                except TypeError:
                    continue

            raise positional_error

    @staticmethod
    def _run_awaitable(awaitable: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(awaitable)

        raise RuntimeError(
            "respond() cannot execute an async model while an event loop "
            "is already running. Use await AgentRuntime.run(...) instead."
        )

    @staticmethod
    def _normalize_legacy_result(result: Any) -> str:
        if isinstance(result, str):
            return result

        if isinstance(result, ModelResponse):
            return result.content or ""

        content = getattr(result, "content", None)

        if isinstance(content, str):
            return content

        if result is None:
            return ""

        return str(result)


__all__ = [
    "Agent",
    "AgentRuntime",
    "RuntimeLimitError",
    "RuntimeResult",
]
