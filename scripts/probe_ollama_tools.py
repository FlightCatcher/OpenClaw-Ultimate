from __future__ import annotations

import asyncio
import json

from openclaw_ultimate import Agent, AgentRuntime
from openclaw_ultimate.models import OpenAICompatibleModel


BASE_URL = "http://127.0.0.1:11434/v1"
MODEL_NAME = "qwen3:8b"


def add(a: float, b: float) -> float:
    """计算两个数字之和。"""
    return a + b


async def main() -> None:
    print(f"正在连接：{BASE_URL}")
    print(f"使用模型：{MODEL_NAME}")
    print("正在测试真实工具调用……")

    model = OpenAICompatibleModel(
        model=MODEL_NAME,
        base_url=BASE_URL,
        timeout=300,
        temperature=0,
    )

    agent = Agent(
        name="calculator-agent",
        model=model,
        system_prompt=(
            "你是 OpenClaw-Ultimate 的工具调用测试助手。"
            "遇到数学计算时，必须调用提供的工具，"
            "不要自行心算。工具返回结果后，再用中文回答用户。"
        ),
        max_steps=5,
    )

    agent.tools.add(
        name="add",
        description="计算两个数字之和。",
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

    runtime = AgentRuntime()

    result = await runtime.run(
        agent,
        "请计算 137.5 加 862.5，并告诉我结果。",
    )

    print()
    print("========== 最终结果 ==========")
    print(f"模型回答：{result.output}")
    print(f"运行步数：{result.steps}")
    print(f"消息数量：{len(result.messages)}")

    print()
    print("========== 消息记录 ==========")

    tool_called = False

    for index, message in enumerate(result.messages, start=1):
        print(f"[{index}] role={message.role}")

        if message.content:
            print(f"    content={message.content}")

        if message.tool_calls:
            tool_called = True

            for tool_call in message.tool_calls:
                print(f"    tool_name={tool_call.name}")
                print(
                    "    arguments="
                    + json.dumps(
                        dict(tool_call.arguments),
                        ensure_ascii=False,
                    )
                )

        if message.tool_call_id:
            print(f"    tool_call_id={message.tool_call_id}")

    if not tool_called:
        raise RuntimeError(
            "模型完成了回答，但没有调用 add 工具。"
        )

    if result.steps < 2:
        raise RuntimeError(
            "工具调用流程应该至少运行两个步骤。"
        )

    print()
    print("状态：真实工具调用成功")


if __name__ == "__main__":
    asyncio.run(main())
