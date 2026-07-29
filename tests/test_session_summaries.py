from __future__ import annotations

from pathlib import Path

from openclaw_ultimate.sessions import (
    SQLiteSessionStore,
)


def test_summary_round_trip(
    tmp_path: Path,
) -> None:
    store = SQLiteSessionStore(
        tmp_path / "sessions.db"
    )
    session = store.create_session(
        "摘要测试"
    )

    assert store.get_summary(
        session.id
    ) is None

    saved = store.upsert_summary(
        session_id=session.id,
        summary="用户喜欢航空和人工智能。",
        covered_message_count=4,
    )

    assert saved.summary == (
        "用户喜欢航空和人工智能。"
    )
    assert saved.covered_message_count == 4

    loaded = store.get_summary(
        session.id
    )

    assert loaded is not None
    assert loaded.summary == saved.summary
    assert loaded.covered_message_count == 4

    assert store.clear_summary(
        session.id
    )
    assert store.get_summary(
        session.id
    ) is None


def test_summary_is_deleted_with_session(
    tmp_path: Path,
) -> None:
    store = SQLiteSessionStore(
        tmp_path / "sessions.db"
    )
    session = store.create_session()

    store.upsert_summary(
        session_id=session.id,
        summary="测试摘要",
        covered_message_count=2,
    )

    store.delete_session(
        session.id
    )

    with store._connection() as connection:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM session_summaries
            """
        ).fetchone()[0]

    assert count == 0
