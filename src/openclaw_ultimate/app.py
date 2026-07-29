from __future__ import annotations

from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.core.runtime import Agent
from openclaw_ultimate.models import OpenAICompatibleModel
from openclaw_ultimate.tools import (
    SafeCommandRunner,
    WorkspaceTools,
)


def add(a: float, b: float) -> float:
    """计算两个数字之和。"""

    return a + b


def build_default_agent(
    settings: Settings | None = None,
) -> Agent:
    """根据配置创建默认本地 Agent。"""

    current_settings = settings or load_settings()

    model = OpenAICompatibleModel(
        model=current_settings.ollama_model,
        base_url=current_settings.openai_base_url,
        api_key=current_settings.ollama_api_key,
        timeout=current_settings.model_timeout,
        temperature=current_settings.temperature,
    )

    agent = Agent(
        name="default-agent",
        model=model,
        system_prompt=current_settings.system_prompt,
        max_steps=current_settings.max_steps,
    )

    agent.tools.add(
        name="add",
        description="准确计算两个数字之和。",
        parameters={
            "type": "object",
            "properties": {
                "a": {
                    "type": "number",
                    "description": "第一个数字",
                },
                "b": {
                    "type": "number",
                    "description": "第二个数字",
                },
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        handler=add,
    )

    _register_workspace_tools(
        agent,
        current_settings,
    )

    return agent


def _register_workspace_tools(
    agent: Agent,
    settings: Settings,
) -> None:
    workspace = WorkspaceTools(
        settings.workspace_root,
        max_read_bytes=(settings.workspace_max_read_bytes),
        max_results=settings.workspace_max_results,
    )

    agent.tools.add(
        name="list_files",
        description=("列出 Agent 工作区内指定目录的文件和子目录。"),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": ("相对于工作区的目录，默认是根目录"),
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": ("文件匹配模式，例如 *.py"),
                    "default": "*",
                },
            },
            "additionalProperties": False,
        },
        handler=workspace.list_files,
    )
    agent.tools.add(
        name="read_text_file",
        description=("读取 Agent 工作区内的 UTF-8 文本文件。"),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": ("相对于工作区的文件路径"),
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=workspace.read_text_file,
    )
    agent.tools.add(
        name="search_text",
        description=("递归搜索 Agent 工作区中的文本内容。"),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要查找的文本",
                },
                "path": {
                    "type": "string",
                    "description": ("相对于工作区的搜索起点"),
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": ("文件匹配模式，例如 *.py"),
                    "default": "*",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否区分大小写",
                    "default": False,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=workspace.search_text,
    )

    if not settings.enable_shell_tool:
        return

    runner = SafeCommandRunner(
        workspace,
        allowed_commands=(settings.shell_allowed_commands),
        timeout=settings.shell_timeout,
        max_output_characters=(settings.shell_max_output_characters),
    )
    agent.tools.add(
        name="run_command",
        description=("在 Agent 工作区内执行白名单命令。不支持管道、重定向或 Shell 表达式。"),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": ("可执行程序名称，必须在白名单中"),
                },
                "arguments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "命令参数列表",
                    "default": [],
                },
                "working_directory": {
                    "type": "string",
                    "description": ("相对于工作区的运行目录"),
                    "default": ".",
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handler=runner.run_command,
    )
