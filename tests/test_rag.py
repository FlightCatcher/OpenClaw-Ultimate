from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

from openclaw_ultimate.rag import (
    KnowledgeBase,
    MarkdownChunker,
    SQLiteKnowledgeStore,
)


class KeywordEmbeddingModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def embed(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        batch = tuple(texts)
        self.calls.append(batch)
        return tuple((1.0, 0.0) if "apple" in text.casefold() else (0.0, 1.0) for text in batch)


def test_markdown_chunker_preserves_line_citations() -> None:
    chunker = MarkdownChunker(
        max_characters=200,
        overlap_characters=20,
    )

    chunks = chunker.split("# Heading\n\nFirst paragraph.\n\nSecond paragraph.")

    assert chunks
    assert chunks[0].start_line == 1
    assert chunks[0].ordinal == 0
    assert chunks[0].content_hash


def test_knowledge_base_indexes_incrementally_and_searches(
    tmp_path: Path,
) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "fruit.md").write_text(
        "# Fruit\n\nApples are red and useful in pies.",
        encoding="utf-8",
    )
    (root / "systems.md").write_text(
        "# Systems\n\nOpenClaw coordinates local tools.",
        encoding="utf-8",
    )
    embedding = KeywordEmbeddingModel()
    store = SQLiteKnowledgeStore(tmp_path / "knowledge.db")
    knowledge = KnowledgeBase(
        root=root,
        store=store,
        embedding_model=embedding,
        chunker=MarkdownChunker(
            max_characters=200,
            overlap_characters=20,
        ),
        embedding_batch_size=2,
    )

    first, second, hits = asyncio.run(
        _index_twice_and_search(
            knowledge,
            "apple recipes",
        )
    )

    assert first.indexed_files == 2
    assert first.indexed_chunks == 2
    assert second.indexed_files == 0
    assert second.unchanged_files == 2
    assert hits[0].chunk.source_path == "fruit.md"
    assert hits[0].chunk.citation == "fruit.md#L1"
    assert "Apples" in hits[0].chunk.content


def test_knowledge_base_prunes_deleted_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    document = root / "temporary.md"
    document.write_text("Temporary document.", encoding="utf-8")
    store = SQLiteKnowledgeStore(tmp_path / "knowledge.db")
    knowledge = KnowledgeBase(
        root=root,
        store=store,
        embedding_model=KeywordEmbeddingModel(),
    )

    asyncio.run(knowledge.index())
    document.unlink()
    report = asyncio.run(knowledge.index())

    assert report.removed_files == 1
    assert store.stats().document_count == 0


def test_knowledge_base_skips_large_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "large.md").write_text(
        "x" * 1000,
        encoding="utf-8",
    )
    knowledge = KnowledgeBase(
        root=root,
        store=SQLiteKnowledgeStore(tmp_path / "knowledge.db"),
        embedding_model=KeywordEmbeddingModel(),
        max_file_bytes=100,
    )

    report = asyncio.run(knowledge.index())

    assert report.skipped_files == 1
    assert report.indexed_files == 0


async def _index_twice_and_search(
    knowledge: KnowledgeBase,
    query: str,
):
    first = await knowledge.index()
    second = await knowledge.index()
    hits = await knowledge.search(
        query,
        limit=2,
        minimum_score=0,
    )
    return first, second, hits
