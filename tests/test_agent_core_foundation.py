from __future__ import annotations

import asyncio

import pytest

from openclaw_ultimate.core import Agent, AgentRuntime, ModuleRegistry, RuntimeState
from openclaw_ultimate.models.base import ModelResponse
from openclaw_ultimate.observability import configure_logging


class Module:
    name = "test-module"


class Model:
    async def complete(self, messages, tools) -> ModelResponse:
        return ModelResponse(content="完成")


def test_module_registry_lifecycle_and_duplicate_protection() -> None:
    events: list[str] = []
    registry = ModuleRegistry()
    registry.register(
        Module(),
        on_start=lambda: events.append("start"),
        on_stop=lambda: events.append("stop"),
    )

    asyncio.run(registry.start_all())
    asyncio.run(registry.stop_all())

    assert registry.names() == ("test-module",)
    assert events == ["start", "stop"]
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Module())


def test_runtime_exposes_lifecycle_state() -> None:
    runtime = AgentRuntime()
    assert runtime.state == RuntimeState.IDLE

    result = asyncio.run(runtime.run(Agent(name="test", model=Model()), "你好"))

    assert result.output == "完成"
    assert runtime.state == RuntimeState.COMPLETED
    assert runtime.last_error is None


def test_runtime_records_failed_state() -> None:
    runtime = AgentRuntime()

    with pytest.raises(ValueError):
        asyncio.run(runtime.run(Agent(name="test", model=Model()), "   "))

    assert runtime.state == RuntimeState.FAILED
    assert runtime.last_error is not None


def test_logging_rejects_unknown_level() -> None:
    configure_logging("WARNING")
    with pytest.raises(TypeError, match="Unknown log level"):
        configure_logging("not-a-level")
