from __future__ import annotations

import asyncio

from openclaw_ultimate import Agent, AgentRuntime
from openclaw_ultimate.models import OpenAICompatibleModel


BASE_URL = "http://127.0.0.1:11434/v1"
MODEL_NAME = "qwen3:8b"


async def main() -> None:
    print(f"正在连接：{BASE_URL}")
    print(f"使用模型：{MODEL_NAME}")

    model = OpenAICompatibleModel(
        model=MODEL_NAME,
        base_url=BASE_URL,
        timeout=300,
        temperature=0.2,
    )

    agent = Agent(
        name="ollama-agent",
        model=model,
        system_prompt=(
            "你是 OpenClaw-Ultimate 的本地 AI 助手。"
            "请使用简洁、准确的中文回答。"
        ),
        max_steps=4,
    )

    runtime = AgentRuntime()

    result = await runtime.run(
        agent,
        "请用一句话回答：你是否已经成功接入 OpenClaw-Ultimate？",
    )

    print()
    print("========== 运行结果 ==========")
    print(f"模型回答：{result.output}")
    print(f"运行步数：{result.steps}")
    print(f"消息数量：{len(result.messages)}")

    if not result.output.strip():
        raise RuntimeError("模型返回了空内容。")

    print("状态：连接成功")


if __name__ == "__main__":
    asyncio.run(main())
