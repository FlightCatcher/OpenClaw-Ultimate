from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from openclaw_ultimate.rag.models import (
    KnowledgeChunk,
    KnowledgeSearchHit,
    KnowledgeStats,
)


class SQLiteKnowledgeStore:
    """保存文档指纹、文本块、向量和 FTS5 索引。"""

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
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    source_path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    modified_ns INTEGER NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    start_line INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    FOREIGN KEY(source_path)
                        REFERENCES knowledge_documents(source_path)
                        ON DELETE CASCADE,
                    UNIQUE(source_path, ordinal)
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source
                ON knowledge_chunks(source_path, ordinal);

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(
                    content,
                    chunk_id UNINDEXED,
                    source_path UNINDEXED,
                    tokenize='unicode61'
                );
                """
            )

    def document_is_current(
        self,
        *,
        source_path: str,
        sha256_hash: str,
        modified_ns: int,
        size_bytes: int,
    ) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT sha256, modified_ns, size_bytes
                FROM knowledge_documents
                WHERE source_path = ?
                """,
                (source_path,),
            ).fetchone()

        return bool(
            row
            and row["sha256"] == sha256_hash
            and row["modified_ns"] == modified_ns
            and row["size_bytes"] == size_bytes
        )

    def replace_document(
        self,
        *,
        source_path: str,
        sha256_hash: str,
        modified_ns: int,
        size_bytes: int,
        chunks: Sequence[KnowledgeChunk],
    ) -> None:
        now = self._utc_now()

        with self._connection() as connection:
            previous_ids = [
                str(row["chunk_id"])
                for row in connection.execute(
                    """
                    SELECT chunk_id
                    FROM knowledge_chunks
                    WHERE source_path = ?
                    """,
                    (source_path,),
                ).fetchall()
            ]

            if previous_ids:
                placeholders = ",".join("?" for _ in previous_ids)
                connection.execute(
                    f"DELETE FROM knowledge_fts WHERE chunk_id IN ({placeholders})",
                    previous_ids,
                )

            connection.execute(
                "DELETE FROM knowledge_chunks WHERE source_path = ?",
                (source_path,),
            )
            connection.execute(
                """
                INSERT INTO knowledge_documents (
                    source_path,
                    sha256,
                    modified_ns,
                    size_bytes,
                    indexed_at,
                    chunk_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    modified_ns = excluded.modified_ns,
                    size_bytes = excluded.size_bytes,
                    indexed_at = excluded.indexed_at,
                    chunk_count = excluded.chunk_count
                """,
                (
                    source_path,
                    sha256_hash,
                    modified_ns,
                    size_bytes,
                    now,
                    len(chunks),
                ),
            )

            for chunk in chunks:
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id,
                        source_path,
                        ordinal,
                        start_line,
                        content,
                        content_hash,
                        embedding_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.source_path,
                        chunk.ordinal,
                        chunk.start_line,
                        chunk.content,
                        chunk.content_hash,
                        json.dumps(chunk.embedding),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_fts (
                        content,
                        chunk_id,
                        source_path
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        chunk.content,
                        chunk.chunk_id,
                        chunk.source_path,
                    ),
                )

    def remove_missing_documents(
        self,
        active_paths: set[str],
    ) -> int:
        with self._connection() as connection:
            existing = {
                str(row["source_path"])
                for row in connection.execute(
                    "SELECT source_path FROM knowledge_documents"
                ).fetchall()
            }
            removed = existing - active_paths

            for source_path in removed:
                chunk_ids = [
                    str(row["chunk_id"])
                    for row in connection.execute(
                        """
                        SELECT chunk_id
                        FROM knowledge_chunks
                        WHERE source_path = ?
                        """,
                        (source_path,),
                    ).fetchall()
                ]

                for chunk_id in chunk_ids:
                    connection.execute(
                        "DELETE FROM knowledge_fts WHERE chunk_id = ?",
                        (chunk_id,),
                    )

                connection.execute(
                    "DELETE FROM knowledge_chunks WHERE source_path = ?",
                    (source_path,),
                )
                connection.execute(
                    "DELETE FROM knowledge_documents WHERE source_path = ?",
                    (source_path,),
                )

        return len(removed)

    def search(
        self,
        query: str,
        *,
        query_embedding: Sequence[float],
        limit: int = 5,
        minimum_score: float = 0.0,
    ) -> tuple[KnowledgeSearchHit, ...]:
        clean_query = query.strip()
        vector = self._validate_embedding(query_embedding)

        if not clean_query:
            return ()

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        lexical = self._lexical_scores(
            clean_query,
            candidate_limit=max(limit * 20, 100),
        )
        scored: list[KnowledgeSearchHit] = []

        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM knowledge_chunks").fetchall()

        for row in rows:
            chunk = self._row_to_chunk(row)

            if len(chunk.embedding) != len(vector):
                continue

            vector_score = max(
                0.0,
                self._cosine_similarity(
                    vector,
                    chunk.embedding,
                ),
            )
            lexical_score = lexical.get(chunk.chunk_id, 0.0)
            combined = (
                vector_score * 0.8 + lexical_score * 0.2 if lexical_score else vector_score * 0.8
            )

            if combined >= minimum_score:
                scored.append(
                    KnowledgeSearchHit(
                        chunk=chunk,
                        score=combined,
                        vector_score=vector_score,
                        lexical_score=lexical_score,
                    )
                )

        scored.sort(
            key=lambda item: (
                item.score,
                item.chunk.source_path,
                -item.chunk.ordinal,
            ),
            reverse=True,
        )
        return tuple(scored[:limit])

    def stats(self) -> KnowledgeStats:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS document_count,
                    COALESCE(SUM(chunk_count), 0) AS chunk_count,
                    MAX(indexed_at) AS last_indexed_at
                FROM knowledge_documents
                """
            ).fetchone()

        return KnowledgeStats(
            document_count=int(row["document_count"]) if row else 0,
            chunk_count=int(row["chunk_count"]) if row else 0,
            database_size_bytes=(self.db_path.stat().st_size if self.db_path.exists() else 0),
            last_indexed_at=(
                str(row["last_indexed_at"]) if row and row["last_indexed_at"] else None
            ),
        )

    def _lexical_scores(
        self,
        query: str,
        *,
        candidate_limit: int,
    ) -> dict[str, float]:
        terms = [term.replace('"', '""') for term in query.split() if term.strip()]

        if not terms:
            return {}

        expression = " OR ".join(f'"{term}"' for term in terms)

        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT chunk_id, bm25(knowledge_fts) AS rank
                    FROM knowledge_fts
                    WHERE knowledge_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (
                        expression,
                        candidate_limit,
                    ),
                ).fetchall()
        except sqlite3.OperationalError:
            return {}

        if not rows:
            return {}

        return {
            str(row["chunk_id"]): 1.0 - index / max(len(rows), 1) for index, row in enumerate(rows)
        }

    @staticmethod
    def _row_to_chunk(
        row: sqlite3.Row,
    ) -> KnowledgeChunk:
        raw = json.loads(row["embedding_json"])

        if not isinstance(raw, list):
            raise TypeError("Stored knowledge embedding must be a list.")

        return KnowledgeChunk(
            chunk_id=str(row["chunk_id"]),
            source_path=str(row["source_path"]),
            ordinal=int(row["ordinal"]),
            start_line=int(row["start_line"]),
            content=str(row["content"]),
            content_hash=str(row["content_hash"]),
            embedding=SQLiteKnowledgeStore._validate_embedding(raw),
        )

    @staticmethod
    def _validate_embedding(
        embedding: Sequence[float],
    ) -> tuple[float, ...]:
        vector = tuple(float(value) for value in embedding)

        if not vector or any(not math.isfinite(value) for value in vector):
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
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds")
