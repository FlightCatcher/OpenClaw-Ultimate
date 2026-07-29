from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from openclaw_ultimate.planner.graph import TaskGraph
from openclaw_ultimate.planner.models import (
    PlanStatus,
    PlanStep,
    StepStatus,
    TaskPlan,
)


class PlanNotFoundError(KeyError):
    """请求的任务计划不存在。"""


class SQLitePlanStore:
    """持久化任务计划及步骤执行状态。"""

    def __init__(
        self,
        db_path: str | Path,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.initialize()

    @contextmanager
    def _connection(
        self,
    ) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.db_path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                    idx_plans_updated_at
                ON plans(updated_at DESC);
                """
            )

    def save(
        self,
        plan: TaskPlan,
    ) -> TaskPlan:
        TaskGraph(plan.steps)
        payload = json.dumps(
            self._serialize_plan(plan),
            ensure_ascii=False,
        )

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO plans (
                    id,
                    goal,
                    status,
                    plan_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    goal = excluded.goal,
                    status = excluded.status,
                    plan_json = excluded.plan_json,
                    updated_at = excluded.updated_at
                """,
                (
                    plan.id,
                    plan.goal,
                    plan.status.value,
                    payload,
                    plan.created_at,
                    plan.updated_at,
                ),
            )

        return plan

    def get(
        self,
        plan_id: str,
    ) -> TaskPlan:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT plan_json
                FROM plans
                WHERE id = ?
                """,
                (plan_id,),
            ).fetchone()

        if row is None:
            raise PlanNotFoundError(f"Plan not found: {plan_id}")

        try:
            payload = json.loads(row["plan_json"])
        except json.JSONDecodeError as exc:
            raise ValueError("Stored plan contains invalid JSON.") from exc

        return self._deserialize_plan(payload)

    def list(
        self,
        *,
        limit: int = 50,
    ) -> tuple[TaskPlan, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1.")

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT plan_json
                FROM plans
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return tuple(self._deserialize_plan(json.loads(row["plan_json"])) for row in rows)

    def delete(
        self,
        plan_id: str,
    ) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM plans WHERE id = ?",
                (plan_id,),
            )

        if cursor.rowcount == 0:
            raise PlanNotFoundError(f"Plan not found: {plan_id}")

    @staticmethod
    def _serialize_plan(
        plan: TaskPlan,
    ) -> dict[str, Any]:
        return {
            "id": plan.id,
            "goal": plan.goal,
            "status": plan.status.value,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
            "steps": [
                {
                    "id": step.id,
                    "title": step.title,
                    "description": step.description,
                    "dependencies": list(step.dependencies),
                    "tool_hint": step.tool_hint,
                    "status": step.status.value,
                    "result": step.result,
                    "error": step.error,
                }
                for step in plan.steps
            ],
        }

    @staticmethod
    def _deserialize_plan(
        payload: Any,
    ) -> TaskPlan:
        if not isinstance(payload, dict):
            raise TypeError("Stored plan must be an object.")

        raw_steps = payload.get("steps")

        if not isinstance(raw_steps, list):
            raise TypeError("Stored plan steps must be a list.")

        steps = tuple(
            PlanStep(
                id=str(step["id"]),
                title=str(step["title"]),
                description=str(step["description"]),
                dependencies=tuple(
                    str(dependency)
                    for dependency in step.get(
                        "dependencies",
                        [],
                    )
                ),
                tool_hint=step.get("tool_hint"),
                status=StepStatus(
                    step.get(
                        "status",
                        StepStatus.PENDING.value,
                    )
                ),
                result=step.get("result"),
                error=step.get("error"),
            )
            for step in raw_steps
            if isinstance(step, dict)
        )
        TaskGraph(steps)

        return TaskPlan(
            id=str(payload["id"]),
            goal=str(payload["goal"]),
            steps=steps,
            status=PlanStatus(payload["status"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
        )
