from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_ultimate.planner import (
    PlanNotFoundError,
    PlanStep,
    SQLitePlanStore,
    TaskPlan,
)


def test_plan_store_round_trip(
    tmp_path: Path,
) -> None:
    store = SQLitePlanStore(tmp_path / "plans.db")
    plan = TaskPlan.create(
        goal="实现 Planner",
        steps=(
            PlanStep(
                id="design",
                title="设计",
                description="设计 DAG",
            ),
            PlanStep(
                id="test",
                title="测试",
                description="测试 DAG",
                dependencies=("design",),
            ),
        ),
    )

    store.save(plan)

    assert store.get(plan.id) == plan
    assert store.list() == (plan,)

    store.delete(plan.id)

    with pytest.raises(PlanNotFoundError):
        store.get(plan.id)
