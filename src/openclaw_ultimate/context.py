from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from openclaw_ultimate.core.messages import Message


class ContextBudgetError(RuntimeError):
    """上下文预算无法满足最基本要求。"""


@dataclass(frozen=True, slots=True)
class ContextSelection:
    """上下文裁剪结果。"""

    messages: tuple[Message, ...]
    estimated_tokens: int
    dropped_messages: int
    max_input_tokens: int


def estimate_text_tokens(
    text: str | None,
) -> int:
    """使用稳定、无外部依赖的启发式方法估算 Token。

    中日韩字符通常接近一个字符一个 Token；
    其他文本大约按每四个字符一个 Token 估算。
    """

    if not text:
        return 0

    cjk_count = sum(
        1
        for character in text
        if _is_cjk(character)
    )
    other_count = len(text) - cjk_count

    return cjk_count + math.ceil(
        other_count / 4
    )


def estimate_message_tokens(
    message: Message,
) -> int:
    """估算一条内部消息占用的 Token 数量。"""

    token_count = 4

    token_count += estimate_text_tokens(
        message.role
    )
    token_count += estimate_text_tokens(
        message.content
    )
    token_count += estimate_text_tokens(
        message.name
    )
    token_count += estimate_text_tokens(
        message.tool_call_id
    )

    for tool_call in message.tool_calls:
        token_count += 6
        token_count += estimate_text_tokens(
            tool_call.id
        )
        token_count += estimate_text_tokens(
            tool_call.name
        )
        token_count += estimate_text_tokens(
            json.dumps(
                dict(tool_call.arguments),
                ensure_ascii=False,
                default=str,
            )
        )

    return token_count


def estimate_messages_tokens(
    messages: Iterable[Message],
) -> int:
    """估算一组消息的 Token 总量。"""

    return sum(
        estimate_message_tokens(message)
        for message in messages
    )


class ContextWindowBuilder:
    """根据 Token 预算构造模型上下文。

    规则：

    1. 第一条 system 消息始终保留。
    2. 优先保留最近的对话轮次。
    3. 一个用户轮次内的工具调用和工具结果不可拆开。
    4. 预留模型输出所需的 Token 空间。
    """

    def __init__(
        self,
        *,
        max_tokens: int,
        response_reserve_tokens: int = 2048,
    ) -> None:
        if max_tokens < 1:
            raise ValueError(
                "max_tokens must be at least 1."
            )

        if response_reserve_tokens < 0:
            raise ValueError(
                "response_reserve_tokens cannot be negative."
            )

        if response_reserve_tokens >= max_tokens:
            raise ValueError(
                "response_reserve_tokens must be smaller "
                "than max_tokens."
            )

        self.max_tokens = max_tokens
        self.response_reserve_tokens = (
            response_reserve_tokens
        )

    @property
    def max_input_tokens(self) -> int:
        return (
            self.max_tokens
            - self.response_reserve_tokens
        )

    def build(
        self,
        messages: Iterable[Message],
    ) -> ContextSelection:
        """选择能够放入上下文预算的消息。"""

        items = tuple(messages)

        if not items:
            return ContextSelection(
                messages=(),
                estimated_tokens=0,
                dropped_messages=0,
                max_input_tokens=self.max_input_tokens,
            )

        system_message, remaining = (
            self._extract_system_message(items)
        )

        pinned_messages = (
            (system_message,)
            if system_message is not None
            else ()
        )

        pinned_tokens = (
            estimate_messages_tokens(
                pinned_messages
            )
        )

        if pinned_tokens > self.max_input_tokens:
            raise ContextBudgetError(
                "System message exceeds the available "
                "input token budget."
            )

        blocks = self._group_into_turns(
            remaining
        )

        selected_reversed: list[
            tuple[Message, ...]
        ] = []
        current_tokens = pinned_tokens

        for block in reversed(blocks):
            block_tokens = (
                estimate_messages_tokens(block)
            )

            if (
                current_tokens + block_tokens
                > self.max_input_tokens
            ):
                # 只保留连续的最近历史，
                # 不跳过中间轮次去选择更旧的内容。
                break

            selected_reversed.append(block)
            current_tokens += block_tokens

        selected_blocks = reversed(
            selected_reversed
        )

        selected_messages = (
            pinned_messages
            + tuple(
                message
                for block in selected_blocks
                for message in block
            )
        )

        return ContextSelection(
            messages=selected_messages,
            estimated_tokens=current_tokens,
            dropped_messages=(
                len(items)
                - len(selected_messages)
            ),
            max_input_tokens=self.max_input_tokens,
        )

    @staticmethod
    def _extract_system_message(
        messages: Sequence[Message],
    ) -> tuple[
        Message | None,
        tuple[Message, ...],
    ]:
        """取出第一条 system 消息并放到上下文首位。"""

        for index, message in enumerate(
            messages
        ):
            if message.role == "system":
                return (
                    message,
                    tuple(messages[:index])
                    + tuple(messages[index + 1:]),
                )

        return None, tuple(messages)

    @staticmethod
    def _group_into_turns(
        messages: Sequence[Message],
    ) -> tuple[
        tuple[Message, ...],
        ...,
    ]:
        """按用户轮次分组，避免拆散工具调用协议。"""

        if not messages:
            return ()

        blocks: list[
            tuple[Message, ...]
        ] = []
        current: list[Message] = []

        for message in messages:
            if (
                message.role == "user"
                and current
            ):
                blocks.append(tuple(current))
                current = [message]
            else:
                current.append(message)

        if current:
            blocks.append(tuple(current))

        return tuple(blocks)


def _is_cjk(
    character: str,
) -> bool:
    codepoint = ord(character)

    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x3040 <= codepoint <= 0x30FF
        or 0xAC00 <= codepoint <= 0xD7AF
    )
