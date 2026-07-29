from __future__ import annotations

from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.core.runtime import Agent
from openclaw_ultimate.models import OpenAICompatibleModel


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

    return agent
