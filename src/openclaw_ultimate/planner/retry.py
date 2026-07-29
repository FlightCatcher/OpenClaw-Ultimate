from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from openclaw_ultimate.planner.reflection import FailureType, ReflectionResult, SuggestedAction


@dataclass(frozen=True, slots=True)
class RetryAttempt:
    attempt_id: str
    plan_id: str
    step_id: str
    attempt_number: int
    error_type: str
    error_message: str
    error_fingerprint: str
    scheduled: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class RetryDecision:
    allowed: bool
    attempt_number: int
    reason: str
    error_fingerprint: str


class RetryPolicy:
    """限制自动重试次数和适用范围，避免失败循环。"""

    def __init__(self, *, max_retries: int = 1) -> None:
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        self.max_retries = max_retries

    def decide(
        self,
        *,
        reflection: ReflectionResult,
        previous_attempts: tuple[RetryAttempt, ...] = (),
    ) -> RetryDecision:
        fingerprint = self.fingerprint(
            error_type=reflection.original_error_type,
            error_message=reflection.original_error_message,
            step_id=reflection.step_id,
        )
        attempt_number = len(previous_attempts) + 1

        if not reflection.retryable:
            return RetryDecision(False, attempt_number, "Reflection 标记为不可重试。", fingerprint)
        if reflection.suggested_action != SuggestedAction.RETRY_SAME_STEP:
            return RetryDecision(
                False,
                attempt_number,
                "当前建议需要修改输入、工具或模型，系统暂不自动执行。",
                fingerprint,
            )
        if reflection.failure_type != FailureType.TIMEOUT:
            return RetryDecision(
                False,
                attempt_number,
                "仅允许对超时类失败进行原步骤自动重试。",
                fingerprint,
            )
        if attempt_number > self.max_retries:
            return RetryDecision(False, attempt_number, "已达到最大自动重试次数。", fingerprint)
        if any(attempt.error_fingerprint == fingerprint for attempt in previous_attempts):
            return RetryDecision(
                False, attempt_number, "检测到重复错误指纹，停止重试。", fingerprint
            )

        return RetryDecision(True, attempt_number, "允许进行一次受限的超时重试。", fingerprint)

    @staticmethod
    def fingerprint(*, error_type: str, error_message: str, step_id: str) -> str:
        value = f"{step_id}\x00{error_type}\x00{error_message.strip()}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def create_attempt(
        *,
        reflection: ReflectionResult,
        decision: RetryDecision,
    ) -> RetryAttempt:
        return RetryAttempt(
            attempt_id=uuid4().hex,
            plan_id=reflection.plan_id,
            step_id=reflection.step_id,
            attempt_number=decision.attempt_number,
            error_type=reflection.original_error_type,
            error_message=reflection.original_error_message,
            error_fingerprint=decision.error_fingerprint,
            scheduled=decision.allowed,
            created_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
        )
