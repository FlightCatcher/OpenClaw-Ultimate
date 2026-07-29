from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.integrations import (
    OpenClawCliClient,
    OpenClawIntegrationError,
)

openclaw_app = typer.Typer(
    no_args_is_help=True,
    help="连接和检查本机 OpenClaw Gateway",
)
console = Console()


def build_openclaw_client(
    settings: Settings,
) -> OpenClawCliClient:
    return OpenClawCliClient(
        cli_command=settings.openclaw_cli_command,
        gateway_url=settings.openclaw_gateway_url,
        agent_id=settings.openclaw_agent_id,
        model=settings.openclaw_model,
        timeout=settings.openclaw_timeout,
    )


@openclaw_app.command("status")
def openclaw_status() -> None:
    """检查 VELA 与本机 OpenClaw 的真实连接。"""

    client = build_openclaw_client(load_settings())

    try:
        health = client.health()
        status = client.status()
    except OpenClawIntegrationError as exc:
        console.print(f"[red]OpenClaw 接入失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="VELA ↔ OpenClaw")
    table.add_column("项目")
    table.add_column("状态")
    table.add_row("Gateway 存活", "是" if health.live else "否")
    table.add_row("Gateway 就绪", "是" if health.ready else "否")
    table.add_row("运行状态", status.runtime_status or "未知")
    table.add_row("服务状态", status.service_state or "未知")
    table.add_row("CLI 版本", status.cli_version or "未知")
    table.add_row("Gateway 版本", status.gateway_version or "未知")
    table.add_row(
        "地址",
        f"{status.bind_host or '未知'}:{status.port or '未知'}",
    )
    table.add_row("RPC", "已连接" if status.rpc_ok else "不可用")
    table.add_row("配置审计", "通过" if status.config_valid else "未通过")
    console.print(table)


@openclaw_app.command("ask")
def openclaw_ask(
    message: str = typer.Argument(
        ...,
        help="交给现有 OpenClaw Agent 的任务",
    ),
    session_key: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="可选的 OpenClaw 会话键",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="临时覆盖 OpenClaw 后端模型",
    ),
) -> None:
    """通过 VELA 调用现有 OpenClaw Agent。"""

    client = build_openclaw_client(load_settings())

    try:
        result = client.run_agent(
            message,
            session_key=session_key,
            model=model,
        )
    except (OpenClawIntegrationError, ValueError) as exc:
        console.print(f"[red]OpenClaw 调用失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(result.text)
    console.print(f"[dim]OpenClaw run={result.run_id or 'unknown'} · status={result.status}[/dim]")
