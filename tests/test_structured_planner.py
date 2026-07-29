from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.tools import ToolDefinition
from openclaw_ultimate.models.base import ModelResponse
from openclaw_ultimate.planner import (
    PlanningError,
    StructuredPlanner,
)


class PlannerFakeModel:
    def __init__(
        self,
        content: str,
    ) -> None:
        self.content = content

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
    ) -> ModelResponse:
        return ModelResponse(content=self.content)


def test_structured_planner_creates_valid_plan() -> None:
    content = """
    {
      "steps": [
        {
          "id": "inspect",
          "title": "检查仓库",
          "description": "读取项目结构",
          "dependencies": [],
          "tool_hint": "list_files"
        },
        {
          "id": "test",
          "title": "运行测试",
          "description": "验证当前状态",
          "dependencies": ["inspect"],
          "tool_hint": "run_command"
        }
      ]
    }
    """
    planner = StructuredPlanner(PlannerFakeModel(content))

    plan = asyncio.run(planner.create_plan("检查并测试项目"))

    assert plan.goal == "检查并测试项目"
    assert len(plan.steps) == 2
    assert plan.steps[1].dependencies == ("inspect",)


def test_structured_planner_rejects_invalid_json() -> None:
    planner = StructuredPlanner(PlannerFakeModel("not-json"))

    with pytest.raises(
        PlanningError,
        match="JSON",
    ):
        asyncio.run(planner.create_plan("目标"))


def test_structured_planner_enforces_step_limit() -> None:
    planner = StructuredPlanner(
        PlannerFakeModel(
            '{"steps":['
            '{"id":"a","title":"A","description":"A"},'
            '{"id":"b","title":"B","description":"B"}'
            "]}"
        ),
        max_steps=1,
    )

    with pytest.raises(
        PlanningError,
        match="max_steps",
    ):
        asyncio.run(planner.create_plan("目标"))
