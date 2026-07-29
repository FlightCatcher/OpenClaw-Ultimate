from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from openclaw_ultimate.core.messages import (
    Message,
    Role,
    ToolCall,
)
from openclaw_ultimate.sessions.models import (
    SessionRecord,
    SessionSummaryRecord,
)


class SessionStoreError(RuntimeError):
    """Session Store 基础异常。"""


class SessionNotFoundError(SessionStoreError):
    """请求的 Session 不存在。"""


class SQLiteSessionStore:
    """使用 SQLite 保存会话和完整消息历史。"""

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
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """创建数据库表和索引。"""

        with self._connection() as connection:
            connection.execute(
                "PRAGMA journal_mode = WAL"
            )
            connection.execute(
                "PRAGMA synchronous = NORMAL"
            )

            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    name TEXT,
                    tool_call_id TEXT,
                    tool_calls_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    covered_message_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS
                    idx_messages_session_id
                ON messages(session_id, id);

                CREATE INDEX IF NOT EXISTS
                    idx_sessions_updated_at
                ON sessions(updated_at DESC);
                """
            )

    def create_session(
        self,
        title: str = "新会话",
    ) -> SessionRecord:
        """创建一个新会话。"""

        clean_title = self._validate_title(title)
        session_id = uuid4().hex
        now = self._utc_now()

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    id,
                    title,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    clean_title,
                    now,
                    now,
                ),
            )

        return SessionRecord(
            id=session_id,
            title=clean_title,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

    def get_session(
        self,
        session_id: str,
    ) -> SessionRecord:
        """根据 ID 获取一个会话。"""

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    (
                        SELECT COUNT(*)
                        FROM messages AS m
                        WHERE m.session_id = s.id
                    ) AS message_count
                FROM sessions AS s
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            raise SessionNotFoundError(
                f"Session not found: {session_id}"
            )

        return self._row_to_session(row)

    def list_sessions(
        self,
        *,
        limit: int = 50,
    ) -> tuple[SessionRecord, ...]:
        """按照最近更新时间列出会话。"""

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    (
                        SELECT COUNT(*)
                        FROM messages AS m
                        WHERE m.session_id = s.id
                    ) AS message_count
                FROM sessions AS s
                ORDER BY s.updated_at DESC, s.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return tuple(
            self._row_to_session(row)
            for row in rows
        )

    def rename_session(
        self,
        session_id: str,
        title: str,
    ) -> SessionRecord:
        """修改会话标题。"""

        clean_title = self._validate_title(title)
        now = self._utc_now()

        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    clean_title,
                    now,
                    session_id,
                ),
            )

        if cursor.rowcount == 0:
            raise SessionNotFoundError(
                f"Session not found: {session_id}"
            )

        return self.get_session(session_id)

    def delete_session(
        self,
        session_id: str,
    ) -> None:
        """删除会话及其全部消息。"""

        with self._connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            )

        if cursor.rowcount == 0:
            raise SessionNotFoundError(
                f"Session not found: {session_id}"
            )

    def append_messages(
        self,
        session_id: str,
        messages: Iterable[Message],
    ) -> int:
        """向会话追加消息，返回新增消息数量。"""

        message_items = tuple(messages)

        if not message_items:
            return 0

        now = self._utc_now()

        with self._connection() as connection:
            session_exists = connection.execute(
                """
                SELECT 1
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()

            if session_exists is None:
                raise SessionNotFoundError(
                    f"Session not found: {session_id}"
                )

            connection.executemany(
                """
                INSERT INTO messages (
                    session_id,
                    role,
                    content,
                    name,
                    tool_call_id,
                    tool_calls_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        message.role,
                        message.content,
                        message.name,
                        message.tool_call_id,
                        self._serialize_tool_calls(
                            message.tool_calls
                        ),
                        now,
                    )
                    for message in message_items
                ],
            )

            connection.execute(
                """
                UPDATE sessions
                SET updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    session_id,
                ),
            )

        return len(message_items)

    def load_messages(
        self,
        session_id: str,
        *,
        limit: int | None = None,
    ) -> tuple[Message, ...]:
        """读取会话消息。

        设置 limit 后，会保留最早的 system 消息，
        再读取最近的 limit 条非 system 消息。
        """

        self.get_session(session_id)

        if limit is not None and limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        with self._connection() as connection:
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY id ASC
                    """,
                    (session_id,),
                ).fetchall()
            else:
                system_row = connection.execute(
                    """
                    SELECT *
                    FROM messages
                    WHERE session_id = ?
                      AND role = 'system'
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()

                recent_rows = connection.execute(
                    """
                    SELECT *
                    FROM messages
                    WHERE session_id = ?
                      AND role != 'system'
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (
                        session_id,
                        limit,
                    ),
                ).fetchall()

                rows_by_id: dict[int, sqlite3.Row] = {
                    int(row["id"]): row
                    for row in recent_rows
                }

                if system_row is not None:
                    rows_by_id[
                        int(system_row["id"])
                    ] = system_row

                rows = [
                    rows_by_id[row_id]
                    for row_id in sorted(rows_by_id)
                ]

        return tuple(
            self._row_to_message(row)
            for row in rows
        )


    def get_summary(
        self,
        session_id: str,
    ) -> SessionSummaryRecord | None:
        """读取会话滚动摘要。"""

        self.get_session(session_id)

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    session_id,
                    summary,
                    covered_message_count,
                    updated_at
                FROM session_summaries
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            return None

        return SessionSummaryRecord(
            session_id=str(row["session_id"]),
            summary=str(row["summary"]),
            covered_message_count=int(
                row["covered_message_count"]
            ),
            updated_at=str(row["updated_at"]),
        )

    def upsert_summary(
        self,
        *,
        session_id: str,
        summary: str,
        covered_message_count: int,
    ) -> SessionSummaryRecord:
        """创建或更新滚动摘要。"""

        clean_summary = summary.strip()

        if not clean_summary:
            raise ValueError(
                "Session summary cannot be empty."
            )

        if covered_message_count < 0:
            raise ValueError(
                "covered_message_count cannot be negative."
            )

        self.get_session(session_id)
        now = self._utc_now()

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO session_summaries (
                    session_id,
                    summary,
                    covered_message_count,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET
                    summary = excluded.summary,
                    covered_message_count =
                        excluded.covered_message_count,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    clean_summary,
                    covered_message_count,
                    now,
                ),
            )

        return SessionSummaryRecord(
            session_id=session_id,
            summary=clean_summary,
            covered_message_count=(
                covered_message_count
            ),
            updated_at=now,
        )

    def clear_summary(
        self,
        session_id: str,
    ) -> bool:
        """删除当前会话摘要。"""

        self.get_session(session_id)

        with self._connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM session_summaries
                WHERE session_id = ?
                """,
                (session_id,),
            )

        return cursor.rowcount > 0

    @staticmethod
    def _serialize_tool_calls(
        tool_calls: Iterable[ToolCall],
    ) -> str:
        payload = [
            {
                "id": tool_call.id,
                "name": tool_call.name,
                "arguments": dict(
                    tool_call.arguments
                ),
            }
            for tool_call in tool_calls
        ]

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )

    @staticmethod
    def _deserialize_tool_calls(
        raw_value: str,
    ) -> tuple[ToolCall, ...]:
        try:
            payload = json.loads(
                raw_value or "[]"
            )
        except json.JSONDecodeError as exc:
            raise SessionStoreError(
                "Stored tool calls contain invalid JSON."
            ) from exc

        if not isinstance(payload, list):
            raise SessionStoreError(
                "Stored tool calls must be a list."
            )

        tool_calls: list[ToolCall] = []

        for item in payload:
            if not isinstance(item, dict):
                raise SessionStoreError(
                    "Stored tool call must be an object."
                )

            arguments = item.get("arguments", {})

            if not isinstance(arguments, dict):
                raise SessionStoreError(
                    "Stored tool arguments must be an object."
                )

            tool_calls.append(
                ToolCall(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    arguments=arguments,
                )
            )

        return tuple(tool_calls)

    @classmethod
    def _row_to_message(
        cls,
        row: sqlite3.Row,
    ) -> Message:
        return Message(
            role=cast(Role, row["role"]),
            content=row["content"],
            name=row["name"],
            tool_call_id=row["tool_call_id"],
            tool_calls=cls._deserialize_tool_calls(
                row["tool_calls_json"]
            ),
        )

    @staticmethod
    def _row_to_session(
        row: sqlite3.Row,
    ) -> SessionRecord:
        return SessionRecord(
            id=str(row["id"]),
            title=str(row["title"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            message_count=int(
                row["message_count"]
            ),
        )

    @staticmethod
    def _validate_title(title: str) -> str:
        clean_title = title.strip()

        if not clean_title:
            raise ValueError(
                "Session title cannot be empty."
            )

        return clean_title[:120]

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat(
            timespec="milliseconds"
        )
