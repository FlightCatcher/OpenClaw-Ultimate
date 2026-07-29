from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class TextChunk:
    ordinal: int
    start_line: int
    content: str
    content_hash: str


class MarkdownChunker:
    """按段落切分文本，并为超长段落使用重叠窗口。"""

    def __init__(
        self,
        *,
        max_characters: int = 1200,
        overlap_characters: int = 200,
    ) -> None:
        if max_characters < 200:
            raise ValueError("max_characters must be at least 200.")

        if not 0 <= overlap_characters < max_characters:
            raise ValueError(
                "overlap_characters must be non-negative and smaller than max_characters."
            )

        self.max_characters = max_characters
        self.overlap_characters = overlap_characters

    def split(
        self,
        text: str,
    ) -> tuple[TextChunk, ...]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()

        if not normalized:
            return ()

        blocks = [block.strip() for block in re.split(r"\n{2,}", normalized) if block.strip()]
        chunks: list[tuple[int, str]] = []
        current: list[str] = []
        current_length = 0
        current_line = 1
        search_offset = 0

        for block in blocks:
            block_offset = normalized.find(block, search_offset)
            block_line = normalized.count("\n", 0, max(block_offset, 0)) + 1
            search_offset = max(block_offset, 0) + len(block)

            if len(block) > self.max_characters:
                if current:
                    chunks.append((current_line, "\n\n".join(current)))
                    current = []
                    current_length = 0

                chunks.extend(
                    self._split_oversized_block(
                        block,
                        start_line=block_line,
                    )
                )
                continue

            separator_length = 2 if current else 0

            if current and (current_length + separator_length + len(block) > self.max_characters):
                chunks.append((current_line, "\n\n".join(current)))
                current = []
                current_length = 0

            if not current:
                current_line = block_line

            current.append(block)
            current_length += separator_length + len(block)

        if current:
            chunks.append((current_line, "\n\n".join(current)))

        return tuple(
            TextChunk(
                ordinal=ordinal,
                start_line=start_line,
                content=content,
                content_hash=sha256(content.encode("utf-8")).hexdigest(),
            )
            for ordinal, (start_line, content) in enumerate(chunks)
        )

    def _split_oversized_block(
        self,
        block: str,
        *,
        start_line: int,
    ) -> list[tuple[int, str]]:
        step = self.max_characters - self.overlap_characters
        output: list[tuple[int, str]] = []

        for offset in range(0, len(block), step):
            content = block[offset : offset + self.max_characters].strip()

            if not content:
                continue

            line = start_line + block.count("\n", 0, offset)
            output.append((line, content))

            if offset + self.max_characters >= len(block):
                break

        return output
