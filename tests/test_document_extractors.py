from __future__ import annotations

import io
import zipfile
from pathlib import Path

from pypdf import PdfWriter

from openclaw_ultimate.rag import DocumentExtractor


def test_extracts_html_and_csv() -> None:
    extractor = DocumentExtractor()

    html = extractor.extract(
        Path("page.html"),
        b"<html><style>hidden</style><body><h1>Title</h1><p>Body</p></body></html>",
    )
    csv = extractor.extract(Path("data.csv"), b"name,value\nvela,1\n")

    assert "Title" in html
    assert "hidden" not in html
    assert "name | value" in csv


def test_extracts_docx_text() -> None:
    document_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>VELA document</w:t></w:r></w:p></w:body>
    </w:document>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    text = DocumentExtractor().extract(Path("example.docx"), buffer.getvalue())

    assert text == "VELA document"


def test_extracts_pdf_without_text_as_empty() -> None:
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)

    text = DocumentExtractor().extract(Path("blank.pdf"), buffer.getvalue())

    assert text == ""
