from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


class AgentModule(Protocol):
    name: str


ModuleHook = Callable[[], Any]


@dataclass(slots=True)
class RegisteredModule:
    name: str
    module: AgentModule
    on_start: ModuleHook | None = None
    on_stop: ModuleHook | None = None


class ModuleRegistry:
    """管理 Agent 可插拔模块，禁止同名覆盖。"""

    def __init__(self) -> None:
        self._modules: dict[str, RegisteredModule] = {}

    def register(
        self,
        module: AgentModule,
        *,
        on_start: ModuleHook | None = None,
        on_stop: ModuleHook | None = None,
    ) -> RegisteredModule:
        name = module.name.strip()
        if not name:
            raise ValueError("Module name cannot be empty.")
        if name in self._modules:
            raise ValueError(f"Module already registered: {name}")

        registered = RegisteredModule(
            name=name,
            module=module,
            on_start=on_start,
            on_stop=on_stop,
        )
        self._modules[name] = registered
        return registered

    def get(self, name: str) -> RegisteredModule:
        try:
            return self._modules[name]
        except KeyError as exc:
            raise KeyError(f"Module not registered: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self._modules)

    async def start_all(self) -> None:
        for registered in self._modules.values():
            await self._invoke(registered.on_start)

    async def stop_all(self) -> None:
        for registered in reversed(tuple(self._modules.values())):
            await self._invoke(registered.on_stop)

    @staticmethod
    async def _invoke(hook: ModuleHook | None) -> None:
        if hook is None:
            return
        result = hook()
        if inspect.isawaitable(result):
            await result

    def __contains__(self, name: str) -> bool:
        return name in self._modules

    def __len__(self) -> int:
        return len(self._modules)


__all__ = ["AgentModule", "ModuleRegistry", "RegisteredModule"]
