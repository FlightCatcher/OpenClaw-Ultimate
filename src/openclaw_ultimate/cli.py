from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.runtime import AgentRuntime
from openclaw_ultimate.doctor import run_doctor


app = typer.Typer(
    no_args_is_help=True,
    help="OpenClaw-Ultimate 本地 AI Agent 平台",
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
) -> None:
    """与本地 Agent 对话。"""

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
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]已退出。[/yellow]")


async def _chat_async(
    *,
    settings: Settings,
    initial_message: str | None,
) -> None:
    agent = build_default_agent(settings)
    runtime = AgentRuntime()

    console.print(
        f"[green]{settings.app_name}[/green]"
        f" · 模型：[cyan]{settings.ollama_model}[/cyan]"
    )

    if initial_message is not None:
        prompt = initial_message.strip()

        if not prompt:
            raise typer.BadParameter("消息不能为空。")

        result = await runtime.run(agent, prompt)
        console.print(f"[magenta]AI>[/magenta] {result.output}")
        return

    console.print(
        "[dim]输入 /exit 或 /quit 退出。[/dim]"
    )

    history: tuple[Message, ...] = ()

    while True:
        try:
            prompt = console.input(
                "[blue]你> [/blue]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]已退出。[/yellow]")
            break

        if prompt.lower() in {
            "/exit",
            "/quit",
        }:
            break

        if not prompt:
            continue

        try:
            result = await runtime.run(
                agent,
                prompt,
                history=history,
            )

            history = result.messages

            console.print(
                f"[magenta]AI>[/magenta] {result.output}"
            )

        except Exception as exc:
            console.print(
                f"[red]错误：{exc}[/red]"
            )


if __name__ == "__main__":
    app()
