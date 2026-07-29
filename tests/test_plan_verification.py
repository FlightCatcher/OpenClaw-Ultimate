from __future__ import annotations

import json
from pathlib import Path

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.runtime import RuntimeResult
from openclaw_ultimate.planner import (
    ErrorContext,
    FailureType,
    PlanStep,
    ReflectionEngine,
    RuleBasedVerifier,
    SQLitePlanStore,
    StepStatus,
    StepVerificationError,
    SuggestedAction,
    TaskPlan,
    VerificationStatus,
)


def _plan_and_step(*, tool_hint: str | None = None) -> tuple[TaskPlan, PlanStep]:
    step = PlanStep(
        id="inspect",
        title="Inspect",
        description="Inspect the workspace",
        tool_hint=tool_hint,
    )
    return TaskPlan.create(goal="Inspect workspace", steps=(step,)), step


def test_verifier_accepts_non_tool_result() -> None:
    plan, step = _plan_and_step()

    result = RuleBasedVerifier().verify(
        plan=plan,
        step=step,
        runtime_result=RuntimeResult(
            output="Inspection completed.",
            messages=(Message.assistant("Inspection completed."),),
            steps=1,
        ),
    )

    assert result.status == VerificationStatus.PASSED
    assert result.passed is True


def test_verifier_records_missing_tool_evidence_as_inconclusive() -> None:
    plan, step = _plan_and_step(tool_hint="read_text_file")

    result = RuleBasedVerifier().verify(
        plan=plan,
        step=step,
        runtime_result=RuntimeResult(
            output="README was inspected.",
            messages=(Message.assistant("README was inspected."),),
            steps=1,
        ),
    )

    assert result.status == VerificationStatus.INCONCLUSIVE
    assert result.passed is True


def test_verifier_rejects_explicit_tool_failure() -> None:
    plan, step = _plan_and_step(tool_hint="read_text_file")

    result = RuleBasedVerifier().verify(
        plan=plan,
        step=step,
        runtime_result=RuntimeResult(
            output="The file could not be read.",
            messages=(
                Message.tool(
                    name="read_text_file",
                    tool_call_id="call-1",
                    content=json.dumps({"ok": False, "error": "file missing"}),
                ),
                Message.assistant("The file could not be read."),
            ),
            steps=2,
        ),
    )

    assert result.status == VerificationStatus.FAILED
    assert result.passed is False
    assert "file missing" in result.evidence[0]


def test_verifications_are_persisted(tmp_path: Path) -> None:
    plan, step = _plan_and_step()
    store = SQLitePlanStore(tmp_path / "plans.db")
    verification = RuleBasedVerifier().verify(
        plan=plan,
        step=step,
        runtime_result=RuntimeResult(
            output="Done.",
            messages=(Message.assistant("Done."),),
            steps=1,
        ),
    )

    store.save_verification(verification)

    assert store.list_verifications(plan_id=plan.id) == (verification,)


def test_failed_tool_evidence_is_available_to_reflection() -> None:
    plan, step = _plan_and_step(tool_hint="read_text_file")
    verification = RuleBasedVerifier().verify(
        plan=plan,
        step=step,
        runtime_result=RuntimeResult(
            output="The file could not be read.",
            messages=(
                Message.tool(
                    name="read_text_file",
                    tool_call_id="call-1",
                    content=json.dumps(
                        {
                            "ok": False,
                            "error": "File does not exist: missing.txt",
                        }
                    ),
                ),
            ),
            steps=1,
        ),
    )
    error = StepVerificationError(verification)
    failed_step = step.with_status(StepStatus.FAILED, error=str(error))

    reflection = ReflectionEngine().reflect(
        plan=plan.with_steps((failed_step,)),
        failed_step=failed_step,
        error_context=ErrorContext(
            error_type=type(error).__name__,
            error_message=str(error),
            tool_name=step.tool_hint,
            input_summary=step.description,
        ),
    )

    assert reflection.failure_type == FailureType.TOOL_ERROR
    assert reflection.retryable is True
    assert reflection.suggested_action == SuggestedAction.RETRY_WITH_MODIFIED_INPUT
