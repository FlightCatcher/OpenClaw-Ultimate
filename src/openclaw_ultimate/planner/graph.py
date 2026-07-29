from __future__ import annotations

from collections.abc import Iterable

from openclaw_ultimate.planner.models import (
    PlanStep,
    StepStatus,
)


class PlanValidationError(ValueError):
    """任务计划不是有效的有向无环图。"""


class TaskGraph:
    """验证和查询任务步骤依赖图。"""

    def __init__(
        self,
        steps: Iterable[PlanStep],
    ) -> None:
        self.steps = tuple(steps)
        self._by_id = {step.id: step for step in self.steps}
        self._validate()

    def topological_order(
        self,
    ) -> tuple[PlanStep, ...]:
        remaining = {step.id: set(step.dependencies) for step in self.steps}
        ordered: list[PlanStep] = []

        while remaining:
            ready_ids = sorted(
                step_id for step_id, dependencies in remaining.items() if not dependencies
            )

            if not ready_ids:
                raise PlanValidationError("Plan contains a dependency cycle.")

            for step_id in ready_ids:
                ordered.append(self._by_id[step_id])
                del remaining[step_id]

            for dependencies in remaining.values():
                dependencies.difference_update(ready_ids)

        return tuple(ordered)

    def ready_steps(
        self,
    ) -> tuple[PlanStep, ...]:
        completed = {step.id for step in self.steps if step.status == StepStatus.COMPLETED}

        return tuple(
            step
            for step in self.topological_order()
            if (step.status == StepStatus.PENDING and set(step.dependencies) <= completed)
        )

    def _validate(self) -> None:
        if not self.steps:
            raise PlanValidationError("Plan must contain at least one step.")

        if len(self._by_id) != len(self.steps):
            raise PlanValidationError("Plan step ids must be unique.")

        known_ids = set(self._by_id)

        for step in self.steps:
            if not step.id.strip():
                raise PlanValidationError("Plan step id cannot be empty.")

            if not step.title.strip():
                raise PlanValidationError(f"Plan step title cannot be empty: {step.id}")

            if step.id in step.dependencies:
                raise PlanValidationError(f"Step cannot depend on itself: {step.id}")

            unknown = set(step.dependencies) - known_ids

            if unknown:
                raise PlanValidationError(
                    f"Step {step.id} has unknown dependencies: " + ", ".join(sorted(unknown))
                )

        self.topological_order()
