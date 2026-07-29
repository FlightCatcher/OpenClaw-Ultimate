from __future__ import annotations

import asyncio
from collections.abc import Sequence

import typer
from rich.console import Console
from rich.table import Table

from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.runtime import AgentRuntime
from openclaw_ultimate.doctor import run_doctor
from openclaw_ultimate.sessions import (
    SQLiteSessionStore,
    SessionNotFoundError,
)


app = typer.Typer(
    no_args_is_help=True,
    help="OpenClaw-Ultimate 本地 AI Agent 平台",
)

session_app = typer.Typer(
    no_args_is_help=True,
    help="管理持久化聊天会话",
)

app.add_typer(
    session_app,
    name="session",
)

console = Console()


@app.command()
def doctor() -> None:
    """检查 OpenClaw-Ultimate 的运行环境。"""

    raise typer.Exit(
        code=0 if run_doctor(load_settings()) else 1
    )


@app.command()
def chat(
    message: str | None = typer.Argument(
        None,
        help="单次发送的消息；不填写则进入交互模式。",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="临时覆盖模型名称。",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="临时覆盖 Ollama 地址。",
    ),
    session_id: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="恢复指定的持久化会话。",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        "-t",
        help="新会话的标题。",
    ),
) -> None:
    """与本地 Agent 对话，并自动保存会话。"""

    settings = load_settings()
    updates: dict[str, object] = {}

    if model:
        updates["ollama_model"] = model

    if base_url:
        updates["ollama_base_url"] = base_url

    if updates:
        settings = settings.model_copy(
            update=updates
        )

    try:
        asyncio.run(
            _chat_async(
                settings=settings,
                initial_message=message,
                session_id=session_id,
                title=title,
            )
        )
    except SessionNotFoundError as exc:
        console.print(
            f"[red]会话不存在：{exc}[/red]"
        )
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]已退出。[/yellow]"
        )
    except Exception as exc:
        console.print(
            f"[red]运行失败：{exc}[/red]"
        )
        raise typer.Exit(code=1) from exc


async def _chat_async(
    *,
    settings: Settings,
    initial_message: str | None,
    session_id: str | None,
    title: str | None,
) -> None:
    agent = build_default_agent(settings)
    runtime = AgentRuntime()
    store = SQLiteSessionStore(
        settings.session_db_path
    )

    created_new_session = session_id is None

    if session_id is None:
        initial_title = (
            title.strip()
            if title and title.strip()
            else _title_from_message(
                initial_message
            )
        )

        session = store.create_session(
            initial_title or "新会话"
        )
    else:
        session = store.get_session(
            session_id
        )

    console.print(
        f"[green]{settings.app_name}[/green]"
        f" · 模型：[cyan]{settings.ollama_model}[/cyan]"
    )
    console.print(
        f"会话：[yellow]{session.title}[/yellow]"
        f" · ID：[dim]{session.id}[/dim]"
    )

    history = store.load_messages(
        session.id,
        limit=settings.history_message_limit,
    )

    if initial_message is not None:
        prompt = initial_message.strip()

        if not prompt:
            raise typer.BadParameter(
                "消息不能为空。"
            )

        result = await runtime.run(
            agent,
            prompt,
            history=history,
        )

        _append_runtime_delta(
            store=store,
            session_id=session.id,
            previous_history=history,
            runtime_messages=result.messages,
        )

        console.print(
            f"[magenta]AI>[/magenta] {result.output}"
        )
        console.print(
            f"[dim]会话已保存：{session.id}[/dim]"
        )
        return

    console.print(
        "[dim]输入 /exit 或 /quit 退出。[/dim]"
    )
    console.print(
        "[dim]输入 /session 查看当前会话 ID。[/dim]"
    )

    first_user_message = (
        created_new_session
        and session.title == "新会话"
    )

    while True:
        try:
            prompt = console.input(
                "[blue]你> [/blue]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print(
                "\n[yellow]已退出。[/yellow]"
            )
            break

        if prompt.lower() in {
            "/exit",
            "/quit",
        }:
            break

        if prompt.lower() == "/session":
            current = store.get_session(
                session.id
            )
            console.print(
                f"会话：[yellow]{current.title}[/yellow]"
            )
            console.print(
                f"ID：[dim]{current.id}[/dim]"
            )
            console.print(
                f"消息数：{current.message_count}"
            )
            continue

        if not prompt:
            continue

        try:
            history = store.load_messages(
                session.id,
                limit=settings.history_message_limit,
            )

            result = await runtime.run(
                agent,
                prompt,
                history=history,
            )

            _append_runtime_delta(
                store=store,
                session_id=session.id,
                previous_history=history,
                runtime_messages=result.messages,
            )

            if first_user_message:
                session = store.rename_session(
                    session.id,
                    _title_from_message(prompt)
                    or "新会话",
                )
                first_user_message = False

            console.print(
                f"[magenta]AI>[/magenta] {result.output}"
            )

        except Exception as exc:
            console.print(
                f"[red]错误：{exc}[/red]"
            )

    console.print(
        f"[dim]会话已保存：{session.id}[/dim]"
    )


def _append_runtime_delta(
    *,
    store: SQLiteSessionStore,
    session_id: str,
    previous_history: Sequence[Message],
    runtime_messages: Sequence[Message],
) -> None:
    """只保存本轮新增的消息，避免重复写入历史。"""

    history_count = len(previous_history)
    new_messages = tuple(
        runtime_messages[history_count:]
    )

    if not new_messages:
        return

    store.append_messages(
        session_id,
        new_messages,
    )


def _title_from_message(
    message: str | None,
) -> str | None:
    if message is None:
        return None

    compact = " ".join(
        message.strip().split()
    )

    if not compact:
        return None

    if len(compact) <= 36:
        return compact

    return compact[:36] + "…"


def _get_store() -> SQLiteSessionStore:
    settings = load_settings()

    return SQLiteSessionStore(
        settings.session_db_path
    )


@session_app.command("new")
def session_new(
    title: str = typer.Argument(
        "新会话",
        help="新会话标题。",
    ),
) -> None:
    """创建一个空白会话。"""

    store = _get_store()
    session = store.create_session(title)

    console.print(
        "[green]会话创建成功[/green]"
    )
    console.print(
        f"标题：[yellow]{session.title}[/yellow]"
    )
    console.print(
        f"ID：[cyan]{session.id}[/cyan]"
    )
    console.print()
    console.print(
        "使用以下命令恢复："
    )
    console.print(
        f"[bold]uv run ocu chat --session {session.id}[/bold]"
    )


@session_app.command("list")
def session_list(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        min=1,
        max=200,
        help="最多显示的会话数量。",
    ),
) -> None:
    """列出最近的会话。"""

    store = _get_store()
    sessions = store.list_sessions(
        limit=limit
    )

    if not sessions:
        console.print(
            "[yellow]还没有保存的会话。[/yellow]"
        )
        return

    table = Table(
        title="OpenClaw-Ultimate 会话"
    )
    table.add_column(
        "标题",
        overflow="fold",
    )
    table.add_column(
        "会话 ID",
        style="cyan",
    )
    table.add_column(
        "消息数",
        justify="right",
    )
    table.add_column(
        "更新时间",
    )

    for session in sessions:
        table.add_row(
            session.title,
            session.id,
            str(session.message_count),
            session.updated_at,
        )

    console.print(table)


@session_app.command("show")
def session_show(
    session_id: str = typer.Argument(
        ...,
        help="需要查看的会话 ID。",
    ),
) -> None:
    """查看会话信息和完整消息历史。"""

    store = _get_store()

    try:
        session = store.get_session(
            session_id
        )
        messages = store.load_messages(
            session_id
        )
    except SessionNotFoundError as exc:
        console.print(
            f"[red]会话不存在：{session_id}[/red]"
        )
        raise typer.Exit(code=1) from exc

    console.print(
        f"[bold]{session.title}[/bold]"
    )
    console.print(
        f"ID：[cyan]{session.id}[/cyan]"
    )
    console.print(
        f"创建时间：{session.created_at}"
    )
    console.print(
        f"更新时间：{session.updated_at}"
    )
    console.print(
        f"消息数量：{session.message_count}"
    )
    console.print()

    if not messages:
        console.print(
            "[dim]该会话还没有消息。[/dim]"
        )
        return

    role_names = {
        "system": "系统",
        "user": "用户",
        "assistant": "助手",
        "tool": "工具",
    }

    role_styles = {
        "system": "dim",
        "user": "blue",
        "assistant": "magenta",
        "tool": "yellow",
    }

    for index, message in enumerate(
        messages,
        start=1,
    ):
        role_name = role_names[
            message.role
        ]
        style = role_styles[
            message.role
        ]

        console.print(
            f"[{style}][{index}] "
            f"{role_name}[/{style}]"
        )

        if message.content:
            console.print(
                message.content
            )

        for tool_call in message.tool_calls:
            console.print(
                f"[yellow]调用工具："
                f"{tool_call.name}[/yellow]"
            )
            console.print(
                f"参数：{dict(tool_call.arguments)}"
            )

        if message.tool_call_id:
            console.print(
                f"[dim]调用 ID："
                f"{message.tool_call_id}[/dim]"
            )

        console.print()


@session_app.command("rename")
def session_rename(
    session_id: str = typer.Argument(
        ...,
        help="需要重命名的会话 ID。",
    ),
    title: str = typer.Argument(
        ...,
        help="新的会话标题。",
    ),
) -> None:
    """修改会话标题。"""

    store = _get_store()

    try:
        session = store.rename_session(
            session_id,
            title,
        )
    except SessionNotFoundError as exc:
        console.print(
            f"[red]会话不存在：{session_id}[/red]"
        )
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]已重命名为："
        f"{session.title}[/green]"
    )


@session_app.command("delete")
def session_delete(
    session_id: str = typer.Argument(
        ...,
        help="需要删除的会话 ID。",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="跳过删除确认。",
    ),
) -> None:
    """永久删除会话和全部消息。"""

    store = _get_store()

    try:
        session = store.get_session(
            session_id
        )
    except SessionNotFoundError as exc:
        console.print(
            f"[red]会话不存在：{session_id}[/red]"
        )
        raise typer.Exit(code=1) from exc

    if not yes:
        confirmed = typer.confirm(
            f"确定删除会话“{session.title}”吗？"
        )

        if not confirmed:
            console.print(
                "[yellow]已取消。[/yellow]"
            )
            raise typer.Abort()

    store.delete_session(
        session_id
    )

    console.print(
        f"[green]会话已删除："
        f"{session_id}[/green]"
    )


if __name__ == "__main__":
    app()
