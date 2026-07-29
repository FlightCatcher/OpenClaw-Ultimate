from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

from openclaw_ultimate.planner.graph import TaskGraph
from openclaw_ultimate.planner.models import (
    PlanStatus,
    PlanStep,
    StepStatus,
    TaskPlan,
)
from openclaw_ultimate.planner.reflection import (
    FailureType,
    ReflectionResult,
    SuggestedAction,
)
from openclaw_ultimate.planner.replanning import PlanRevision, RevisionStatus
from openclaw_ultimate.planner.retry import RetryAttempt


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

                CREATE TABLE IF NOT EXISTS reflections (
                    reflection_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    failure_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    retryable INTEGER NOT NULL,
                    suggested_action TEXT NOT NULL,
                    suggested_changes_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    original_error_type TEXT NOT NULL,
                    original_error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                    idx_reflections_plan_step
                ON reflections(plan_id, step_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS retry_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    error_fingerprint TEXT NOT NULL,
                    scheduled INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                    idx_retry_attempts_plan_step
                ON retry_attempts(plan_id, step_id, attempt_number ASC);

                CREATE TABLE IF NOT EXISTS plan_revisions (
                    revision_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    parent_plan_id TEXT NOT NULL,
                    revision_number INTEGER NOT NULL,
                    step_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    suggested_changes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    proposed_step_json TEXT,
                    child_plan_id TEXT
                );

                CREATE INDEX IF NOT EXISTS
                    idx_plan_revisions_plan
                ON plan_revisions(plan_id, revision_number ASC);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(plan_revisions)").fetchall()
            }
            if "proposed_step_json" not in columns:
                connection.execute("ALTER TABLE plan_revisions ADD COLUMN proposed_step_json TEXT")
            if "child_plan_id" not in columns:
                connection.execute("ALTER TABLE plan_revisions ADD COLUMN child_plan_id TEXT")

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

    def save_reflection(
        self,
        reflection: ReflectionResult,
    ) -> ReflectionResult:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO reflections (
                    reflection_id, plan_id, step_id, failure_type, summary,
                    root_cause, retryable, suggested_action, suggested_changes_json,
                    confidence, original_error_type, original_error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reflection_id) DO UPDATE SET
                    summary = excluded.summary,
                    root_cause = excluded.root_cause,
                    retryable = excluded.retryable,
                    suggested_action = excluded.suggested_action,
                    suggested_changes_json = excluded.suggested_changes_json,
                    confidence = excluded.confidence,
                    original_error_type = excluded.original_error_type,
                    original_error_message = excluded.original_error_message
                """,
                (
                    reflection.reflection_id,
                    reflection.plan_id,
                    reflection.step_id,
                    reflection.failure_type.value,
                    reflection.summary,
                    reflection.root_cause,
                    int(reflection.retryable),
                    reflection.suggested_action.value,
                    json.dumps(reflection.suggested_changes, ensure_ascii=False),
                    reflection.confidence,
                    reflection.original_error_type,
                    reflection.original_error_message,
                    reflection.created_at,
                ),
            )
        return reflection

    def list_reflections(
        self,
        *,
        plan_id: str,
        step_id: str | None = None,
    ) -> tuple[ReflectionResult, ...]:
        query = "SELECT * FROM reflections WHERE plan_id = ?"
        parameters: list[str] = [plan_id]
        if step_id is not None:
            query += " AND step_id = ?"
            parameters.append(step_id)
        query += " ORDER BY created_at ASC, reflection_id ASC"

        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return tuple(
            ReflectionResult(
                reflection_id=row["reflection_id"],
                plan_id=row["plan_id"],
                step_id=row["step_id"],
                failure_type=FailureType(row["failure_type"]),
                summary=row["summary"],
                root_cause=row["root_cause"],
                retryable=bool(row["retryable"]),
                suggested_action=SuggestedAction(row["suggested_action"]),
                suggested_changes=tuple(json.loads(row["suggested_changes_json"])),
                confidence=float(row["confidence"]),
                original_error_type=row["original_error_type"],
                original_error_message=row["original_error_message"],
                created_at=row["created_at"],
            )
            for row in rows
        )

    def save_retry_attempt(
        self,
        attempt: RetryAttempt,
    ) -> RetryAttempt:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO retry_attempts (
                    attempt_id, plan_id, step_id, attempt_number, error_type,
                    error_message, error_fingerprint, scheduled, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.attempt_id,
                    attempt.plan_id,
                    attempt.step_id,
                    attempt.attempt_number,
                    attempt.error_type,
                    attempt.error_message,
                    attempt.error_fingerprint,
                    int(attempt.scheduled),
                    attempt.created_at,
                ),
            )
        return attempt

    def list_retry_attempts(
        self,
        *,
        plan_id: str,
        step_id: str,
    ) -> tuple[RetryAttempt, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM retry_attempts
                WHERE plan_id = ? AND step_id = ?
                ORDER BY attempt_number ASC, created_at ASC
                """,
                (plan_id, step_id),
            ).fetchall()

        return tuple(
            RetryAttempt(
                attempt_id=row["attempt_id"],
                plan_id=row["plan_id"],
                step_id=row["step_id"],
                attempt_number=int(row["attempt_number"]),
                error_type=row["error_type"],
                error_message=row["error_message"],
                error_fingerprint=row["error_fingerprint"],
                scheduled=bool(row["scheduled"]),
                created_at=row["created_at"],
            )
            for row in rows
        )

    def list_retry_attempts_for_plan(
        self,
        *,
        plan_id: str,
    ) -> tuple[RetryAttempt, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM retry_attempts
                WHERE plan_id = ?
                ORDER BY step_id ASC, attempt_number ASC, created_at ASC
                """,
                (plan_id,),
            ).fetchall()

        return tuple(
            RetryAttempt(
                attempt_id=row["attempt_id"],
                plan_id=row["plan_id"],
                step_id=row["step_id"],
                attempt_number=int(row["attempt_number"]),
                error_type=row["error_type"],
                error_message=row["error_message"],
                error_fingerprint=row["error_fingerprint"],
                scheduled=bool(row["scheduled"]),
                created_at=row["created_at"],
            )
            for row in rows
        )

    def save_revision(
        self,
        revision: PlanRevision,
    ) -> PlanRevision:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO plan_revisions (
                    revision_id, plan_id, parent_plan_id, revision_number, step_id,
                    status, rationale, suggested_changes_json, created_at,
                    proposed_step_json, child_plan_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision.revision_id,
                    revision.plan_id,
                    revision.parent_plan_id,
                    revision.revision_number,
                    revision.step_id,
                    revision.status.value,
                    revision.rationale,
                    json.dumps(revision.suggested_changes, ensure_ascii=False),
                    revision.created_at,
                    json.dumps(self._serialize_step(revision.proposed_step), ensure_ascii=False)
                    if revision.proposed_step is not None
                    else None,
                    revision.child_plan_id,
                ),
            )
        return revision

    def get_revision(
        self,
        revision_id: str,
    ) -> PlanRevision:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM plan_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
        if row is None:
            raise PlanNotFoundError(f"Revision not found: {revision_id}")
        return self._deserialize_revision(row)

    def update_revision_applied(
        self,
        *,
        revision_id: str,
        child_plan_id: str,
    ) -> PlanRevision:
        revision = self.get_revision(revision_id)
        if revision.status != RevisionStatus.CANDIDATE:
            raise ValueError("Only candidate revisions can be applied.")
        with self._connection() as connection:
            connection.execute(
                "UPDATE plan_revisions SET status = ?, child_plan_id = ? WHERE revision_id = ?",
                (RevisionStatus.APPLIED.value, child_plan_id, revision_id),
            )
        return replace(
            revision,
            status=RevisionStatus.APPLIED,
            child_plan_id=child_plan_id,
        )

    def list_revisions(
        self,
        *,
        plan_id: str,
    ) -> tuple[PlanRevision, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM plan_revisions
                WHERE plan_id = ?
                ORDER BY revision_number ASC, created_at ASC
                """,
                (plan_id,),
            ).fetchall()

        return tuple(self._deserialize_revision(row) for row in rows)

    @staticmethod
    def _serialize_step(step: PlanStep | None) -> dict[str, object] | None:
        if step is None:
            return None
        return {
            "id": step.id,
            "title": step.title,
            "description": step.description,
            "dependencies": list(step.dependencies),
            "tool_hint": step.tool_hint,
            "status": step.status.value,
            "result": step.result,
            "error": step.error,
        }

    @staticmethod
    def _deserialize_revision(row: sqlite3.Row) -> PlanRevision:
        payload = json.loads(row["proposed_step_json"]) if row["proposed_step_json"] else None
        proposed_step = None
        if payload is not None:
            proposed_step = PlanStep(
                id=str(payload["id"]),
                title=str(payload["title"]),
                description=str(payload["description"]),
                dependencies=tuple(str(item) for item in payload.get("dependencies", [])),
                tool_hint=payload.get("tool_hint"),
                status=StepStatus(payload.get("status", StepStatus.PENDING.value)),
                result=payload.get("result"),
                error=payload.get("error"),
            )
        return PlanRevision(
            revision_id=row["revision_id"],
            plan_id=row["plan_id"],
            parent_plan_id=row["parent_plan_id"],
            revision_number=int(row["revision_number"]),
            step_id=row["step_id"],
            status=RevisionStatus(row["status"]),
            rationale=row["rationale"],
            suggested_changes=tuple(json.loads(row["suggested_changes_json"])),
            created_at=row["created_at"],
            proposed_step=proposed_step,
            child_plan_id=row["child_plan_id"],
        )

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
