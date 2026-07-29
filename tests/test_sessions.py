from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_ultimate.core.messages import (
    Message,
    ToolCall,
)
from openclaw_ultimate.sessions import (
    SessionNotFoundError,
    SQLiteSessionStore,
)


def create_store(
    tmp_path: Path,
) -> SQLiteSessionStore:
    return SQLiteSessionStore(tmp_path / "sessions.db")


def test_session_lifecycle(
    tmp_path: Path,
) -> None:
    store = create_store(tmp_path)

    session = store.create_session("测试会话")

    assert session.title == "测试会话"
    assert session.message_count == 0

    loaded = store.get_session(session.id)

    assert loaded.id == session.id

    renamed = store.rename_session(
        session.id,
        "新标题",
    )

    assert renamed.title == "新标题"

    sessions = store.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].id == session.id

    store.delete_session(session.id)

    with pytest.raises(SessionNotFoundError):
        store.get_session(session.id)


def test_message_round_trip(
    tmp_path: Path,
) -> None:
    store = create_store(tmp_path)
    session = store.create_session()

    messages = (
        Message.system("系统提示"),
        Message.user("计算 1 加 2"),
        Message.assistant(
            tool_calls=(
                ToolCall(
                    id="call-1",
                    name="add",
                    arguments={
                        "a": 1,
                        "b": 2,
                    },
                ),
            )
        ),
        Message.tool(
            name="add",
            tool_call_id="call-1",
            content=('{"ok": true, "result": 3}'),
        ),
        Message.assistant("结果是 3"),
    )

    count = store.append_messages(
        session.id,
        messages,
    )

    assert count == 5

    loaded = store.load_messages(session.id)

    assert loaded == messages

    updated_session = store.get_session(session.id)

    assert updated_session.message_count == 5


def test_history_limit_preserves_system_message(
    tmp_path: Path,
) -> None:
    store = create_store(tmp_path)
    session = store.create_session()

    store.append_messages(
        session.id,
        (
            Message.system("系统提示"),
            Message.user("第一条"),
            Message.assistant("第一个回答"),
            Message.user("第二条"),
            Message.assistant("第二个回答"),
        ),
    )

    loaded = store.load_messages(
        session.id,
        limit=2,
    )

    assert [message.role for message in loaded] == [
        "system",
        "user",
        "assistant",
    ]

    assert loaded[0].content == "系统提示"
    assert loaded[1].content == "第二条"
    assert loaded[2].content == "第二个回答"


def test_unknown_session_raises(
    tmp_path: Path,
) -> None:
    store = create_store(tmp_path)

    with pytest.raises(SessionNotFoundError):
        store.load_messages("missing")


def test_empty_session_title_is_rejected(
    tmp_path: Path,
) -> None:
    store = create_store(tmp_path)

    with pytest.raises(
        ValueError,
        match="title",
    ):
        store.create_session("   ")
