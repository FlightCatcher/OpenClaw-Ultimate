from __future__ import annotations

import csv
import io
import json
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader


class DocumentExtractionError(ValueError):
    """A supported document could not be converted into local text."""


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style", "noscript"}:
            self._hidden_depth += 1
        elif tag.casefold() in {"p", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript"} and self._hidden_depth:
            self._hidden_depth -= 1
        elif tag.casefold() in {"p", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(part for part in self.parts if part.strip())


class DocumentExtractor:
    """Convert common local document formats to citation-friendly text."""

    text_suffixes = frozenset(
        {
            ".md",
            ".markdown",
            ".txt",
            ".rst",
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".csv",
            ".log",
        }
    )
    supported_suffixes = text_suffixes | {".html", ".htm", ".docx", ".pdf"}

    def extract(self, path: Path, raw: bytes) -> str:
        suffix = path.suffix.casefold()
        try:
            if suffix in self.text_suffixes:
                text = raw.decode("utf-8-sig")
                if suffix == ".json":
                    parsed = json.loads(text)
                    return json.dumps(parsed, ensure_ascii=False, indent=2)
                if suffix == ".csv":
                    return self._extract_csv(text)
                return text
            if suffix in {".html", ".htm"}:
                parser = _VisibleTextParser()
                parser.feed(raw.decode("utf-8-sig", errors="replace"))
                return parser.text()
            if suffix == ".docx":
                return self._extract_docx(raw)
            if suffix == ".pdf":
                return self._extract_pdf(raw)
        except (OSError, UnicodeError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            raise DocumentExtractionError(f"{path.name}: {type(exc).__name__}: {exc}") from exc
        raise DocumentExtractionError(f"Unsupported document format: {suffix}")

    @staticmethod
    def _extract_csv(text: str) -> str:
        rows = csv.reader(io.StringIO(text))
        return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)

    @staticmethod
    def _extract_docx(raw: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            document = archive.read("word/document.xml")
        root = ElementTree.fromstring(document)
        paragraphs: list[str] = []
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for paragraph in root.iter(f"{namespace}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
            if text:
                paragraphs.append(text)
        return "\n\n".join(paragraphs)

    @staticmethod
    def _extract_pdf(raw: bytes) -> str:
        reader = PdfReader(io.BytesIO(raw))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"[PDF page {index}]\n{text}")
        return "\n\n".join(pages)
