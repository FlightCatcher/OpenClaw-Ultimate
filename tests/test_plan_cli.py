from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from openclaw_ultimate.cli import app
from openclaw_ultimate.planner import (
    PlanStep,
    SQLitePlanStore,
    TaskPlan,
)

runner = CliRunner()


def test_plan_list_show_and_delete(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "plans.db"
    environment = {
        "OCU_PLANNER_DB_PATH": str(db_path),
    }
    store = SQLitePlanStore(db_path)
    plan = TaskPlan.create(
        goal="测试 CLI 计划",
        steps=(
            PlanStep(
                id="step-1",
                title="检查",
                description="检查项目",
                tool_hint="list_files",
            ),
        ),
    )
    store.save(plan)

    list_result = runner.invoke(
        app,
        ["plan", "list"],
        env=environment,
    )
    show_result = runner.invoke(
        app,
        ["plan", "show", plan.id],
        env=environment,
    )
    delete_result = runner.invoke(
        app,
        [
            "plan",
            "delete",
            plan.id,
            "--yes",
        ],
        env=environment,
    )

    assert list_result.exit_code == 0
    assert "测试 CLI 计划" in list_result.stdout
    assert show_result.exit_code == 0
    assert "list_files" in show_result.stdout
    assert delete_result.exit_code == 0
    assert store.list() == ()
