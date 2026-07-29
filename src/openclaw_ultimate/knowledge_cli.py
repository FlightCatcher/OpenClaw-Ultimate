from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from openclaw_ultimate.config import load_settings
from openclaw_ultimate.rag import (
    SQLiteKnowledgeStore,
    build_knowledge_base,
)

knowledge_app = typer.Typer(
    no_args_is_help=True,
    help="索引和检索本地知识库",
)
console = Console()


@knowledge_app.command("index")
def knowledge_index(
    root: Annotated[
        Path | None,
        typer.Argument(
            help="可选的知识库根目录覆盖",
        ),
    ] = None,
) -> None:
    """增量索引本地知识库，未变化文件不会重复嵌入。"""

    settings = load_settings()

    if root is not None:
        settings.knowledge_root = root

    report = asyncio.run(build_knowledge_base(settings).index())
    console.print(
        "[green]知识库索引完成[/green] "
        f"发现 {report.discovered_files}，"
        f"更新 {report.indexed_files}，"
        f"未变化 {report.unchanged_files}，"
        f"跳过 {report.skipped_files}，"
        f"移除 {report.removed_files}，"
        f"新增块 {report.indexed_chunks}。"
    )

    if report.skipped_reasons:
        console.print("[yellow]跳过原因（前 10 项）：[/yellow]")

        for reason in report.skipped_reasons[:10]:
            console.print(f"- {reason}")


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(
        ...,
        help="要检索的问题或关键词",
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        "-n",
        min=1,
        max=20,
    ),
) -> None:
    """检索本地知识库并显示来源。"""

    settings = load_settings()
    hits = asyncio.run(
        build_knowledge_base(settings).search(
            query,
            limit=limit,
            minimum_score=(settings.knowledge_minimum_score),
        )
    )
    table = Table(title=f"知识检索：{query}")
    table.add_column("分数", justify="right")
    table.add_column("来源")
    table.add_column("内容")

    for hit in hits:
        table.add_row(
            f"{hit.score:.3f}",
            hit.chunk.citation,
            hit.chunk.content[:300].replace("\n", " "),
        )

    console.print(table)


@knowledge_app.command("status")
def knowledge_status() -> None:
    """显示知识库索引状态。"""

    settings = load_settings()
    stats = SQLiteKnowledgeStore(settings.knowledge_db_path).stats()
    console.print(
        {
            "root": str(settings.knowledge_root),
            "database": str(settings.knowledge_db_path),
            "documents": stats.document_count,
            "chunks": stats.chunk_count,
            "database_size_bytes": (stats.database_size_bytes),
            "last_indexed_at": stats.last_indexed_at,
        }
    )
