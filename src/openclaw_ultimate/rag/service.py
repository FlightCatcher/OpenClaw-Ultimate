from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from openclaw_ultimate.models.embeddings import EmbeddingClient
from openclaw_ultimate.rag.chunking import MarkdownChunker
from openclaw_ultimate.rag.extractors import (
    DocumentExtractionError,
    DocumentExtractor,
)
from openclaw_ultimate.rag.models import (
    KnowledgeChunk,
    KnowledgeIndexReport,
    KnowledgeSearchHit,
)
from openclaw_ultimate.rag.store import SQLiteKnowledgeStore


class KnowledgeBase:
    """增量索引本地文档，并执行带引用的混合检索。"""

    def __init__(
        self,
        *,
        root: Path,
        store: SQLiteKnowledgeStore,
        embedding_model: EmbeddingClient,
        chunker: MarkdownChunker | None = None,
        max_file_bytes: int = 1_000_000,
        embedding_batch_size: int = 16,
        extractor: DocumentExtractor | None = None,
    ) -> None:
        if max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive.")

        if embedding_batch_size < 1:
            raise ValueError("embedding_batch_size must be positive.")

        self.root = root.resolve()
        self.store = store
        self.embedding_model = embedding_model
        self.chunker = chunker or MarkdownChunker()
        self.max_file_bytes = max_file_bytes
        self.embedding_batch_size = embedding_batch_size
        self.extractor = extractor or DocumentExtractor()

    async def index(
        self,
    ) -> KnowledgeIndexReport:
        if not self.root.is_dir():
            raise FileNotFoundError(f"Knowledge root does not exist: {self.root}")

        files = tuple(
            sorted(
                (
                    path
                    for path in self.root.rglob("*")
                    if path.is_file()
                    and path.suffix.casefold() in self.extractor.supported_suffixes
                ),
                key=lambda path: str(path).casefold(),
            )
        )
        indexed_files = 0
        unchanged_files = 0
        skipped_files = 0
        indexed_chunks = 0
        skipped_reasons: list[str] = []
        active_paths: set[str] = set()

        for path in files:
            relative = path.relative_to(self.root).as_posix()
            active_paths.add(relative)
            stat = path.stat()

            if stat.st_size > self.max_file_bytes:
                skipped_files += 1
                skipped_reasons.append(f"{relative}: exceeds {self.max_file_bytes} bytes")
                continue

            try:
                raw = path.read_bytes()
                text = self.extractor.extract(path, raw)
            except (OSError, DocumentExtractionError) as exc:
                skipped_files += 1
                skipped_reasons.append(f"{relative}: {type(exc).__name__}")
                continue

            digest = sha256(raw).hexdigest()

            if self.store.document_is_current(
                source_path=relative,
                sha256_hash=digest,
                modified_ns=stat.st_mtime_ns,
                size_bytes=stat.st_size,
            ):
                unchanged_files += 1
                continue

            text_chunks = self.chunker.split(text)
            embeddings = await self._embed_chunks(tuple(chunk.content for chunk in text_chunks))
            knowledge_chunks = tuple(
                KnowledgeChunk(
                    chunk_id=sha256(
                        (f"{relative}:{chunk.ordinal}:{chunk.content_hash}").encode()
                    ).hexdigest(),
                    source_path=relative,
                    ordinal=chunk.ordinal,
                    start_line=chunk.start_line,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                    embedding=embedding,
                )
                for chunk, embedding in zip(
                    text_chunks,
                    embeddings,
                    strict=True,
                )
            )
            self.store.replace_document(
                source_path=relative,
                sha256_hash=digest,
                modified_ns=stat.st_mtime_ns,
                size_bytes=stat.st_size,
                chunks=knowledge_chunks,
            )
            indexed_files += 1
            indexed_chunks += len(knowledge_chunks)

        removed_files = self.store.remove_missing_documents(active_paths)
        return KnowledgeIndexReport(
            discovered_files=len(files),
            indexed_files=indexed_files,
            unchanged_files=unchanged_files,
            skipped_files=skipped_files,
            removed_files=removed_files,
            indexed_chunks=indexed_chunks,
            skipped_reasons=tuple(skipped_reasons),
        )

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        minimum_score: float = 0.2,
    ) -> tuple[KnowledgeSearchHit, ...]:
        clean_query = query.strip()

        if not clean_query:
            return ()

        vectors = await self.embedding_model.embed((clean_query,))

        if len(vectors) != 1:
            raise RuntimeError("Embedding model returned an unexpected vector count.")

        return self.store.search(
            clean_query,
            query_embedding=vectors[0],
            limit=limit,
            minimum_score=minimum_score,
        )

    async def _embed_chunks(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        output: list[tuple[float, ...]] = []

        for start in range(
            0,
            len(texts),
            self.embedding_batch_size,
        ):
            batch = texts[start : start + self.embedding_batch_size]
            vectors = await self.embedding_model.embed(batch)

            if len(vectors) != len(batch):
                raise RuntimeError("Embedding model returned an unexpected vector count.")

            output.extend(vectors)

        return tuple(output)

    @staticmethod
    def format_context(
        hits: Sequence[KnowledgeSearchHit],
        *,
        max_characters: int = 5000,
    ) -> str:
        if max_characters < 1:
            raise ValueError("max_characters must be positive.")

        blocks: list[str] = []
        used = 0

        for hit in hits:
            block = f"[来源: {hit.chunk.citation}]\n{hit.chunk.content}"

            if used + len(block) > max_characters:
                break

            blocks.append(block)
            used += len(block)

        return "\n\n".join(blocks)
