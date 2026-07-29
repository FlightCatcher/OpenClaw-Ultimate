from __future__ import annotations

import pytest

from openclaw_ultimate.context import (
    ContextBudgetError,
    ContextWindowBuilder,
    estimate_message_tokens,
    estimate_messages_tokens,
    estimate_text_tokens,
)
from openclaw_ultimate.core.messages import (
    Message,
    ToolCall,
)


def test_token_estimator_supports_chinese() -> None:
    assert estimate_text_tokens("你好，世界") >= 4

    assert estimate_text_tokens("hello world") >= 1


def test_context_keeps_system_and_latest_turn() -> None:
    system = Message.system("系统提示")

    old_turn = (
        Message.user("旧问题" * 20),
        Message.assistant("旧回答" * 20),
    )

    latest_turn = (
        Message.user("新问题" * 20),
        Message.assistant("新回答" * 20),
    )

    exact_budget = estimate_messages_tokens(
        (
            system,
            *latest_turn,
        )
    )

    selection = ContextWindowBuilder(
        max_tokens=exact_budget,
        response_reserve_tokens=0,
    ).build(
        (
            system,
            *old_turn,
            *latest_turn,
        )
    )

    assert selection.messages == (
        system,
        *latest_turn,
    )

    assert selection.dropped_messages == 2


def test_tool_call_turn_is_never_split() -> None:
    system = Message.system("系统提示")

    old_turn = (
        Message.user("旧问题"),
        Message.assistant("旧回答"),
    )

    tool_turn = (
        Message.user("计算 10 加 20"),
        Message.assistant(
            tool_calls=(
                ToolCall(
                    id="call-1",
                    name="add",
                    arguments={
                        "a": 10,
                        "b": 20,
                    },
                ),
            )
        ),
        Message.tool(
            name="add",
            tool_call_id="call-1",
            content=('{"ok": true, "result": 30}'),
        ),
        Message.assistant("结果是 30"),
    )

    exact_budget = estimate_messages_tokens(
        (
            system,
            *tool_turn,
        )
    )

    selection = ContextWindowBuilder(
        max_tokens=exact_budget,
        response_reserve_tokens=0,
    ).build(
        (
            system,
            *old_turn,
            *tool_turn,
        )
    )

    assert selection.messages == (
        system,
        *tool_turn,
    )

    assert any(message.role == "tool" for message in selection.messages)


def test_context_is_recent_contiguous_suffix() -> None:
    system = Message.system("系统提示")
    first = (
        Message.user("第一轮"),
        Message.assistant("第一轮回答"),
    )
    second = (
        Message.user("第二轮" * 40),
        Message.assistant("第二轮回答" * 40),
    )
    third = (
        Message.user("第三轮"),
        Message.assistant("第三轮回答"),
    )

    third_budget = estimate_messages_tokens(
        (
            system,
            *third,
        )
    )

    selection = ContextWindowBuilder(
        max_tokens=third_budget,
        response_reserve_tokens=0,
    ).build(
        (
            system,
            *first,
            *second,
            *third,
        )
    )

    assert selection.messages == (
        system,
        *third,
    )


def test_system_message_over_budget_raises() -> None:
    system = Message.system("很长的系统提示" * 30)

    system_tokens = estimate_message_tokens(system)

    with pytest.raises(ContextBudgetError):
        ContextWindowBuilder(
            max_tokens=system_tokens - 1,
            response_reserve_tokens=0,
        ).build((system,))


def test_invalid_reserve_is_rejected() -> None:
    with pytest.raises(ValueError):
        ContextWindowBuilder(
            max_tokens=100,
            response_reserve_tokens=100,
        )


def test_empty_context() -> None:
    selection = ContextWindowBuilder(
        max_tokens=100,
        response_reserve_tokens=10,
    ).build(())

    assert selection.messages == ()
    assert selection.estimated_tokens == 0
    assert selection.dropped_messages == 0
