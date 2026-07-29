from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from openclaw_ultimate.planner.models import PlanStatus, PlanStep, TaskPlan
from openclaw_ultimate.planner.reflection import ReflectionResult, SuggestedAction


class RevisionStatus(StrEnum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class PlanRevision:
    revision_id: str
    plan_id: str
    parent_plan_id: str
    revision_number: int
    step_id: str
    status: RevisionStatus
    rationale: str
    suggested_changes: tuple[str, ...]
    created_at: str
    proposed_step: PlanStep | None = None
    child_plan_id: str | None = None


class ReplanningEngine:
    """生成候选修订，不修改或执行原计划。"""

    _REVISION_ACTIONS = frozenset(
        {
            SuggestedAction.REVISE_PLAN,
            SuggestedAction.RETRY_WITH_MODIFIED_INPUT,
            SuggestedAction.CHOOSE_DIFFERENT_TOOL,
            SuggestedAction.CHOOSE_DIFFERENT_MODEL,
            SuggestedAction.REQUEST_USER_INPUT,
        }
    )

    def propose(
        self,
        *,
        plan: TaskPlan,
        reflection: ReflectionResult,
        revision_number: int,
        proposed_step: PlanStep | None = None,
    ) -> PlanRevision:
        if reflection.plan_id != plan.id:
            raise ValueError("Reflection does not belong to the supplied plan.")
        if reflection.suggested_action not in self._REVISION_ACTIONS:
            raise ValueError("Reflection does not require plan revision.")
        if revision_number < 1:
            raise ValueError("revision_number must be at least 1.")

        return PlanRevision(
            revision_id=uuid4().hex,
            plan_id=plan.id,
            parent_plan_id=plan.id,
            revision_number=revision_number,
            step_id=reflection.step_id,
            status=RevisionStatus.CANDIDATE,
            rationale=reflection.root_cause,
            suggested_changes=reflection.suggested_changes,
            created_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
            proposed_step=proposed_step,
        )

    def apply(
        self,
        *,
        plan: TaskPlan,
        revision: PlanRevision,
    ) -> TaskPlan:
        if revision.status != RevisionStatus.CANDIDATE:
            raise ValueError("Only candidate revisions can be applied.")
        if revision.parent_plan_id != plan.id:
            raise ValueError("Revision does not belong to the supplied plan.")
        if revision.proposed_step is None:
            raise ValueError("Revision has no explicit proposed step.")

        if not any(step.id == revision.step_id for step in plan.steps):
            raise ValueError(f"Revision step does not exist: {revision.step_id}")

        steps = tuple(
            revision.proposed_step if step.id == revision.step_id else step for step in plan.steps
        )
        return TaskPlan.create(
            goal=plan.goal,
            steps=steps,
        ).with_status(PlanStatus.READY)
