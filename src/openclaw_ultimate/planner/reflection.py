from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from openclaw_ultimate.planner.models import PlanStep, StepStatus, TaskPlan


class FailureType(StrEnum):
    TOOL_ERROR = "tool_error"
    MODEL_ERROR = "model_error"
    TIMEOUT = "timeout"
    PERMISSION_ERROR = "permission_error"
    VALIDATION_ERROR = "validation_error"
    DEPENDENCY_ERROR = "dependency_error"
    PERSISTENCE_ERROR = "persistence_error"
    USER_INPUT_REQUIRED = "user_input_required"
    UNKNOWN = "unknown"


class SuggestedAction(StrEnum):
    RETRY_SAME_STEP = "retry_same_step"
    RETRY_WITH_MODIFIED_INPUT = "retry_with_modified_input"
    CHOOSE_DIFFERENT_TOOL = "choose_different_tool"
    CHOOSE_DIFFERENT_MODEL = "choose_different_model"
    REVISE_PLAN = "revise_plan"
    REQUEST_USER_INPUT = "request_user_input"
    ABORT_PLAN = "abort_plan"
    NO_ACTION = "no_action"


@dataclass(frozen=True, slots=True)
class ErrorContext:
    error_type: str
    error_message: str
    tool_name: str | None = None
    input_summary: str | None = None
    dependency_failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReflectionResult:
    reflection_id: str
    plan_id: str
    step_id: str
    failure_type: FailureType
    summary: str
    root_cause: str
    retryable: bool
    suggested_action: SuggestedAction
    suggested_changes: tuple[str, ...]
    confidence: float
    original_error_type: str
    original_error_message: str
    created_at: str


class RuleBasedReflector:
    """离线、无副作用的失败分类器。"""

    def reflect(
        self,
        *,
        plan: TaskPlan,
        failed_step: PlanStep,
        error_context: ErrorContext,
    ) -> ReflectionResult:
        if failed_step.status != StepStatus.FAILED:
            raise ValueError("Reflection requires a failed step.")

        failure_type, action, retryable, root_cause, changes = self._classify(
            plan=plan,
            failed_step=failed_step,
            error_context=error_context,
        )
        summary = (
            f"步骤“{failed_step.title}”失败，分类为 {failure_type.value}；建议：{action.value}。"
        )

        return ReflectionResult(
            reflection_id=uuid4().hex,
            plan_id=plan.id,
            step_id=failed_step.id,
            failure_type=failure_type,
            summary=summary,
            root_cause=root_cause,
            retryable=retryable,
            suggested_action=action,
            suggested_changes=changes,
            confidence=0.95 if failure_type != FailureType.UNKNOWN else 0.55,
            original_error_type=error_context.error_type,
            original_error_message=error_context.error_message,
            created_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
        )

    def _classify(
        self,
        *,
        plan: TaskPlan,
        failed_step: PlanStep,
        error_context: ErrorContext,
    ) -> tuple[FailureType, SuggestedAction, bool, str, tuple[str, ...]]:
        error_type = error_context.error_type.casefold()
        message = error_context.error_message.casefold()

        if error_context.dependency_failures:
            return (
                FailureType.DEPENDENCY_ERROR,
                SuggestedAction.REVISE_PLAN,
                False,
                "一个或多个依赖步骤失败，当前步骤缺少可靠输入。",
                tuple(f"检查依赖步骤：{step_id}" for step_id in error_context.dependency_failures),
            )
        if "timeout" in error_type or "timed out" in message:
            return (
                FailureType.TIMEOUT,
                SuggestedAction.RETRY_SAME_STEP,
                True,
                "步骤执行超过了允许的时间限制。",
                ("检查超时设置或拆分步骤。",),
            )
        if "permission" in error_type or "access denied" in message:
            return (
                FailureType.PERMISSION_ERROR,
                SuggestedAction.REQUEST_USER_INPUT,
                False,
                "当前操作缺少所需权限，不能安全地自动重试。",
                ("确认目标路径和所需权限。",),
            )
        if "filenotfound" in error_type or "file does not exist" in message:
            return (
                FailureType.TOOL_ERROR,
                SuggestedAction.RETRY_WITH_MODIFIED_INPUT,
                True,
                "工具找不到请求的文件或路径。",
                ("核对文件路径、工作区范围和文件是否存在。",),
            )
        if "validation" in error_type or "invalid" in message:
            return (
                FailureType.VALIDATION_ERROR,
                SuggestedAction.RETRY_WITH_MODIFIED_INPUT,
                True,
                "步骤输入或工具参数未通过校验。",
                ("根据校验错误修正结构化输入。",),
            )
        if any(term in message for term in ("model", "ollama", "connection refused")):
            return (
                FailureType.MODEL_ERROR,
                SuggestedAction.CHOOSE_DIFFERENT_MODEL,
                True,
                "模型服务不可用、模型不存在或连接失败。",
                ("检查模型服务健康状态和可用模型列表。",),
            )
        if "unknown tool" in message or "tool" in error_type and "not found" in message:
            return (
                FailureType.TOOL_ERROR,
                SuggestedAction.CHOOSE_DIFFERENT_TOOL,
                True,
                "请求的工具不存在或未注册。",
                ("检查工具注册表和工具名称。",),
            )
        return (
            FailureType.UNKNOWN,
            SuggestedAction.REQUEST_USER_INPUT,
            False,
            "无法根据现有错误上下文确定安全的恢复方式。",
            (f"检查步骤“{failed_step.id}”及其执行上下文。", f"计划目标：{plan.goal}"),
        )


class ReflectionEngine:
    """只分析失败，不执行建议。"""

    def __init__(self, reflector: RuleBasedReflector | None = None) -> None:
        self.reflector = reflector or RuleBasedReflector()

    def reflect(
        self,
        *,
        plan: TaskPlan,
        failed_step: PlanStep,
        error_context: ErrorContext,
    ) -> ReflectionResult:
        return self.reflector.reflect(
            plan=plan,
            failed_step=failed_step,
            error_context=error_context,
        )
