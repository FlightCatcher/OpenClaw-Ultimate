from __future__ import annotations

import asyncio
from collections.abc import Sequence

import typer
from rich.console import Console
from rich.table import Table

from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.models.catalog import (
    ModelCatalogError,
    ModelDescriptor,
    OllamaModelCatalog,
)
from openclaw_ultimate.models.router import (
    ModelRouter,
    TaskKind,
)

model_app = typer.Typer(
    no_args_is_help=True,
    help="检查本地模型库存和硬件感知路由",
)
console = Console()


def build_model_router(
    settings: Settings,
    models: Sequence[ModelDescriptor],
) -> ModelRouter:
    gib = 1024**3
    return ModelRouter(
        models,
        max_resident_bytes=int(settings.model_resident_budget_gb * gib),
        preferences={
            TaskKind.CHAT: settings.model_route_chat,
            TaskKind.CODING: settings.model_route_coding,
            TaskKind.PLANNING: settings.model_route_planning,
            TaskKind.TOOL_CALLING: (settings.model_route_tool_calling),
            TaskKind.VISION: settings.model_route_vision,
            TaskKind.EMBEDDING: (settings.model_route_embedding),
        },
    )


@model_app.command("routes")
def model_routes() -> None:
    """读取 Ollama 实际库存并显示每类任务的模型路由。"""

    async def run() -> None:
        settings = load_settings()
        catalog = OllamaModelCatalog(
            base_url=settings.ollama_base_url,
            timeout=min(settings.model_timeout, 30.0),
        )
        models = await catalog.discover()
        router = build_model_router(
            settings,
            models,
        )

        inventory = Table(title="Ollama 模型库存")
        inventory.add_column("模型")
        inventory.add_column("大小", justify="right")
        inventory.add_column("能力")

        for model in models:
            inventory.add_row(
                model.name,
                f"{model.size_bytes / (1024**3):.2f} GiB",
                ", ".join(sorted(capability.value for capability in model.capabilities)),
            )

        routes = Table(
            title=(f"OCU 模型路由 (驻留预算 {settings.model_resident_budget_gb:.1f} GiB)")
        )
        routes.add_column("任务")
        routes.add_column("模型")
        routes.add_column("原因")

        selected = {route.task: route for route in router.select_all()}

        for task in TaskKind:
            route = selected.get(task)
            routes.add_row(
                task.value,
                route.model.model_ref if route else "无可用模型",
                route.reason if route else "能力或显存预算不满足",
            )

        console.print(inventory)
        console.print(routes)

    try:
        asyncio.run(run())
    except ModelCatalogError as exc:
        console.print(f"[red]模型目录读取失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc
