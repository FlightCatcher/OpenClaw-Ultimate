from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from openclaw_ultimate.core.runtime import Agent
from openclaw_ultimate.models.base import ModelResponse
from openclaw_ultimate.planner import (
    ErrorContext,
    FailureType,
    PlanExecutor,
    PlanStatus,
    PlanStep,
    ReflectionEngine,
    ReplanningEngine,
    RetryPolicy,
    RevisionStatus,
    SQLitePlanStore,
    StepStatus,
    SuggestedAction,
    TaskPlan,
)


def failed_plan() -> TaskPlan:
    return TaskPlan.create(
        goal="读取配置",
        steps=(
            PlanStep(
                id="read",
                title="读取不存在的文件",
                description="读取 missing.txt",
                tool_hint="read_text_file",
                status=StepStatus.FAILED,
                error="FileNotFoundError: File does not exist: missing.txt",
            ),
        ),
    ).with_status(PlanStatus.FAILED)


def test_rule_reflection_classifies_missing_file() -> None:
    plan = failed_plan()
    reflection = ReflectionEngine().reflect(
        plan=plan,
        failed_step=plan.steps[0],
        error_context=ErrorContext(
            error_type="FileNotFoundError",
            error_message=plan.steps[0].error or "",
            tool_name="read_text_file",
        ),
    )

    assert reflection.failure_type == FailureType.TOOL_ERROR
    assert reflection.retryable is True
    assert reflection.suggested_action == SuggestedAction.RETRY_WITH_MODIFIED_INPUT
    assert "missing.txt" in reflection.original_error_message


@pytest.mark.parametrize(
    ("error_type", "failure_type", "retryable", "action"),
    [
        ("TimeoutError", FailureType.TIMEOUT, True, SuggestedAction.RETRY_SAME_STEP),
        (
            "PermissionError",
            FailureType.PERMISSION_ERROR,
            False,
            SuggestedAction.REQUEST_USER_INPUT,
        ),
        ("RuntimeError", FailureType.MODEL_ERROR, True, SuggestedAction.CHOOSE_DIFFERENT_MODEL),
        (
            "ValueError",
            FailureType.VALIDATION_ERROR,
            True,
            SuggestedAction.RETRY_WITH_MODIFIED_INPUT,
        ),
        ("RuntimeError", FailureType.UNKNOWN, False, SuggestedAction.REQUEST_USER_INPUT),
    ],
)
def test_rule_reflection_classifies_common_failures(
    error_type: str,
    failure_type: FailureType,
    retryable: bool,
    action: SuggestedAction,
) -> None:
    plan = failed_plan()
    message = {
        "RuntimeError": "model connection failed"
        if action == SuggestedAction.CHOOSE_DIFFERENT_MODEL
        else "unexpected",
        "ValueError": "invalid input",
    }.get(error_type, error_type)
    reflection = ReflectionEngine().reflect(
        plan=plan,
        failed_step=plan.steps[0],
        error_context=ErrorContext(error_type=error_type, error_message=message),
    )

    assert reflection.failure_type == failure_type
    assert reflection.retryable is retryable
    assert reflection.suggested_action == action


def test_reflection_requires_failed_step() -> None:
    plan = failed_plan().with_steps(
        (plan_step := PlanStep(id="read", title="读取", description="读取"),)
    )
    with pytest.raises(ValueError, match="failed"):
        ReflectionEngine().reflect(
            plan=plan,
            failed_step=plan_step,
            error_context=ErrorContext(error_type="RuntimeError", error_message="boom"),
        )


def test_reflections_are_persisted_without_overwriting_history(tmp_path: Path) -> None:
    plan = failed_plan()
    store = SQLitePlanStore(tmp_path / "plans.db")
    store.save(plan)
    engine = ReflectionEngine()

    for message in ("first", "second"):
        reflection = engine.reflect(
            plan=plan,
            failed_step=plan.steps[0],
            error_context=ErrorContext("FileNotFoundError", message),
        )
        store.save_reflection(reflection)

    saved = store.list_reflections(plan_id=plan.id, step_id="read")
    assert len(saved) == 2
    assert store.get(plan.id).status == PlanStatus.FAILED


def test_executor_persists_reflection_after_agent_failure(tmp_path: Path) -> None:
    class MissingFileAgentModel:
        async def complete(self, messages, tools) -> ModelResponse:
            raise FileNotFoundError("missing/README.md")

    store = SQLitePlanStore(tmp_path / "plans.db")
    plan = TaskPlan.create(
        goal="执行失败后反思",
        steps=(
            PlanStep(
                id="read",
                title="读取文件",
                description="读取不存在的 README",
                tool_hint="read_text_file",
            ),
        ),
    )
    store.save(plan)

    result = asyncio.run(
        PlanExecutor().execute(
            plan=plan,
            agent=Agent(name="failure-test", model=MissingFileAgentModel()),
            store=store,
        )
    )

    assert result.plan.status == PlanStatus.FAILED
    reflections = store.list_reflections(plan_id=plan.id, step_id="read")
    assert len(reflections) == 1
    assert reflections[0].failure_type == FailureType.TOOL_ERROR


def test_retry_policy_allows_one_timeout_retry_only() -> None:
    plan = failed_plan()
    reflection = ReflectionEngine().reflect(
        plan=plan,
        failed_step=plan.steps[0],
        error_context=ErrorContext("TimeoutError", "model timed out"),
    )
    policy = RetryPolicy()

    first = policy.decide(reflection=reflection)
    attempt = policy.create_attempt(reflection=reflection, decision=first)
    second = policy.decide(reflection=reflection, previous_attempts=(attempt,))

    assert first.allowed is True
    assert first.attempt_number == 1
    assert second.allowed is False
    assert "最大" in second.reason or "重复" in second.reason


def test_executor_retries_timeout_once_and_persists_attempt(tmp_path: Path) -> None:
    class TimeoutThenSuccessModel:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, messages, tools) -> ModelResponse:
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("model timed out")
            return ModelResponse(content="重试成功")

    store = SQLitePlanStore(tmp_path / "plans.db")
    plan = TaskPlan.create(
        goal="超时后重试",
        steps=(PlanStep(id="step", title="调用模型", description="调用模型"),),
    )
    store.save(plan)
    model = TimeoutThenSuccessModel()

    result = asyncio.run(
        PlanExecutor().execute(
            plan=plan,
            agent=Agent(name="retry-test", model=model),
            store=store,
        )
    )

    assert result.plan.status == PlanStatus.COMPLETED
    assert result.plan.steps[0].result == "重试成功"
    assert model.calls == 2
    attempts = store.list_retry_attempts(plan_id=plan.id, step_id="step")
    assert len(attempts) == 1
    assert attempts[0].scheduled is True


def test_replanning_creates_candidate_without_changing_plan(tmp_path: Path) -> None:
    plan = failed_plan()
    store = SQLitePlanStore(tmp_path / "plans.db")
    store.save(plan)
    reflection = ReflectionEngine().reflect(
        plan=plan,
        failed_step=plan.steps[0],
        error_context=ErrorContext(
            "FileNotFoundError",
            "File does not exist: missing.txt",
        ),
    )
    store.save_reflection(reflection)

    revision = ReplanningEngine().propose(
        plan=plan,
        reflection=reflection,
        revision_number=1,
    )
    store.save_revision(revision)

    saved = store.list_revisions(plan_id=plan.id)
    assert len(saved) == 1
    assert saved[0].parent_plan_id == plan.id
    assert saved[0].status.value == "candidate"
    assert store.get(plan.id) == plan


def test_approved_revision_creates_child_plan_and_preserves_parent(tmp_path: Path) -> None:
    plan = failed_plan()
    store = SQLitePlanStore(tmp_path / "plans.db")
    store.save(plan)
    reflection = ReflectionEngine().reflect(
        plan=plan,
        failed_step=plan.steps[0],
        error_context=ErrorContext("FileNotFoundError", "missing.txt"),
    )
    proposed_step = PlanStep(
        id="read",
        title="读取备用文件",
        description="读取 docs/README.md",
        tool_hint="read_text_file",
    )
    revision = ReplanningEngine().propose(
        plan=plan,
        reflection=reflection,
        revision_number=1,
        proposed_step=proposed_step,
    )
    store.save_revision(revision)

    child = ReplanningEngine().apply(plan=plan, revision=revision)
    store.save(child)
    applied = store.update_revision_applied(
        revision_id=revision.revision_id,
        child_plan_id=child.id,
    )

    assert child.id != plan.id
    assert child.status == PlanStatus.READY
    assert child.steps[0].description == "读取 docs/README.md"
    assert store.get(plan.id) == plan
    assert applied.status == RevisionStatus.APPLIED
    assert applied.child_plan_id == child.id
