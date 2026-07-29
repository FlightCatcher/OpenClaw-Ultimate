from __future__ import annotations

import json
from collections.abc import Sequence

from openclaw_ultimate.context import (
    ContextSelection,
    ContextWindowBuilder,
)
from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.models.base import ModelClient
from openclaw_ultimate.sessions import SQLiteSessionStore


class SummaryGenerationError(RuntimeError):
    """模型未能生成有效会话摘要。"""


class ConversationSummarizer:
    """使用当前语言模型生成滚动会话摘要。"""

    def __init__(
        self,
        model: ModelClient,
        *,
        max_characters: int = 4000,
    ) -> None:
        if max_characters < 100:
            raise ValueError(
                "max_characters must be at least 100."
            )

        self.model = model
        self.max_characters = max_characters

    async def summarize(
        self,
        *,
        previous_summary: str | None,
        messages: Sequence[Message],
    ) -> str:
        if not messages:
            return previous_summary or ""

        payload = {
            "previous_summary": previous_summary or "",
            "new_messages": [
                self._serialize_message(message)
                for message in messages
            ],
        }

        response = await self.model.complete(
            messages=(
                Message.system(
                    "你是会话记忆压缩器。"
                    "请把旧摘要和新增消息合并成一份简洁、准确、"
                    "可供后续 AI 使用的中文摘要。"
                    "必须保留用户身份、偏好、目标、承诺、重要事实、"
                    "项目状态、决定和未完成事项。"
                    "删除寒暄、重复内容和无用措辞。"
                    "不要解释你的工作，只输出摘要正文。"
                ),
                Message.user(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        default=str,
                    )
                ),
            ),
            tools=(),
        )

        content = (response.content or "").strip()

        if not content:
            raise SummaryGenerationError(
                "Model returned an empty conversation summary."
            )

        return content[: self.max_characters]

    @staticmethod
    def _serialize_message(
        message: Message,
    ) -> dict[str, object]:
        return {
            "role": message.role,
            "content": message.content,
            "name": message.name,
            "tool_call_id": message.tool_call_id,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": dict(
                        tool_call.arguments
                    ),
                }
                for tool_call in message.tool_calls
            ],
        }


class RollingSummaryContextManager:
    """构造 Token 上下文并自动压缩被裁掉的旧消息。"""

    def __init__(
        self,
        *,
        builder: ContextWindowBuilder,
        summarizer: ConversationSummarizer,
    ) -> None:
        self.builder = builder
        self.summarizer = summarizer

    async def build(
        self,
        *,
        store: SQLiteSessionStore,
        session_id: str,
        system_prompt: str,
    ) -> ContextSelection:
        raw_messages = store.load_messages(
            session_id
        )
        summary_record = store.get_summary(
            session_id
        )

        stored_system = next(
            (
                message
                for message in raw_messages
                if message.role == "system"
            ),
            None,
        )

        base_system_prompt = (
            stored_system.content
            if stored_system
            and stored_system.content
            else system_prompt
        )

        conversation_messages = tuple(
            message
            for message in raw_messages
            if message.role != "system"
        )

        covered_count = (
            summary_record.covered_message_count
            if summary_record is not None
            else 0
        )
        covered_count = min(
            covered_count,
            len(conversation_messages),
        )

        summary_text = (
            summary_record.summary
            if summary_record is not None
            else None
        )

        remaining_messages = list(
            conversation_messages[
                covered_count:
            ]
        )

        while True:
            system_message = Message.system(
                self._compose_system_prompt(
                    base_system_prompt,
                    summary_text,
                )
            )

            candidate_messages = (
                system_message,
                *remaining_messages,
            )

            selection = self.builder.build(
                candidate_messages
            )

            if selection.dropped_messages == 0:
                return selection

            dropped_count = (
                selection.dropped_messages
            )
            dropped_chunk = tuple(
                remaining_messages[
                    :dropped_count
                ]
            )

            if not dropped_chunk:
                return selection

            summary_text = (
                await self.summarizer.summarize(
                    previous_summary=summary_text,
                    messages=dropped_chunk,
                )
            )

            covered_count += len(
                dropped_chunk
            )
            remaining_messages = (
                remaining_messages[
                    dropped_count:
                ]
            )

            store.upsert_summary(
                session_id=session_id,
                summary=summary_text,
                covered_message_count=(
                    covered_count
                ),
            )

    @staticmethod
    def _compose_system_prompt(
        system_prompt: str,
        summary: str | None,
    ) -> str:
        if not summary:
            return system_prompt

        return (
            system_prompt.rstrip()
            + "\n\n"
            + "以下是此前会话的压缩摘要。"
            + "请把它作为可靠的历史上下文使用：\n"
            + summary.strip()
        )
