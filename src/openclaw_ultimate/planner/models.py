from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PlanStep:
    id: str
    title: str
    description: str
    dependencies: tuple[str, ...] = ()
    tool_hint: str | None = None
    status: StepStatus = StepStatus.PENDING
    result: str | None = None
    error: str | None = None

    def with_status(
        self,
        status: StepStatus,
        *,
        result: str | None = None,
        error: str | None = None,
    ) -> PlanStep:
        return replace(
            self,
            status=status,
            result=result,
            error=error,
        )


@dataclass(frozen=True, slots=True)
class TaskPlan:
    id: str
    goal: str
    steps: tuple[PlanStep, ...]
    status: PlanStatus
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        goal: str,
        steps: tuple[PlanStep, ...],
    ) -> TaskPlan:
        clean_goal = goal.strip()

        if not clean_goal:
            raise ValueError("Plan goal cannot be empty.")

        now = datetime.now(UTC).isoformat(timespec="milliseconds")

        return cls(
            id=uuid4().hex,
            goal=clean_goal,
            steps=steps,
            status=PlanStatus.READY,
            created_at=now,
            updated_at=now,
        )

    def with_steps(
        self,
        steps: tuple[PlanStep, ...],
        *,
        status: PlanStatus | None = None,
    ) -> TaskPlan:
        return replace(
            self,
            steps=steps,
            status=status or self.status,
            updated_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
        )

    def with_status(
        self,
        status: PlanStatus,
    ) -> TaskPlan:
        return replace(
            self,
            status=status,
            updated_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
        )
