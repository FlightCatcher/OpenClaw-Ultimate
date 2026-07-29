from __future__ import annotations

from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.config import Settings
from openclaw_ultimate.models import OpenAICompatibleModel


def test_build_default_agent() -> None:
    settings = Settings(
        _env_file=None,
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen3:8b",
        model_timeout=120,
        temperature=0.1,
        max_steps=6,
    )

    agent = build_default_agent(settings)

    assert agent.name == "default-agent"
    assert agent.max_steps == 6
    assert isinstance(
        agent.model,
        OpenAICompatibleModel,
    )
    assert agent.model.base_url == "http://localhost:11434/v1"
    assert agent.model.model == "qwen3:8b"
    assert "add" in agent.tools
    assert "list_files" in agent.tools
    assert "read_text_file" in agent.tools
    assert "search_text" in agent.tools
    assert "run_command" not in agent.tools


def test_build_default_agent_can_enable_shell(
    tmp_path,
) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=tmp_path,
        enable_shell_tool=True,
    )

    agent = build_default_agent(settings)

    assert "run_command" in agent.tools
