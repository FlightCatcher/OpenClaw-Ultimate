from __future__ import annotations

from collections.abc import Sequence

from openclaw_ultimate.memory.store import (
    MemoryRecord,
    MemorySearchResult,
    SQLiteMemoryStore,
)
from openclaw_ultimate.models.embeddings import EmbeddingClient


class LongTermMemory:
    """协调嵌入模型与持久化向量记忆库。"""

    def __init__(
        self,
        *,
        store: SQLiteMemoryStore,
        embedding_model: EmbeddingClient,
    ) -> None:
        self.store = store
        self.embedding_model = embedding_model

    async def remember(
        self,
        content: str,
        *,
        source_session_id: str | None = None,
        memory_type: str = "fact",
        importance: float = 0.5,
        sensitivity: str = "normal",
        expires_at: str | None = None,
    ) -> MemoryRecord:
        clean_content = content.strip()

        if not clean_content:
            raise ValueError("Memory content cannot be empty.")

        vectors = await self.embedding_model.embed((clean_content,))

        if len(vectors) != 1:
            raise RuntimeError("Embedding model returned an unexpected vector count.")

        return self.store.add(
            content=clean_content,
            embedding=vectors[0],
            source_session_id=source_session_id,
            memory_type=memory_type,
            importance=importance,
            sensitivity=sensitivity,
            expires_at=expires_at,
        )

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        minimum_score: float = 0.0,
    ) -> tuple[MemorySearchResult, ...]:
        clean_query = query.strip()

        if not clean_query:
            return ()

        vectors = await self.embedding_model.embed((clean_query,))

        if len(vectors) != 1:
            raise RuntimeError("Embedding model returned an unexpected vector count.")

        return self.store.search(
            vectors[0],
            limit=limit,
            minimum_score=minimum_score,
        )

    @staticmethod
    def format_context(
        results: Sequence[MemorySearchResult],
        *,
        max_characters: int = 2000,
    ) -> str | None:
        if max_characters < 1:
            raise ValueError("max_characters must be at least 1.")

        lines: list[str] = []
        used_characters = 0

        for result in results:
            line = f"- {result.memory.content} (相关度 {result.score:.3f})"

            if used_characters + len(line) > max_characters:
                break

            lines.append(line)
            used_characters += len(line)

        if not lines:
            return None

        return (
            "以下是与当前请求相关的长期记忆。"
            "仅在确实相关时使用，不要把相关度数字告诉用户：\n" + "\n".join(lines)
        )
