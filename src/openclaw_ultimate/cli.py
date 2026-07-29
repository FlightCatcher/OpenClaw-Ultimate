from __future__ import annotations

import asyncio
import threading
import webbrowser
from collections.abc import Sequence

import typer
from rich.console import Console
from rich.table import Table

from openclaw_ultimate.api import LocalApiServer
from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.context import (
    ContextSelection,
    ContextWindowBuilder,
)
from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.runtime import (
    Agent,
    AgentRuntime,
)
from openclaw_ultimate.diagnostics import (
    collect_diagnostics,
)
from openclaw_ultimate.doctor import run_doctor
from openclaw_ultimate.knowledge_cli import knowledge_app
from openclaw_ultimate.memory import (
    ConversationSummarizer,
    LongTermMemory,
    RollingSummaryContextManager,
    SQLiteMemoryStore,
)
from openclaw_ultimate.model_cli import model_app
from openclaw_ultimate.models import (
    OpenAICompatibleEmbeddingModel,
)
from openclaw_ultimate.openclaw_cli import openclaw_app
from openclaw_ultimate.planner import (
    ErrorContext,
    PlanExecutionError,
    PlanExecutor,
    PlanNotFoundError,
    PlanRevision,
    ReflectionEngine,
    ReflectionResult,
    ReplanningEngine,
    RetryAttempt,
    SQLitePlanStore,
    StepStatus,
    StructuredPlanner,
    TaskGraph,
    TaskPlan,
)
from openclaw_ultimate.planner.models import PlanStep
from openclaw_ultimate.sessions import (
    SessionNotFoundError,
    SQLiteSessionStore,
)

app = typer.Typer(
    no_args_is_help=True,
    help="VELA（兼容 OpenClaw-Ultimate）本地 AI Agent 操作系统",
)

session_app = typer.Typer(
    no_args_is_help=True,
    help="管理持久化聊天会话",
)

memory_app = typer.Typer(
    no_args_is_help=True,
    help="管理跨会话长期记忆",
)
plan_app = typer.Typer(
    no_args_is_help=True,
    help="创建和管理结构化任务计划",
)

app.add_typer(
    session_app,
    name="session",
)
app.add_typer(
    memory_app,
    name="memory",
)
app.add_typer(
    plan_app,
    name="plan",
)
app.add_typer(
    openclaw_app,
    name="openclaw",
)
app.add_typer(
    model_app,
    name="model",
)
app.add_typer(
    knowledge_app,
    name="knowledge",
)

console = Console()


@app.command()
def doctor() -> None:
    """检查 OpenClaw-Ultimate 的运行环境。"""

    raise typer.Exit(code=0 if run_doctor(load_settings()) else 1)


@app.command("status")
def unified_status() -> None:
    """显示 VELA、OpenClaw、模型、知识库和工具后端状态。"""

    report = asyncio.run(collect_diagnostics(load_settings()))
    table = Table(title=f"VELA 系统状态：{report.state.value}")
    table.add_column("组件")
    table.add_column("状态")
    table.add_column("详情")
    table.add_column("必需")

    for component in report.components:
        table.add_row(
            component.name,
            component.state.value,
            component.detail,
            "是" if component.required else "否",
        )

    console.print(table)
    raise typer.Exit(code=0 if report.ready else 1)


@app.command()
def serve(
    host: str | None = typer.Option(
        None,
        "--host",
        help="监听地址；默认只允许 127.0.0.1",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        min=0,
        max=65535,
        help="监听端口",
    ),
) -> None:
    """启动 VELA 本地 API 和控制台。"""

    settings = load_settings()
    updates: dict[str, object] = {}

    if host is not None:
        updates["api_host"] = host

    if port is not None:
        updates["api_port"] = port

    if updates:
        settings = settings.model_copy(update=updates)

    server = LocalApiServer(settings)
    address = server.address
    console.print(f"[green]VELA 已启动：[/green]http://{address[0]}:{address[1]}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]VELA 已停止。[/yellow]")
    finally:
        server.shutdown()


@app.command()
def ui(
    port: int = typer.Option(
        8765,
        "--port",
        min=1,
        max=65535,
        help="本地控制台端口",
    ),
) -> None:
    """启动并打开 VELA 本地控制台。"""

    settings = load_settings().model_copy(
        update={
            "api_host": "127.0.0.1",
            "api_port": port,
        }
    )
    server = LocalApiServer(settings)
    url = f"http://127.0.0.1:{server.address[1]}/"
    threading.Timer(
        0.4,
        lambda: webbrowser.open(url),
    ).start()
    console.print(f"[green]VELA Command Deck：[/green]{url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]VELA 已停止。[/yellow]")
    finally:
        server.shutdown()


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
        settings = settings.model_copy(update=updates)

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
        console.print(f"[red]会话不存在：{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        console.print("\n[yellow]已退出。[/yellow]")
    except Exception as exc:
        console.print(f"[red]运行失败：{exc}[/red]")
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
    store = SQLiteSessionStore(settings.session_db_path)
    long_term_memory = _build_long_term_memory(settings) if settings.memory_enabled else None

    created_new_session = session_id is None

    if session_id is None:
        initial_title = (
            title.strip() if title and title.strip() else _title_from_message(initial_message)
        )

        session = store.create_session(initial_title or "新会话")
    else:
        session = store.get_session(session_id)

    if long_term_memory is not None:
        _register_memory_tool(
            agent=agent,
            memory=long_term_memory,
            session_id=session.id,
        )

    console.print(
        f"[green]{settings.app_name}[/green] · 模型：[cyan]{settings.ollama_model}[/cyan]"
    )
    console.print(f"会话：[yellow]{session.title}[/yellow] · ID：[dim]{session.id}[/dim]")

    if initial_message is not None:
        prompt = initial_message.strip()

        if not prompt:
            raise typer.BadParameter("消息不能为空。")

        context_selection = await _load_context_history(
            agent=agent,
            store=store,
            session_id=session.id,
            settings=settings,
            query=prompt,
            long_term_memory=long_term_memory,
        )
        history = context_selection.messages
        _print_context_selection(context_selection)

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

        console.print(f"[magenta]AI>[/magenta] {result.output}")
        console.print(f"[dim]会话已保存：{session.id}[/dim]")
        return

    console.print("[dim]输入 /exit 或 /quit 退出。[/dim]")
    console.print("[dim]输入 /session 查看当前会话 ID。[/dim]")

    first_user_message = created_new_session and session.title == "新会话"

    while True:
        try:
            prompt = console.input("[blue]你> [/blue]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]已退出。[/yellow]")
            break

        if prompt.lower() in {
            "/exit",
            "/quit",
        }:
            break

        if prompt.lower() == "/session":
            current = store.get_session(session.id)
            console.print(f"会话：[yellow]{current.title}[/yellow]")
            console.print(f"ID：[dim]{current.id}[/dim]")
            console.print(f"消息数：{current.message_count}")
            continue

        if not prompt:
            continue

        try:
            context_selection = await _load_context_history(
                agent=agent,
                store=store,
                session_id=session.id,
                settings=settings,
                query=prompt,
                long_term_memory=long_term_memory,
            )
            history = context_selection.messages
            _print_context_selection(context_selection)

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
                    _title_from_message(prompt) or "新会话",
                )
                first_user_message = False

            console.print(f"[magenta]AI>[/magenta] {result.output}")

        except Exception as exc:  # noqa: BLE001 - CLI must render unexpected runtime errors
            console.print(f"[red]错误：{exc}[/red]")

    console.print(f"[dim]会话已保存：{session.id}[/dim]")


async def _load_context_history(
    *,
    agent: Agent,
    store: SQLiteSessionStore,
    session_id: str,
    settings: Settings,
    query: str,
    long_term_memory: LongTermMemory | None,
) -> ContextSelection:
    """读取历史、生成滚动摘要并构造模型上下文。"""

    builder = ContextWindowBuilder(
        max_tokens=settings.context_token_budget,
        response_reserve_tokens=(settings.context_response_reserve),
    )

    manager = RollingSummaryContextManager(
        builder=builder,
        summarizer=ConversationSummarizer(agent.model),
    )

    memory_context = await _recall_memory_context(
        memory=long_term_memory,
        query=query,
        settings=settings,
    )

    return await manager.build(
        store=store,
        session_id=session_id,
        system_prompt=agent.system_prompt,
        additional_context=memory_context,
    )


def _build_long_term_memory(
    settings: Settings,
) -> LongTermMemory:
    embedding_model = OpenAICompatibleEmbeddingModel(
        model=settings.embedding_model,
        base_url=settings.openai_base_url,
        api_key=settings.ollama_api_key,
        timeout=settings.model_timeout,
    )

    return LongTermMemory(
        store=SQLiteMemoryStore(settings.memory_db_path),
        embedding_model=embedding_model,
    )


def _register_memory_tool(
    *,
    agent: Agent,
    memory: LongTermMemory,
    session_id: str,
) -> None:
    async def remember_memory(
        content: str,
    ) -> dict[str, str]:
        record = await memory.remember(
            content,
            source_session_id=session_id,
        )

        return {
            "id": record.id,
            "content": record.content,
        }

    agent.system_prompt += (
        "\n当用户明确要求你长期记住身份、偏好、目标或重要事实时，"
        "必须调用 remember_memory 工具保存；不要保存密码、密钥等敏感信息。"
    )
    agent.tools.add(
        name="remember_memory",
        description=(
            "把用户明确要求长期记住的重要事实保存到跨会话记忆。不要保存密码、令牌、密钥等敏感数据。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": ("简洁、独立、可在未来理解的事实陈述"),
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
        handler=remember_memory,
    )


async def _recall_memory_context(
    *,
    memory: LongTermMemory | None,
    query: str,
    settings: Settings,
) -> str | None:
    if memory is None:
        return None

    results = await memory.search(
        query,
        limit=settings.memory_recall_limit,
        minimum_score=(settings.memory_similarity_threshold),
    )

    return memory.format_context(
        results,
        max_characters=(settings.memory_max_context_characters),
    )


def _print_context_selection(
    selection: ContextSelection,
) -> None:
    if selection.dropped_messages <= 0:
        return

    console.print(
        "[dim]上下文预算已启用："
        f"省略 {selection.dropped_messages} 条旧消息，"
        f"预计使用 {selection.estimated_tokens}/"
        f"{selection.max_input_tokens} 输入 Token。"
        "[/dim]"
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
    new_messages = tuple(runtime_messages[history_count:])

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

    compact = " ".join(message.strip().split())

    if not compact:
        return None

    if len(compact) <= 36:
        return compact

    return compact[:36] + "…"


def _get_store() -> SQLiteSessionStore:
    settings = load_settings()

    return SQLiteSessionStore(settings.session_db_path)


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

    console.print("[green]会话创建成功[/green]")
    console.print(f"标题：[yellow]{session.title}[/yellow]")
    console.print(f"ID：[cyan]{session.id}[/cyan]")
    console.print()
    console.print("使用以下命令恢复：")
    console.print(f"[bold]uv run ocu chat --session {session.id}[/bold]")


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
    sessions = store.list_sessions(limit=limit)

    if not sessions:
        console.print("[yellow]还没有保存的会话。[/yellow]")
        return

    table = Table(title="OpenClaw-Ultimate 会话")
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
        session = store.get_session(session_id)
        messages = store.load_messages(session_id)
    except SessionNotFoundError as exc:
        console.print(f"[red]会话不存在：{session_id}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold]{session.title}[/bold]")
    console.print(f"ID：[cyan]{session.id}[/cyan]")
    console.print(f"创建时间：{session.created_at}")
    console.print(f"更新时间：{session.updated_at}")
    console.print(f"消息数量：{session.message_count}")
    console.print()

    if not messages:
        console.print("[dim]该会话还没有消息。[/dim]")
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
        role_name = role_names[message.role]
        style = role_styles[message.role]

        console.print(f"[{style}][{index}] {role_name}[/{style}]")

        if message.content:
            console.print(message.content)

        for tool_call in message.tool_calls:
            console.print(f"[yellow]调用工具：{tool_call.name}[/yellow]")
            console.print(f"参数：{dict(tool_call.arguments)}")

        if message.tool_call_id:
            console.print(f"[dim]调用 ID：{message.tool_call_id}[/dim]")

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
        console.print(f"[red]会话不存在：{session_id}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]已重命名为：{session.title}[/green]")


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
        session = store.get_session(session_id)
    except SessionNotFoundError as exc:
        console.print(f"[red]会话不存在：{session_id}[/red]")
        raise typer.Exit(code=1) from exc

    if not yes:
        confirmed = typer.confirm(f"确定删除会话“{session.title}”吗？")

        if not confirmed:
            console.print("[yellow]已取消。[/yellow]")
            raise typer.Abort()

    store.delete_session(session_id)

    console.print(f"[green]会话已删除：{session_id}[/green]")


@memory_app.command("remember")
def memory_remember(
    content: str = typer.Argument(
        ...,
        help="需要长期记住的事实。",
    ),
) -> None:
    """保存一条跨会话长期记忆。"""

    async def run() -> None:
        memory = _build_long_term_memory(load_settings())
        record = await memory.remember(content)

        console.print("[green]长期记忆已保存[/green]")
        console.print(f"ID：[cyan]{record.id}[/cyan]")
        console.print(record.content)

    asyncio.run(run())


@memory_app.command("search")
def memory_search(
    query: str = typer.Argument(
        ...,
        help="用于检索长期记忆的文本。",
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        "-n",
        min=1,
        max=50,
        help="最多返回的记忆数量。",
    ),
) -> None:
    """按语义相似度搜索长期记忆。"""

    async def run() -> None:
        settings = load_settings()
        memory = _build_long_term_memory(settings)
        results = await memory.search(
            query,
            limit=limit,
            minimum_score=(settings.memory_similarity_threshold),
        )

        if not results:
            console.print("[yellow]没有找到相关长期记忆。[/yellow]")
            return

        table = Table(title="长期记忆搜索结果")
        table.add_column(
            "相关度",
            justify="right",
        )
        table.add_column(
            "记忆 ID",
            style="cyan",
        )
        table.add_column(
            "内容",
            overflow="fold",
        )

        for result in results:
            table.add_row(
                f"{result.score:.3f}",
                result.memory.id,
                result.memory.content,
            )

        console.print(table)

    asyncio.run(run())


@memory_app.command("list")
def memory_list(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        min=1,
        max=200,
        help="最多显示的长期记忆数量。",
    ),
) -> None:
    """列出最近保存的长期记忆。"""

    settings = load_settings()
    store = SQLiteMemoryStore(settings.memory_db_path)
    memories = store.list(limit=limit)

    if not memories:
        console.print("[yellow]还没有长期记忆。[/yellow]")
        return

    table = Table(title="长期记忆")
    table.add_column(
        "记忆 ID",
        style="cyan",
    )
    table.add_column(
        "内容",
        overflow="fold",
    )
    table.add_column("来源会话")
    table.add_column("更新时间")

    for memory in memories:
        table.add_row(
            memory.id,
            memory.content,
            memory.source_session_id or "-",
            memory.updated_at,
        )

    console.print(table)


@memory_app.command("delete")
def memory_delete(
    memory_id: str = typer.Argument(
        ...,
        help="需要删除的长期记忆 ID。",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="跳过删除确认。",
    ),
) -> None:
    """永久删除一条长期记忆。"""

    settings = load_settings()
    store = SQLiteMemoryStore(settings.memory_db_path)

    try:
        memory = store.get(memory_id)
    except KeyError as exc:
        console.print(f"[red]长期记忆不存在：{memory_id}[/red]")
        raise typer.Exit(code=1) from exc

    if not yes and not typer.confirm(f"确定删除“{memory.content}”吗？"):
        console.print("[yellow]已取消。[/yellow]")
        raise typer.Abort()

    store.delete(memory_id)
    console.print(f"[green]长期记忆已删除：{memory_id}[/green]")


def _get_plan_store(
    settings: Settings | None = None,
) -> SQLitePlanStore:
    current_settings = settings or load_settings()

    return SQLitePlanStore(current_settings.planner_db_path)


@plan_app.command("create")
def plan_create(
    goal: str = typer.Argument(
        ...,
        help="需要拆解的任务目标。",
    ),
) -> None:
    """使用当前模型生成并保存 DAG 任务计划。"""

    async def run() -> None:
        settings = load_settings()
        agent = build_default_agent(settings)
        planner = StructuredPlanner(
            agent.model,
            max_steps=settings.planner_max_steps,
        )
        plan = await planner.create_plan(
            goal,
            tools=agent.tools.definitions(),
        )
        _get_plan_store(settings).save(plan)
        _print_plan(plan)
        console.print(f"[green]计划已保存：{plan.id}[/green]")

    asyncio.run(run())


@plan_app.command("list")
def plan_list(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        min=1,
        max=200,
    ),
) -> None:
    """列出最近的任务计划。"""

    plans = _get_plan_store().list(limit=limit)

    if not plans:
        console.print("[yellow]还没有任务计划。[/yellow]")
        return

    table = Table(title="任务计划")
    table.add_column("计划 ID", style="cyan")
    table.add_column("状态")
    table.add_column("步骤", justify="right")
    table.add_column("目标", overflow="fold")

    for plan in plans:
        table.add_row(
            plan.id,
            plan.status.value,
            str(len(plan.steps)),
            plan.goal,
        )

    console.print(table)


@plan_app.command("show")
def plan_show(
    plan_id: str = typer.Argument(...),
) -> None:
    """显示任务计划及依赖关系。"""

    try:
        plan = _get_plan_store().get(plan_id)
    except PlanNotFoundError as exc:
        console.print(f"[red]计划不存在：{plan_id}[/red]")
        raise typer.Exit(code=1) from exc

    _print_plan(plan)
    store = _get_plan_store()
    _print_reflections(store.list_reflections(plan_id=plan.id))
    _print_retry_attempts(
        store.list_retry_attempts_for_plan(plan_id=plan.id),
    )
    _print_revisions(store.list_revisions(plan_id=plan.id))


@plan_app.command("reflect")
def plan_reflect(
    plan_id: str = typer.Argument(...),
) -> None:
    """分析计划中的失败步骤并持久化 Reflection，不执行任何恢复动作。"""

    store = _get_plan_store()
    try:
        plan = store.get(plan_id)
    except PlanNotFoundError as exc:
        console.print(f"[red]计划不存在：{plan_id}[/red]")
        raise typer.Exit(code=1) from exc

    failed_steps = tuple(step for step in plan.steps if step.status == StepStatus.FAILED)
    if not failed_steps:
        console.print("[yellow]计划中没有失败步骤，无需 Reflection。[/yellow]")
        return

    engine = ReflectionEngine()
    reflections = []
    for step in failed_steps:
        reflection = engine.reflect(
            plan=plan,
            failed_step=step,
            error_context=ErrorContext(
                error_type=(step.error or "UnknownError").split(":", 1)[0],
                error_message=step.error or "Unknown error",
                tool_name=step.tool_hint,
                input_summary=step.description,
            ),
        )
        store.save_reflection(reflection)
        reflections.append(reflection)

    _print_reflections(tuple(reflections))


@plan_app.command("revise")
def plan_revise(
    plan_id: str = typer.Argument(...),
    step_id: str | None = typer.Option(None, "--step-id"),
    description: str | None = typer.Option(None, "--description"),
    tool: str | None = typer.Option(None, "--tool"),
) -> None:
    """根据最近 Reflection 生成候选修订，不修改原计划。"""

    store = _get_plan_store()
    try:
        plan = store.get(plan_id)
    except PlanNotFoundError as exc:
        console.print(f"[red]计划不存在：{plan_id}[/red]")
        raise typer.Exit(code=1) from exc

    reflections = store.list_reflections(plan_id=plan.id)
    if not reflections:
        console.print("[yellow]没有 Reflection，无法生成候选修订。[/yellow]")
        return

    latest_by_step = {reflection.step_id: reflection for reflection in reflections}
    engine = ReplanningEngine()
    existing = store.list_revisions(plan_id=plan.id)
    next_number = len(existing) + 1
    revisions = []

    for reflection in latest_by_step.values():
        proposed_step = None
        if step_id == reflection.step_id and description:
            original_step = next(step for step in plan.steps if step.id == reflection.step_id)
            proposed_step = PlanStep(
                id=original_step.id,
                title=original_step.title,
                description=description,
                dependencies=original_step.dependencies,
                tool_hint=tool if tool is not None else original_step.tool_hint,
            )
        try:
            revision = engine.propose(
                plan=plan,
                reflection=reflection,
                revision_number=next_number,
                proposed_step=proposed_step,
            )
        except ValueError:
            continue
        store.save_revision(revision)
        revisions.append(revision)
        next_number += 1

    if not revisions:
        console.print("[yellow]最近的 Reflection 不需要候选修订。[/yellow]")
        return

    _print_revisions(tuple(revisions))


@plan_app.command("apply")
def plan_apply(
    revision_id: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """批准候选修订并创建新的计划版本，不覆盖父计划。"""

    store = _get_plan_store()
    try:
        revision = store.get_revision(revision_id)
        parent = store.get(revision.parent_plan_id)
    except PlanNotFoundError as exc:
        console.print(f"[red]修订或父计划不存在：{revision_id}[/red]")
        raise typer.Exit(code=1) from exc

    if revision.proposed_step is None:
        console.print("[red]该修订没有明确的候选步骤，不能应用。[/red]")
        raise typer.Exit(code=1)

    if not yes and not typer.confirm(
        f"确认生成父计划 {parent.id} 的新版本吗？修订步骤：{revision.step_id}"
    ):
        raise typer.Abort()

    child = ReplanningEngine().apply(plan=parent, revision=revision)
    store.save(child)
    store.update_revision_applied(
        revision_id=revision.revision_id,
        child_plan_id=child.id,
    )
    console.print(f"[green]新计划版本已创建：{child.id}[/green]")


@plan_app.command("delete")
def plan_delete(
    plan_id: str = typer.Argument(...),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
    ),
) -> None:
    """删除一个任务计划。"""

    store = _get_plan_store()

    try:
        plan = store.get(plan_id)
    except PlanNotFoundError as exc:
        console.print(f"[red]计划不存在：{plan_id}[/red]")
        raise typer.Exit(code=1) from exc

    if not yes and not typer.confirm(f"确定删除计划“{plan.goal}”吗？"):
        raise typer.Abort()

    store.delete(plan_id)
    console.print(f"[green]计划已删除：{plan_id}[/green]")


@plan_app.command("run")
def plan_run(
    plan_id: str = typer.Argument(...),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="跳过执行确认。",
    ),
) -> None:
    """按照 DAG 依赖顺序执行计划。"""

    async def run() -> None:
        settings = load_settings()
        store = _get_plan_store(settings)

        try:
            plan = store.get(plan_id)
        except PlanNotFoundError as exc:
            console.print(f"[red]计划不存在：{plan_id}[/red]")
            raise typer.Exit(code=1) from exc

        if not yes and not typer.confirm(f"确定执行计划“{plan.goal}”吗？"):
            raise typer.Abort()

        agent = build_default_agent(settings)
        executor = PlanExecutor()

        try:
            result = await executor.execute(
                plan=plan,
                agent=agent,
                store=store,
            )
        except PlanExecutionError as exc:
            console.print(f"[red]计划无法执行：{exc}[/red]")
            raise typer.Exit(code=1) from exc

        _print_plan(result.plan)

        if result.failed_step_id:
            console.print(f"[red]执行失败：{result.failed_step_id}[/red]")
            raise typer.Exit(code=1)

        console.print("[green]计划执行完成。[/green]")

    asyncio.run(run())


def _print_plan(plan: TaskPlan) -> None:
    graph = TaskGraph(plan.steps)
    table = Table(title=f"任务计划：{plan.goal}")
    table.add_column("步骤", style="cyan")
    table.add_column("状态")
    table.add_column("依赖")
    table.add_column("工具")
    table.add_column("说明", overflow="fold")

    for step in graph.topological_order():
        table.add_row(
            step.id,
            step.status.value,
            ", ".join(step.dependencies) or "-",
            step.tool_hint or "-",
            f"{step.title}\n{step.description}",
        )

    console.print(table)

    for step in graph.topological_order():
        if step.result:
            console.print(f"[green]{step.id} 结果：[/green]{step.result}")

        if step.error:
            console.print(f"[red]{step.id} 错误：[/red]{step.error}")


def _print_reflections(reflections: Sequence[ReflectionResult]) -> None:
    if not reflections:
        return

    table = Table(title="Reflection")
    table.add_column("步骤", style="cyan")
    table.add_column("失败分类")
    table.add_column("可重试")
    table.add_column("建议")
    table.add_column("根因", overflow="fold")

    for reflection in reflections:
        table.add_row(
            reflection.step_id,
            reflection.failure_type.value,
            "是" if reflection.retryable else "否",
            reflection.suggested_action.value,
            reflection.root_cause,
        )

    console.print(table)


def _print_retry_attempts(attempts: Sequence[RetryAttempt]) -> None:
    if not attempts:
        return

    table = Table(title="自动重试记录")
    table.add_column("步骤", style="cyan")
    table.add_column("次数", justify="right")
    table.add_column("已安排")
    table.add_column("错误")

    for attempt in attempts:
        table.add_row(
            attempt.step_id,
            str(attempt.attempt_number),
            "是" if attempt.scheduled else "否",
            f"{attempt.error_type}: {attempt.error_message}",
        )

    console.print(table)


def _print_revisions(revisions: Sequence[PlanRevision]) -> None:
    if not revisions:
        return

    table = Table(title="候选计划修订")
    table.add_column("修订", style="cyan")
    table.add_column("步骤")
    table.add_column("状态")
    table.add_column("建议变更", overflow="fold")

    for revision in revisions:
        table.add_row(
            str(revision.revision_number),
            revision.step_id,
            revision.status.value,
            "；".join(revision.suggested_changes),
        )

    console.print(table)


if __name__ == "__main__":
    app()
