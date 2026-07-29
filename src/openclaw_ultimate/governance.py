from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock, RLock
from typing import Any, ClassVar
from uuid import uuid4


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    HIGH = "high"


class ConfirmationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONSUMED = "consumed"


class PlanControlState(StrEnum):
    RUN = "run"
    PAUSE = "pause"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    category: str
    action: str
    outcome: str
    actor: str
    resource_id: str | None
    metadata: Mapping[str, Any]
    created_at: str


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    confirmation_id: str
    action: str
    description: str
    risk: RiskLevel
    resource_id: str | None
    status: ConfirmationStatus
    created_at: str
    resolved_at: str | None


class ConfirmationRequired(PermissionError):
    def __init__(self, request: ConfirmationRequest) -> None:
        self.request = request
        super().__init__(
            f"Confirmation required for '{request.action}' "
            f"(confirmation_id={request.confirmation_id})."
        )


class SQLiteGovernanceStore:
    """Versioned local state for audit, confirmations, and task controls."""

    schema_version = 1
    _lock_registry: ClassVar[dict[str, RLock]] = {}
    _lock_registry_guard: ClassVar[Lock] = Lock()

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        lock_key = str(self.db_path.resolve())
        with self._lock_registry_guard:
            self._lock = self._lock_registry.setdefault(lock_key, RLock())
        self.initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = sqlite3.connect(self.db_path, timeout=5)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 5000")
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
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    resource_id TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_created
                ON audit_events(created_at DESC);

                CREATE TABLE IF NOT EXISTS confirmations (
                    confirmation_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    description TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    resource_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_confirmation_status
                ON confirmations(status, created_at DESC);

                CREATE TABLE IF NOT EXISTS plan_controls (
                    plan_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO schema_migrations(version, applied_at)
                VALUES (?, ?)
                """,
                (self.schema_version, self._utc_now()),
            )

    def audit(
        self,
        *,
        category: str,
        action: str,
        outcome: str,
        actor: str = "local",
        resource_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=uuid4().hex,
            category=self._clean(category, "category"),
            action=self._clean(action, "action"),
            outcome=self._clean(outcome, "outcome"),
            actor=self._clean(actor, "actor"),
            resource_id=resource_id,
            metadata=dict(metadata or {}),
            created_at=self._utc_now(),
        )
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_events(
                    event_id, category, action, outcome, actor,
                    resource_id, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.category,
                    event.action,
                    event.outcome,
                    event.actor,
                    event.resource_id,
                    json.dumps(event.metadata, ensure_ascii=False, default=str),
                    event.created_at,
                ),
            )
        return event

    def list_audit(self, *, limit: int = 100) -> tuple[AuditEvent, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000.")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._audit_from_row(row) for row in rows)

    def request_confirmation(
        self,
        *,
        action: str,
        description: str,
        risk: RiskLevel,
        resource_id: str | None = None,
    ) -> ConfirmationRequest:
        request = ConfirmationRequest(
            confirmation_id=uuid4().hex,
            action=self._clean(action, "action"),
            description=self._clean(description, "description"),
            risk=risk,
            resource_id=resource_id,
            status=ConfirmationStatus.PENDING,
            created_at=self._utc_now(),
            resolved_at=None,
        )
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO confirmations(
                    confirmation_id, action, description, risk, resource_id,
                    status, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.confirmation_id,
                    request.action,
                    request.description,
                    request.risk.value,
                    request.resource_id,
                    request.status.value,
                    request.created_at,
                    request.resolved_at,
                ),
            )
        self.audit(
            category="safety",
            action="confirmation.requested",
            outcome="pending",
            resource_id=request.confirmation_id,
            metadata={"requested_action": request.action, "risk": request.risk.value},
        )
        return request

    def list_confirmations(
        self,
        *,
        status: ConfirmationStatus | None = None,
        limit: int = 100,
    ) -> tuple[ConfirmationRequest, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000.")
        query = "SELECT * FROM confirmations"
        parameters: list[Any] = []
        if status is not None:
            query += " WHERE status = ?"
            parameters.append(status.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(limit)
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(self._confirmation_from_row(row) for row in rows)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        *,
        approve: bool,
    ) -> ConfirmationRequest:
        status = ConfirmationStatus.APPROVED if approve else ConfirmationStatus.REJECTED
        resolved_at = self._utc_now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE confirmations
                SET status = ?, resolved_at = ?
                WHERE confirmation_id = ? AND status = ?
                """,
                (
                    status.value,
                    resolved_at,
                    confirmation_id,
                    ConfirmationStatus.PENDING.value,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Pending confirmation not found: {confirmation_id}")
            row = connection.execute(
                "SELECT * FROM confirmations WHERE confirmation_id = ?",
                (confirmation_id,),
            ).fetchone()
        assert row is not None
        request = self._confirmation_from_row(row)
        self.audit(
            category="safety",
            action="confirmation.resolved",
            outcome=status.value,
            resource_id=confirmation_id,
            metadata={"requested_action": request.action},
        )
        return request

    def require_confirmation(
        self,
        *,
        action: str,
        description: str,
        risk: RiskLevel,
        resource_id: str | None = None,
    ) -> None:
        if risk == RiskLevel.READ_ONLY:
            return
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM confirmations
                WHERE action = ?
                  AND COALESCE(resource_id, '') = COALESCE(?, '')
                  AND status = ?
                ORDER BY resolved_at DESC
                LIMIT 1
                """,
                (action, resource_id, ConfirmationStatus.APPROVED.value),
            ).fetchone()
            if row is not None:
                connection.execute(
                    """
                    UPDATE confirmations
                    SET status = ?
                    WHERE confirmation_id = ?
                    """,
                    (ConfirmationStatus.CONSUMED.value, row["confirmation_id"]),
                )
                return
        raise ConfirmationRequired(
            self.request_confirmation(
                action=action,
                description=description,
                risk=risk,
                resource_id=resource_id,
            )
        )

    def set_plan_control(
        self,
        plan_id: str,
        state: PlanControlState,
    ) -> None:
        clean_plan_id = self._clean(plan_id, "plan_id")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO plan_controls(plan_id, state, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(plan_id) DO UPDATE SET
                    state = excluded.state,
                    updated_at = excluded.updated_at
                """,
                (clean_plan_id, state.value, self._utc_now()),
            )
        self.audit(
            category="plan",
            action="control.set",
            outcome=state.value,
            resource_id=clean_plan_id,
        )

    def plan_control_state(self, plan_id: str) -> PlanControlState:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT state FROM plan_controls WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        return PlanControlState(row["state"]) if row else PlanControlState.RUN

    def schema_versions(self) -> tuple[int, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        return tuple(int(row["version"]) for row in rows)

    @staticmethod
    def _clean(value: str, field: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{field} cannot be empty.")
        return cleaned

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds")

    @staticmethod
    def _audit_from_row(row: sqlite3.Row) -> AuditEvent:
        metadata = json.loads(row["metadata_json"])
        return AuditEvent(
            event_id=row["event_id"],
            category=row["category"],
            action=row["action"],
            outcome=row["outcome"],
            actor=row["actor"],
            resource_id=row["resource_id"],
            metadata=metadata if isinstance(metadata, dict) else {},
            created_at=row["created_at"],
        )

    @staticmethod
    def _confirmation_from_row(row: sqlite3.Row) -> ConfirmationRequest:
        return ConfirmationRequest(
            confirmation_id=row["confirmation_id"],
            action=row["action"],
            description=row["description"],
            risk=RiskLevel(row["risk"]),
            resource_id=row["resource_id"],
            status=ConfirmationStatus(row["status"]),
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
        )
