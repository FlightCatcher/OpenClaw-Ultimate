from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.tools import ToolDefinition
from openclaw_ultimate.models.base import ModelClient
from openclaw_ultimate.planner.graph import TaskGraph
from openclaw_ultimate.planner.models import (
    PlanStep,
    TaskPlan,
)


class PlanningError(RuntimeError):
    """模型无法生成有效任务计划。"""


class StructuredPlanner:
    """使用模型生成可验证的 DAG 任务计划。"""

    def __init__(
        self,
        model: ModelClient,
        *,
        max_steps: int = 12,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1.")

        self.model = model
        self.max_steps = max_steps

    async def create_plan(
        self,
        goal: str,
        *,
        tools: Sequence[ToolDefinition] = (),
    ) -> TaskPlan:
        clean_goal = goal.strip()

        if not clean_goal:
            raise ValueError("Planning goal cannot be empty.")

        response = await self.model.complete(
            messages=(
                Message.system(self._system_prompt(tools)),
                Message.user(clean_goal),
            ),
            tools=(),
        )
        content = (response.content or "").strip()

        if not content:
            raise PlanningError("Planner model returned empty content.")

        payload = self._parse_json(content)
        steps = self._parse_steps(payload)
        TaskGraph(steps)

        return TaskPlan.create(
            goal=clean_goal,
            steps=steps,
        )

    def _system_prompt(
        self,
        tools: Sequence[ToolDefinition],
    ) -> str:
        tool_names = [tool.name for tool in tools]

        return (
            "你是 OpenClaw-Ultimate 的任务规划器。"
            "把用户目标拆成可验证、粒度适中的有向无环步骤。"
            f"最多 {self.max_steps} 步。"
            "只输出 JSON，不要 Markdown。格式："
            '{"steps":[{"id":"step-1","title":"...",'
            '"description":"...","dependencies":[],'
            '"tool_hint":"可选工具名或null"}]}。'
            "依赖只能引用已有步骤；步骤 ID 必须唯一。"
            f"可用工具：{tool_names or ['none']}。"
        )

    @staticmethod
    def _parse_json(
        content: str,
    ) -> dict[str, Any]:
        candidate = content.strip()

        if candidate.startswith("```"):
            lines = candidate.splitlines()
            candidate = "\n".join(lines[1:-1]).strip()

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise PlanningError("Planner response was not valid JSON.") from exc

        if not isinstance(payload, dict):
            raise PlanningError("Planner response root must be an object.")

        return payload

    def _parse_steps(
        self,
        payload: dict[str, Any],
    ) -> tuple[PlanStep, ...]:
        raw_steps = payload.get("steps")

        if not isinstance(raw_steps, list) or not raw_steps:
            raise PlanningError("Planner response has no steps.")

        if len(raw_steps) > self.max_steps:
            raise PlanningError("Planner response exceeds max_steps.")

        steps: list[PlanStep] = []

        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                raise PlanningError("Planner step must be an object.")

            dependencies = raw_step.get(
                "dependencies",
                [],
            )

            if not isinstance(dependencies, list):
                raise PlanningError("Step dependencies must be a list.")

            tool_hint = raw_step.get("tool_hint")

            if tool_hint is not None and not isinstance(tool_hint, str):
                raise PlanningError("Step tool_hint must be text or null.")

            steps.append(
                PlanStep(
                    id=str(raw_step.get("id", "")),
                    title=str(raw_step.get("title", "")),
                    description=str(
                        raw_step.get(
                            "description",
                            "",
                        )
                    ),
                    dependencies=tuple(str(dependency) for dependency in dependencies),
                    tool_hint=tool_hint,
                )
            )

        return tuple(steps)
