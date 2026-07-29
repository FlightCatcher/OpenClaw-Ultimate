from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.runtime import RuntimeResult
from openclaw_ultimate.planner.models import PlanStep, TaskPlan


class VerificationStatus(StrEnum):
    """A step result's verification outcome."""

    PASSED = "passed"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Persistable evidence describing whether an execution result is trustworthy."""

    verification_id: str
    plan_id: str
    step_id: str
    status: VerificationStatus
    summary: str
    evidence: tuple[str, ...]
    confidence: float
    created_at: str

    @property
    def passed(self) -> bool:
        """Return whether the result is safe to mark completed."""

        return self.status != VerificationStatus.FAILED


class StepVerificationError(RuntimeError):
    """The runtime returned a result that failed deterministic verification."""

    def __init__(self, verification: VerificationResult) -> None:
        self.verification = verification
        evidence = "; ".join(verification.evidence)
        detail = f"{verification.summary} Evidence: {evidence}" if evidence else verification.summary
        super().__init__(detail)


class RuleBasedVerifier:
    """Verify runtime output and tool evidence without another model call."""

    def verify(
        self,
        *,
        plan: TaskPlan,
        step: PlanStep,
        runtime_result: RuntimeResult,
    ) -> VerificationResult:
        output = runtime_result.output.strip()
        if not output:
            return self._result(
                plan=plan,
                step=step,
                status=VerificationStatus.FAILED,
                summary="The model returned no final output.",
                evidence=("runtime output was empty",),
                confidence=1.0,
            )

        tool_messages = tuple(
            message for message in runtime_result.messages if message.role == "tool"
        )
        if step.tool_hint:
            matching = tuple(message for message in tool_messages if message.name == step.tool_hint)
            if not matching:
                return self._result(
                    plan=plan,
                    step=step,
                    status=VerificationStatus.INCONCLUSIVE,
                    summary=(
                        f"No direct tool evidence was recorded for suggested tool "
                        f"'{step.tool_hint}'."
                    ),
                    evidence=("non-empty final output",),
                    confidence=0.45,
                )
            return self._verify_tool_messages(
                plan=plan,
                step=step,
                messages=matching,
                output=output,
            )

        if tool_messages:
            return self._verify_tool_messages(
                plan=plan,
                step=step,
                messages=tool_messages,
                output=output,
            )

        return self._result(
            plan=plan,
            step=step,
            status=VerificationStatus.PASSED,
            summary="The step returned a non-empty result and required no tool evidence.",
            evidence=("non-empty final output",),
            confidence=0.75,
        )

    def _verify_tool_messages(
        self,
        *,
        plan: TaskPlan,
        step: PlanStep,
        messages: tuple[Message, ...],
        output: str,
    ) -> VerificationResult:
        successful: list[str] = []
        failed: list[str] = []
        unreadable: list[str] = []

        for message in messages:
            label = message.name or "unnamed_tool"
            payload = self._parse_payload(message.content)
            if payload is None or not isinstance(payload.get("ok"), bool):
                unreadable.append(label)
            elif payload["ok"]:
                successful.append(label)
            else:
                error = str(payload.get("error", "unknown error"))
                failed.append(f"{label}: {error}")

        if successful:
            return self._result(
                plan=plan,
                step=step,
                status=VerificationStatus.PASSED,
                summary="At least one tool call completed successfully.",
                evidence=(
                    f"successful tools: {', '.join(successful)}",
                    "non-empty final output",
                ),
                confidence=0.95,
            )

        if failed and not unreadable:
            return self._result(
                plan=plan,
                step=step,
                status=VerificationStatus.FAILED,
                summary="Every recorded tool call failed.",
                evidence=tuple(failed),
                confidence=0.98,
            )

        return self._result(
            plan=plan,
            step=step,
            status=VerificationStatus.INCONCLUSIVE,
            summary="Tool evidence could not be interpreted deterministically.",
            evidence=tuple(failed + [f"unreadable tool result: {name}" for name in unreadable])
            or (f"final output: {output[:160]}",),
            confidence=0.35,
        )

    @staticmethod
    def _parse_payload(content: str | None) -> dict[str, object] | None:
        if not content:
            return None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _result(
        *,
        plan: TaskPlan,
        step: PlanStep,
        status: VerificationStatus,
        summary: str,
        evidence: tuple[str, ...],
        confidence: float,
    ) -> VerificationResult:
        return VerificationResult(
            verification_id=uuid4().hex,
            plan_id=plan.id,
            step_id=step.id,
            status=status,
            summary=summary,
            evidence=evidence,
            confidence=confidence,
            created_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
        )
