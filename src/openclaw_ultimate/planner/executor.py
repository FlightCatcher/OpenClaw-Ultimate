from __future__ import annotations

import logging
from dataclasses import dataclass

from openclaw_ultimate.core.runtime import (
    Agent,
    AgentRuntime,
)
from openclaw_ultimate.governance import PlanControlState, SQLiteGovernanceStore
from openclaw_ultimate.planner.graph import TaskGraph
from openclaw_ultimate.planner.models import (
    PlanStatus,
    PlanStep,
    StepStatus,
    TaskPlan,
)
from openclaw_ultimate.planner.reflection import ErrorContext, ReflectionEngine
from openclaw_ultimate.planner.retry import RetryPolicy
from openclaw_ultimate.planner.store import SQLitePlanStore
from openclaw_ultimate.planner.verification import (
    RuleBasedVerifier,
    StepVerificationError,
)

logger = logging.getLogger(__name__)


class PlanExecutionError(RuntimeError):
    """计划当前不能执行。"""


@dataclass(frozen=True, slots=True)
class PlanExecutionResult:
    plan: TaskPlan
    completed_step_ids: tuple[str, ...]
    failed_step_id: str | None = None
    interrupted_reason: str | None = None


class PlanExecutor:
    """按照 DAG 依赖顺序执行任务计划。"""

    def __init__(
        self,
        *,
        runtime: AgentRuntime | None = None,
        stop_on_failure: bool = True,
        reflection_engine: ReflectionEngine | None = None,
        retry_policy: RetryPolicy | None = None,
        control_store: SQLiteGovernanceStore | None = None,
        verifier: RuleBasedVerifier | None = None,
    ) -> None:
        self.runtime = runtime or AgentRuntime()
        self.stop_on_failure = stop_on_failure
        self.reflection_engine = reflection_engine or ReflectionEngine()
        self.retry_policy = retry_policy or RetryPolicy()
        self.control_store = control_store
        self.verifier = verifier or RuleBasedVerifier()

    async def execute(
        self,
        *,
        plan: TaskPlan,
        agent: Agent,
        store: SQLitePlanStore,
    ) -> PlanExecutionResult:
        if plan.status not in {
            PlanStatus.READY,
            PlanStatus.RUNNING,
        }:
            raise PlanExecutionError(f"Plan cannot run from status: {plan.status.value}")

        current = plan.with_status(PlanStatus.RUNNING)
        store.save(current)
        completed_ids: list[str] = [
            step.id for step in current.steps if step.status == StepStatus.COMPLETED
        ]

        while True:
            interrupted = self._apply_control(current, store)
            if interrupted is not None:
                return PlanExecutionResult(
                    plan=interrupted,
                    completed_step_ids=tuple(completed_ids),
                    interrupted_reason=interrupted.status.value,
                )

            graph = TaskGraph(current.steps)
            ready = graph.ready_steps()

            if not ready:
                break

            for step in ready:
                interrupted = self._apply_control(current, store)
                if interrupted is not None:
                    return PlanExecutionResult(
                        plan=interrupted,
                        completed_step_ids=tuple(completed_ids),
                        interrupted_reason=interrupted.status.value,
                    )

                current = self._replace_step(
                    current,
                    step.with_status(StepStatus.RUNNING),
                )
                store.save(current)

                try:
                    result = await self.runtime.run(
                        agent,
                        self._build_step_prompt(
                            current,
                            step,
                        ),
                    )
                    verification = self.verifier.verify(
                        plan=current,
                        step=step,
                        runtime_result=result,
                    )
                    store.save_verification(verification)
                    if not verification.passed:
                        raise StepVerificationError(verification)
                except Exception as exc:  # noqa: BLE001 - executor must persist any agent failure
                    current = self._replace_step(
                        current,
                        step.with_status(
                            StepStatus.FAILED,
                            error=(f"{type(exc).__name__}: {exc}"),
                        ),
                    )
                    current = current.with_status(PlanStatus.FAILED)
                    store.save(current)

                    reflection = None
                    try:
                        reflection = self.reflection_engine.reflect(
                            plan=current,
                            failed_step=next(
                                candidate for candidate in current.steps if candidate.id == step.id
                            ),
                            error_context=ErrorContext(
                                error_type=type(exc).__name__,
                                error_message=str(exc),
                                tool_name=step.tool_hint,
                                input_summary=step.description,
                            ),
                        )
                        store.save_reflection(reflection)
                    except Exception:
                        # Reflection is diagnostic only; never replace the original failure.
                        logger.exception(
                            "Reflection failed for plan %s step %s", current.id, step.id
                        )

                    if reflection is not None:
                        previous_attempts = store.list_retry_attempts(
                            plan_id=current.id,
                            step_id=step.id,
                        )
                        decision = self.retry_policy.decide(
                            reflection=reflection,
                            previous_attempts=previous_attempts,
                        )
                        attempt = self.retry_policy.create_attempt(
                            reflection=reflection,
                            decision=decision,
                        )
                        store.save_retry_attempt(attempt)

                        if decision.allowed:
                            current = self._replace_step(
                                current.with_status(PlanStatus.RUNNING),
                                step.with_status(StepStatus.PENDING),
                            )
                            store.save(current)
                            continue

                    if self.stop_on_failure:
                        return PlanExecutionResult(
                            plan=current,
                            completed_step_ids=tuple(completed_ids),
                            failed_step_id=step.id,
                        )
                    continue

                current = self._replace_step(
                    current,
                    step.with_status(
                        StepStatus.COMPLETED,
                        result=result.output,
                    ),
                )
                store.save(current)
                completed_ids.append(step.id)

        if all(
            step.status
            in {
                StepStatus.COMPLETED,
                StepStatus.SKIPPED,
            }
            for step in current.steps
        ):
            current = current.with_status(PlanStatus.COMPLETED)
        elif any(step.status == StepStatus.FAILED for step in current.steps):
            current = current.with_status(PlanStatus.FAILED)
        else:
            raise PlanExecutionError("Plan has pending steps but none are ready.")

        store.save(current)

        return PlanExecutionResult(
            plan=current,
            completed_step_ids=tuple(completed_ids),
        )

    def _apply_control(
        self,
        plan: TaskPlan,
        store: SQLitePlanStore,
    ) -> TaskPlan | None:
        if self.control_store is None:
            return None
        state = self.control_store.plan_control_state(plan.id)
        if state == PlanControlState.PAUSE:
            interrupted = plan.with_status(PlanStatus.PAUSED)
        elif state == PlanControlState.CANCEL:
            interrupted = plan.with_status(PlanStatus.CANCELLED)
        else:
            return None
        store.save(interrupted)
        return interrupted

    @staticmethod
    def _replace_step(
        plan: TaskPlan,
        replacement: PlanStep,
    ) -> TaskPlan:
        return plan.with_steps(
            tuple(replacement if step.id == replacement.id else step for step in plan.steps)
        )

    @staticmethod
    def _build_step_prompt(
        plan: TaskPlan,
        step: PlanStep,
    ) -> str:
        dependency_results = [
            (
                dependency.id,
                dependency.result or "",
            )
            for dependency in plan.steps
            if dependency.id in step.dependencies
        ]
        context = "\n".join(f"- {step_id}: {result}" for step_id, result in dependency_results)

        return (
            "执行结构化任务计划中的一个步骤。\n"
            f"总目标：{plan.goal}\n"
            f"步骤 ID：{step.id}\n"
            f"步骤标题：{step.title}\n"
            f"步骤说明：{step.description}\n"
            f"建议工具：{step.tool_hint or '无'}\n"
            "依赖步骤结果：\n"
            f"{context or '无'}\n"
            "请实际调用需要的工具；完成后简洁报告"
            "本步骤的真实结果。不要声称未执行的操作成功。"
        )
