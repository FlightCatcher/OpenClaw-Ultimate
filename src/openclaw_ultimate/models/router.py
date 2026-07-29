from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from openclaw_ultimate.models.catalog import (
    ModelCapability,
    ModelDescriptor,
)


class TaskKind(StrEnum):
    CHAT = "chat"
    CODING = "coding"
    PLANNING = "planning"
    TOOL_CALLING = "tool_calling"
    VISION = "vision"
    EMBEDDING = "embedding"


TASK_CAPABILITIES: Mapping[
    TaskKind,
    frozenset[ModelCapability],
] = {
    TaskKind.CHAT: frozenset({ModelCapability.CHAT}),
    TaskKind.CODING: frozenset(
        {
            ModelCapability.CHAT,
            ModelCapability.CODING,
        }
    ),
    TaskKind.PLANNING: frozenset(
        {
            ModelCapability.CHAT,
            ModelCapability.PLANNING,
        }
    ),
    TaskKind.TOOL_CALLING: frozenset(
        {
            ModelCapability.CHAT,
            ModelCapability.TOOL_CALLING,
        }
    ),
    TaskKind.VISION: frozenset(
        {
            ModelCapability.CHAT,
            ModelCapability.VISION,
        }
    ),
    TaskKind.EMBEDDING: frozenset(
        {
            ModelCapability.EMBEDDING,
        }
    ),
}


class NoModelRouteError(RuntimeError):
    """当前模型库存无法满足任务能力和硬件预算。"""


@dataclass(frozen=True, slots=True)
class ModelRoute:
    task: TaskKind
    model: ModelDescriptor
    reason: str


class ModelRouter:
    """使用能力、显存预算和显式偏好进行确定性模型路由。"""

    def __init__(
        self,
        models: Sequence[ModelDescriptor],
        *,
        max_resident_bytes: int,
        preferences: Mapping[TaskKind, Sequence[str]] | None = None,
    ) -> None:
        if max_resident_bytes < 1:
            raise ValueError("max_resident_bytes must be positive.")

        self.models = tuple(models)
        self.max_resident_bytes = max_resident_bytes
        self.preferences = {key: tuple(value) for key, value in (preferences or {}).items()}

    def select(
        self,
        task: TaskKind,
    ) -> ModelRoute:
        required = TASK_CAPABILITIES[task]
        candidates = [
            model
            for model in self.models
            if model.supports(required) and model.size_bytes <= self.max_resident_bytes
        ]

        if not candidates:
            raise NoModelRouteError(
                f"No installed model supports '{task.value}' within the resident-memory budget."
            )

        preference = self.preferences.get(task, ())
        preference_index = {name.casefold(): index for index, name in enumerate(preference)}

        def score(
            model: ModelDescriptor,
        ) -> tuple[int, int, str]:
            preferred = preference_index.get(
                model.name.casefold(),
                len(preference) + 100,
            )
            return (
                preferred,
                model.size_bytes,
                model.name.casefold(),
            )

        selected = min(candidates, key=score)
        preferred_match = selected.name.casefold() in preference_index
        reason = (
            "matched configured task preference"
            if preferred_match
            else "best capability match within the resident-memory budget"
        )

        return ModelRoute(
            task=task,
            model=selected,
            reason=reason,
        )

    def select_all(
        self,
    ) -> tuple[ModelRoute, ...]:
        routes = []

        for task in TaskKind:
            try:
                routes.append(self.select(task))
            except NoModelRouteError:
                continue

        return tuple(routes)
