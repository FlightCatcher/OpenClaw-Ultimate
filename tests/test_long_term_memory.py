from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

from openclaw_ultimate.memory import (
    LongTermMemory,
    SQLiteMemoryStore,
)


class FakeEmbeddingModel:
    async def embed(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        vectors = {
            "用户喜欢航空": (1.0, 0.0),
            "航空爱好": (0.9, 0.1),
            "用户喜欢烹饪": (0.0, 1.0),
            "飞机": (1.0, 0.0),
        }

        return tuple(vectors[text] for text in texts)


def create_memory(
    tmp_path: Path,
) -> LongTermMemory:
    return LongTermMemory(
        store=SQLiteMemoryStore(tmp_path / "memory.db"),
        embedding_model=FakeEmbeddingModel(),
    )


def test_remember_and_semantic_search(
    tmp_path: Path,
) -> None:
    async def run_test() -> None:
        memory = create_memory(tmp_path)

        aviation = await memory.remember(
            "用户喜欢航空",
            source_session_id="session-1",
        )
        await memory.remember("用户喜欢烹饪")

        results = await memory.search(
            "飞机",
            limit=1,
            minimum_score=0.5,
        )

        assert len(results) == 1
        assert results[0].memory.id == aviation.id
        assert results[0].memory.source_session_id == ("session-1")
        assert results[0].score == 1.0

    asyncio.run(run_test())


def test_memory_store_lifecycle(
    tmp_path: Path,
) -> None:
    store = SQLiteMemoryStore(tmp_path / "memory.db")
    saved = store.add(
        content="航空爱好",
        embedding=(0.9, 0.1),
    )

    assert store.get(saved.id) == saved
    assert store.list() == (saved,)

    store.delete(saved.id)
    assert store.list() == ()


def test_memory_context_formatting(
    tmp_path: Path,
) -> None:
    async def run_test() -> None:
        memory = create_memory(tmp_path)
        await memory.remember("用户喜欢航空")

        results = await memory.search("飞机")
        context = memory.format_context(results)

        assert context is not None
        assert "用户喜欢航空" in context
        assert "相关度" in context

    asyncio.run(run_test())
