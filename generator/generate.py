from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from textwrap import dedent

FILES = {
    "pyproject.toml": """
[project]
name = "openclaw-ultimate"
version = "1.0.0"
description = "Local-first modular AI agent platform"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
  "httpx>=0.27",
  "loguru>=0.7",
  "ollama>=0.4",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "pyyaml>=6.0",
  "rich>=13.7",
  "typer>=0.12",
]

[project.scripts]
ocu = "openclaw_ultimate.cli:app"

[dependency-groups]
dev = ["mypy>=1.11", "pytest>=8.3", "ruff>=0.6"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/openclaw_ultimate"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"
""",
    ".python-version": "3.12\n",
    ".env.example": """
OCU_APP_NAME=VELA
OCU_LOG_LEVEL=INFO
OCU_OLLAMA_BASE_URL=http://127.0.0.1:11434
OCU_OLLAMA_MODEL=qwen3:8b
OCU_ENABLE_SHELL_TOOL=false
OCU_WORKSPACE_ROOT=.
""",
    "README.md": """
# VELA

本地优先、模块化、可扩展的 AI Agent 平台。

## 初始化

```powershell
.\\bootstrap.ps1
```

## 运行

```powershell
uv run ocu doctor
uv run ocu chat
```

Shell 工具默认关闭。
""",
    "src/openclaw_ultimate/__init__.py": '__version__ = "1.0.0"\n',
    "src/openclaw_ultimate/config.py": """
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="OCU_", extra="ignore")
    app_name: str = "VELA"
    log_level: str = "INFO"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    enable_shell_tool: bool = False
    workspace_root: Path = Field(default_factory=Path.cwd)

def load_settings() -> Settings:
    return Settings()
""",
    "src/openclaw_ultimate/models/base.py": """
from typing import Protocol

class ModelProvider(Protocol):
    def chat(self, user_message: str, system_prompt: str | None = None) -> str: ...
""",
    "src/openclaw_ultimate/models/ollama_provider.py": """
import ollama

class OllamaProvider:
    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.client = ollama.Client(host=base_url)

    def chat(self, user_message: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        response = self.client.chat(model=self.model, messages=messages)
        return str(response["message"]["content"])
""",
    "src/openclaw_ultimate/models/__init__.py": """
from .ollama_provider import OllamaProvider
__all__ = ["OllamaProvider"]
""",
    "src/openclaw_ultimate/runtime.py": """
from dataclasses import dataclass
from openclaw_ultimate.models.base import ModelProvider

SYSTEM_PROMPT = (
    "You are VELA, a verified local-first assistant. "
    "Be accurate and never claim a tool succeeded unless it actually ran."
)

@dataclass
class AgentRuntime:
    model: ModelProvider
    system_prompt: str = SYSTEM_PROMPT

    def respond(self, user_message: str) -> str:
        message = user_message.strip()
        if not message:
            raise ValueError("User message cannot be empty.")
        return self.model.chat(message, self.system_prompt)
""",
    "src/openclaw_ultimate/doctor.py": """
import sys, httpx
from rich.console import Console
from openclaw_ultimate.config import Settings

console = Console()

def run_doctor(settings: Settings) -> bool:
    ok = True
    console.print(f"[bold]Python:[/bold] {sys.version.split()[0]}")
    if not sys.version.startswith("3.12."):
        console.print("[yellow]建议使用 Python 3.12。[/yellow]")
        ok = False
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        r.raise_for_status()
        console.print("[green]Ollama: connected[/green]")
    except Exception as exc:
        console.print(f"[red]Ollama: unavailable ({exc})[/red]")
        ok = False
    return ok
""",
    "src/openclaw_ultimate/cli.py": """
import typer
from rich.console import Console
from openclaw_ultimate.config import load_settings
from openclaw_ultimate.doctor import run_doctor
from openclaw_ultimate.models import OllamaProvider
from openclaw_ultimate.runtime import AgentRuntime

app = typer.Typer(no_args_is_help=True)
console = Console()

@app.command()
def doctor() -> None:
    raise typer.Exit(code=0 if run_doctor(load_settings()) else 1)

@app.command()
def chat() -> None:
    s = load_settings()
    runtime = AgentRuntime(OllamaProvider(s.ollama_model, s.ollama_base_url))
    console.print(f"[green]{s.app_name}[/green] · {s.ollama_model}")
    while True:
        try:
            msg = console.input("[blue]你> [/blue]").strip()
            if msg.lower() in {"/exit", "/quit"}:
                break
            console.print(f"[magenta]AI>[/magenta] {runtime.respond(msg)}")
        except KeyboardInterrupt:
            break
        except Exception as exc:
            console.print(f"[red]错误：{exc}[/red]")

if __name__ == "__main__":
    app()
""",
    "tests/test_runtime.py": """
import pytest
from openclaw_ultimate.runtime import AgentRuntime

class FakeModel:
    def chat(self, user_message: str, system_prompt: str | None = None) -> str:
        return f"echo:{user_message}"

def test_runtime() -> None:
    assert AgentRuntime(FakeModel()).respond("hello") == "echo:hello"

def test_empty_input() -> None:
    with pytest.raises(ValueError):
        AgentRuntime(FakeModel()).respond(" ")
""",
    "docs/00_SYSTEM_PHILOSOPHY.md": """
# 系统哲学

- 本地优先
- 最小权限
- 用户控制
- 模块化
- 可验证
- 可回滚
""",
    "docs/01_ARCHITECTURE.md": """
# 架构

User → CLI → AgentRuntime → Ollama

后续扩展 Planner、Memory、RAG、MCP、ComfyUI。
""",
    "docs/02_AGENT_LOOP.md": """
# Agent Loop

输入 → 上下文构建 → 模型调用 → 结果返回 → 日志记录。
""",
    "docs/03_HARDWARE_PROFILE.md": """
# Hardware Profile

- Ryzen 5 3600
- RTX 3060 Ti 8GB
- RAM 16GB
- Windows 11
- Models: E:\\AI-Models
""",
    "bootstrap.ps1": """
$ErrorActionPreference = "Stop"
uv python pin 3.12
if (Test-Path ".venv") { Remove-Item -Recurse -Force ".venv" }
uv sync --dev
if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env" }
uv run ocu doctor
""",
    "scripts/verify.ps1": """
$ErrorActionPreference = "Stop"
uv run ruff check .
uv run pytest
Write-Host "All checks passed." -ForegroundColor Green
""",
}

DIRS = [
    "assets",
    "benchmarks",
    "configs",
    "docs",
    "examples",
    "plugins",
    "prompts",
    "scripts",
    "src/openclaw_ultimate/models",
    "tests",
    ".github/workflows",
]


def norm(s: str) -> str:
    return dedent(s).lstrip("\n").rstrip() + "\n"


def backup(path: Path) -> None:
    candidate = path.with_suffix(path.suffix + ".bak")
    n = 1
    while candidate.exists():
        candidate = path.with_suffix(path.suffix + f".bak{n}")
        n += 1
    shutil.copy2(path, candidate)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    root = Path(args.root).resolve()

    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)

    for name, content in FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not args.force:
            print(f"[SKIP] {name}")
            continue
        if path.exists():
            backup(path)
        path.write_text(norm(content), encoding="utf-8")
        print(f"[WRITE] {name}")

    print("\\n完成。下一步执行：")
    print("  .\\\\bootstrap.ps1")
    print("  uv run pytest")
    print("  uv run ocu chat")


if __name__ == "__main__":
    main()
