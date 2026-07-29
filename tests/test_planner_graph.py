from __future__ import annotations

import pytest

from openclaw_ultimate.planner import (
    PlanStep,
    PlanValidationError,
    StepStatus,
    TaskGraph,
)


def test_graph_orders_dependencies_and_finds_ready_steps() -> None:
    steps = (
        PlanStep(
            id="build",
            title="构建",
            description="实现功能",
            dependencies=("inspect",),
        ),
        PlanStep(
            id="inspect",
            title="检查",
            description="检查仓库",
            status=StepStatus.COMPLETED,
        ),
        PlanStep(
            id="test",
            title="测试",
            description="运行测试",
            dependencies=("build",),
        ),
    )
    graph = TaskGraph(steps)

    assert [step.id for step in graph.topological_order()] == ["inspect", "build", "test"]
    assert [step.id for step in graph.ready_steps()] == ["build"]


def test_graph_rejects_cycle() -> None:
    with pytest.raises(
        PlanValidationError,
        match="cycle",
    ):
        TaskGraph(
            (
                PlanStep(
                    id="a",
                    title="A",
                    description="A",
                    dependencies=("b",),
                ),
                PlanStep(
                    id="b",
                    title="B",
                    description="B",
                    dependencies=("a",),
                ),
            )
        )


def test_graph_rejects_unknown_dependency() -> None:
    with pytest.raises(
        PlanValidationError,
        match="unknown",
    ):
        TaskGraph(
            (
                PlanStep(
                    id="a",
                    title="A",
                    description="A",
                    dependencies=("missing",),
                ),
            )
        )
