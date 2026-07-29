from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """一条持久化长期记忆。"""

    id: str
    content: str
    embedding: tuple[float, ...]
    source_session_id: str | None
    created_at: str
    updated_at: str
    memory_type: str = "fact"
    importance: float = 0.5
    sensitivity: str = "normal"
    expires_at: str | None = None
    archived: bool = False
    last_accessed_at: str | None = None


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    """带相似度分数的长期记忆检索结果。"""

    memory: MemoryRecord
    score: float


class SQLiteMemoryStore:
    """使用 SQLite 保存向量，并在本地执行余弦检索。"""

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
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    source_session_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                    idx_memories_updated_at
                ON memories(updated_at DESC);
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(memories)").fetchall()
            }
            migrations = {
                "memory_type": "TEXT NOT NULL DEFAULT 'fact'",
                "importance": "REAL NOT NULL DEFAULT 0.5",
                "sensitivity": "TEXT NOT NULL DEFAULT 'normal'",
                "expires_at": "TEXT",
                "archived": "INTEGER NOT NULL DEFAULT 0",
                "last_accessed_at": "TEXT",
            }
            for column, definition in migrations.items():
                if column not in columns:
                    connection.execute(f"ALTER TABLE memories ADD COLUMN {column} {definition}")

    def add(
        self,
        *,
        content: str,
        embedding: Sequence[float],
        source_session_id: str | None = None,
        memory_type: str = "fact",
        importance: float = 0.5,
        sensitivity: str = "normal",
        expires_at: str | None = None,
    ) -> MemoryRecord:
        clean_content = content.strip()
        vector = self._validate_embedding(embedding)

        if not clean_content:
            raise ValueError("Memory content cannot be empty.")
        clean_type = self._validate_label(memory_type, "memory_type")
        clean_sensitivity = self._validate_label(sensitivity, "sensitivity")
        if not 0 <= importance <= 1:
            raise ValueError("importance must be between 0 and 1.")

        memory_id = uuid4().hex
        now = self._utc_now()

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    id,
                    content,
                    embedding_json,
                    source_session_id,
                    created_at,
                    updated_at,
                    memory_type,
                    importance,
                    sensitivity,
                    expires_at,
                    archived,
                    last_accessed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    clean_content,
                    json.dumps(vector),
                    source_session_id,
                    now,
                    now,
                    clean_type,
                    importance,
                    clean_sensitivity,
                    expires_at,
                    0,
                    None,
                ),
            )

        return MemoryRecord(
            id=memory_id,
            content=clean_content,
            embedding=vector,
            source_session_id=source_session_id,
            created_at=now,
            updated_at=now,
            memory_type=clean_type,
            importance=importance,
            sensitivity=clean_sensitivity,
            expires_at=expires_at,
        )

    def get(
        self,
        memory_id: str,
    ) -> MemoryRecord:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM memories
                WHERE id = ?
                """,
                (memory_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Memory not found: {memory_id}")

        return self._row_to_memory(row)

    def list(
        self,
        *,
        limit: int = 50,
        include_archived: bool = False,
        include_expired: bool = False,
    ) -> tuple[MemoryRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1.")

        conditions: list[str] = []
        parameters: list[object] = []
        if not include_archived:
            conditions.append("archived = 0")
        if not include_expired:
            conditions.append("(expires_at IS NULL OR expires_at > ?)")
            parameters.append(self._utc_now())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM memories
                {where}
                ORDER BY importance DESC, updated_at DESC, id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()

        return tuple(self._row_to_memory(row) for row in rows)

    def delete(
        self,
        memory_id: str,
    ) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM memories
                WHERE id = ?
                """,
                (memory_id,),
            )

        if cursor.rowcount == 0:
            raise KeyError(f"Memory not found: {memory_id}")

    def archive(
        self,
        memory_id: str,
        *,
        archived: bool = True,
    ) -> MemoryRecord:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET archived = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(archived), self._utc_now(), memory_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Memory not found: {memory_id}")
        return self.get(memory_id)

    def update_policy(
        self,
        memory_id: str,
        *,
        importance: float | None = None,
        sensitivity: str | None = None,
        expires_at: str | None = None,
    ) -> MemoryRecord:
        memory = self.get(memory_id)
        selected_importance = memory.importance if importance is None else importance
        if not 0 <= selected_importance <= 1:
            raise ValueError("importance must be between 0 and 1.")
        selected_sensitivity = (
            memory.sensitivity
            if sensitivity is None
            else self._validate_label(sensitivity, "sensitivity")
        )
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE memories
                SET importance = ?, sensitivity = ?, expires_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    selected_importance,
                    selected_sensitivity,
                    expires_at,
                    self._utc_now(),
                    memory_id,
                ),
            )
        return self.get(memory_id)

    def prune_expired(self) -> int:
        now = self._utc_now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET archived = 1, updated_at = ?
                WHERE archived = 0 AND expires_at IS NOT NULL AND expires_at <= ?
                """,
                (now, now),
            )
        return int(cursor.rowcount)

    def search(
        self,
        query_embedding: Sequence[float],
        *,
        limit: int = 5,
        minimum_score: float = 0.0,
    ) -> tuple[MemorySearchResult, ...]:
        query_vector = self._validate_embedding(query_embedding)

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        if not -1 <= minimum_score <= 1:
            raise ValueError("minimum_score must be between -1 and 1.")

        scored: list[MemorySearchResult] = []

        for memory in self.list(limit=1_000_000):
            if len(memory.embedding) != len(query_vector):
                continue

            score = self._cosine_similarity(
                query_vector,
                memory.embedding,
            )

            if score >= minimum_score:
                scored.append(
                    MemorySearchResult(
                        memory=memory,
                        score=score,
                    )
                )

        scored.sort(
            key=lambda result: (
                result.score,
                result.memory.updated_at,
            ),
            reverse=True,
        )

        selected = tuple(scored[:limit])
        self.touch(tuple(result.memory.id for result in selected))
        return selected

    def touch(self, memory_ids: Sequence[str]) -> None:
        ids = tuple(dict.fromkeys(memory_ids))
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._connection() as connection:
            connection.execute(
                f"""
                UPDATE memories
                SET last_accessed_at = ?
                WHERE id IN ({placeholders})
                """,
                (self._utc_now(), *ids),
            )

    @staticmethod
    def _validate_embedding(
        embedding: Sequence[float],
    ) -> tuple[float, ...]:
        try:
            vector = tuple(float(value) for value in embedding)
        except (TypeError, ValueError) as exc:
            raise ValueError("Embedding must contain numbers.") from exc

        if not vector:
            raise ValueError("Embedding cannot be empty.")

        if any(not math.isfinite(value) for value in vector):
            raise ValueError("Embedding must contain finite numbers.")

        return vector

    @staticmethod
    def _cosine_similarity(
        left: Sequence[float],
        right: Sequence[float],
    ) -> float:
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))

        if left_norm == 0 or right_norm == 0:
            return 0.0

        return sum(
            left_value * right_value
            for left_value, right_value in zip(
                left,
                right,
                strict=True,
            )
        ) / (left_norm * right_norm)

    @staticmethod
    def _row_to_memory(
        row: sqlite3.Row,
    ) -> MemoryRecord:
        try:
            raw_embedding = json.loads(row["embedding_json"])
        except json.JSONDecodeError as exc:
            raise ValueError("Stored memory embedding is invalid JSON.") from exc

        if not isinstance(raw_embedding, list):
            raise TypeError("Stored memory embedding must be a list.")

        return MemoryRecord(
            id=str(row["id"]),
            content=str(row["content"]),
            embedding=SQLiteMemoryStore._validate_embedding(raw_embedding),
            source_session_id=(
                str(row["source_session_id"]) if row["source_session_id"] is not None else None
            ),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            memory_type=str(row["memory_type"]),
            importance=float(row["importance"]),
            sensitivity=str(row["sensitivity"]),
            expires_at=(str(row["expires_at"]) if row["expires_at"] is not None else None),
            archived=bool(row["archived"]),
            last_accessed_at=(
                str(row["last_accessed_at"]) if row["last_accessed_at"] is not None else None
            ),
        )

    @staticmethod
    def _validate_label(value: str, field: str) -> str:
        cleaned = value.strip().casefold()
        if not cleaned or len(cleaned) > 40:
            raise ValueError(f"{field} must contain 1 to 40 characters.")
        return cleaned

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds")
