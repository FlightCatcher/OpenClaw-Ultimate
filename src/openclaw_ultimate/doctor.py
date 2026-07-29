from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from openclaw_ultimate.config import Settings

console = Console()


def run_doctor(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
) -> bool:
    """检查 Python、工作区、Ollama 和所需模型。"""

    checks = (
        _check_python(),
        _check_workspace(settings.workspace_root),
        _check_ollama(
            settings,
            client=client,
        ),
    )

    console.print()
    console.print("[green]环境检查通过。[/green]" if all(checks) else "[red]环境检查未通过。[/red]")

    return all(checks)


def _check_python() -> bool:
    version = sys.version_info
    supported = version.major == 3 and version.minor == 12
    rendered = f"{version.major}.{version.minor}.{version.micro}"

    if supported:
        console.print(f"[green]✓[/green] Python {rendered}")
    else:
        console.print(f"[red]✗[/red] Python {rendered}，需要 Python 3.12")

    return supported


def _check_workspace(
    workspace_root: Path,
) -> bool:
    root = workspace_root.resolve()
    valid = root.exists() and root.is_dir()

    if valid:
        console.print(f"[green]✓[/green] 工作区 {root}")
    else:
        console.print(f"[red]✗[/red] 工作区不存在：{root}")

    return valid


def _check_ollama(
    settings: Settings,
    *,
    client: httpx.Client | None,
) -> bool:
    owns_client = client is None
    current_client = client or httpx.Client()

    try:
        response = current_client.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout=5,
        )
        response.raise_for_status()
        names = _parse_model_names(response.json())
    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
    ) as exc:
        console.print(f"[red]✗[/red] Ollama 不可用：{exc}")
        return False
    finally:
        if owns_client:
            current_client.close()

    console.print("[green]✓[/green] Ollama 已连接")
    required_models = [settings.ollama_model]

    if settings.memory_enabled:
        required_models.append(settings.embedding_model)

    missing = [model for model in required_models if model not in names]

    for model in required_models:
        if model in names:
            console.print(f"[green]✓[/green] 模型 {model}")
        else:
            console.print(f"[red]✗[/red] 缺少模型 {model}")

    shell_status = "已开启（白名单模式）" if settings.enable_shell_tool else "已关闭"
    console.print(f"[dim]Shell 工具：{shell_status}[/dim]")

    return not missing


def _parse_model_names(
    payload: Any,
) -> frozenset[str]:
    if not isinstance(payload, dict):
        raise TypeError("Ollama model response must be an object.")

    models = payload.get("models")

    if not isinstance(models, list):
        raise TypeError("Ollama model response has no model list.")

    names: set[str] = set()

    for model in models:
        if not isinstance(model, dict):
            continue

        name = model.get("name")

        if isinstance(name, str):
            names.add(name)

    return frozenset(names)
