from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Sequence

from openclaw_ultimate.context import (
    ContextWindowBuilder,
    estimate_messages_tokens,
)
from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.tools import ToolDefinition
from openclaw_ultimate.memory import (
    ConversationSummarizer,
    RollingSummaryContextManager,
)
from openclaw_ultimate.models.base import (
    ModelResponse,
)
from openclaw_ultimate.sessions import (
    SQLiteSessionStore,
)


class SummaryFakeModel:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
    ) -> ModelResponse:
        self.calls += 1

        return ModelResponse(
            content="用户喜欢航空和人工智能。"
        )


def test_rolling_summary_is_created_and_reused(
    tmp_path: Path,
) -> None:
    async def run_test() -> None:
        store = SQLiteSessionStore(
            tmp_path / "sessions.db"
        )
        session = store.create_session()

        system_prompt = "你是测试助手。"

        old_turn = (
            Message.user(
                "这是非常长的旧问题。" * 30
            ),
            Message.assistant(
                "这是非常长的旧回答。" * 30
            ),
        )
        latest_turn = (
            Message.user("最新问题是什么？"),
            Message.assistant("这是最新回答。"),
        )

        store.append_messages(
            session.id,
            (
                Message.system(system_prompt),
                *old_turn,
                *latest_turn,
            ),
        )

        expected_system = Message.system(
            system_prompt
            + "\n\n"
            + "以下是此前会话的压缩摘要。"
            + "请把它作为可靠的历史上下文使用：\n"
            + "用户喜欢航空和人工智能。"
        )

        required_tokens = estimate_messages_tokens(
            (
                expected_system,
                *latest_turn,
            )
        )

        model = SummaryFakeModel()
        manager = RollingSummaryContextManager(
            builder=ContextWindowBuilder(
                max_tokens=required_tokens + 20,
                response_reserve_tokens=0,
            ),
            summarizer=ConversationSummarizer(
                model
            ),
        )

        first = await manager.build(
            store=store,
            session_id=session.id,
            system_prompt=system_prompt,
        )

        assert model.calls == 1
        assert first.messages[0].role == "system"
        assert "航空和人工智能" in (
            first.messages[0].content or ""
        )
        assert first.messages[-2:] == latest_turn

        saved_summary = store.get_summary(
            session.id
        )

        assert saved_summary is not None
        assert (
            saved_summary.covered_message_count
            == len(old_turn)
        )

        second = await manager.build(
            store=store,
            session_id=session.id,
            system_prompt=system_prompt,
        )

        assert model.calls == 1
        assert second.messages == first.messages

    asyncio.run(run_test())
