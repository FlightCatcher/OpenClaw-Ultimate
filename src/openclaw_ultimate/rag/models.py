from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    chunk_id: str
    source_path: str
    ordinal: int
    start_line: int
    content: str
    content_hash: str
    embedding: tuple[float, ...]

    @property
    def citation(self) -> str:
        return f"{self.source_path}#L{self.start_line}"


@dataclass(frozen=True, slots=True)
class KnowledgeSearchHit:
    chunk: KnowledgeChunk
    score: float
    vector_score: float
    lexical_score: float


@dataclass(frozen=True, slots=True)
class KnowledgeIndexReport:
    discovered_files: int
    indexed_files: int
    unchanged_files: int
    skipped_files: int
    removed_files: int
    indexed_chunks: int
    skipped_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeStats:
    document_count: int
    chunk_count: int
    database_size_bytes: int
    last_indexed_at: str | None
