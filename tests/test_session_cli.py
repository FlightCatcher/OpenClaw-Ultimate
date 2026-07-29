from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from openclaw_ultimate.cli import app
from openclaw_ultimate.sessions import (
    SQLiteSessionStore,
)


runner = CliRunner()


def session_environment(
    db_path: Path,
) -> dict[str, str]:
    return {
        "OCU_SESSION_DB_PATH": str(
            db_path
        ),
    }


def test_session_new_and_list(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sessions.db"
    environment = session_environment(
        db_path
    )

    result = runner.invoke(
        app,
        [
            "session",
            "new",
            "CLI 测试会话",
        ],
        env=environment,
    )

    assert result.exit_code == 0
    assert "会话创建成功" in result.stdout

    list_result = runner.invoke(
        app,
        [
            "session",
            "list",
        ],
        env=environment,
    )

    assert list_result.exit_code == 0
    assert "CLI 测试会话" in list_result.stdout


def test_session_show_and_rename(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sessions.db"
    environment = session_environment(
        db_path
    )

    store = SQLiteSessionStore(
        db_path
    )
    session = store.create_session(
        "旧标题"
    )

    rename_result = runner.invoke(
        app,
        [
            "session",
            "rename",
            session.id,
            "新标题",
        ],
        env=environment,
    )

    assert rename_result.exit_code == 0
    assert "新标题" in rename_result.stdout

    show_result = runner.invoke(
        app,
        [
            "session",
            "show",
            session.id,
        ],
        env=environment,
    )

    assert show_result.exit_code == 0
    assert "新标题" in show_result.stdout
    assert session.id in show_result.stdout


def test_session_delete(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sessions.db"
    environment = session_environment(
        db_path
    )

    store = SQLiteSessionStore(
        db_path
    )
    session = store.create_session(
        "准备删除"
    )

    result = runner.invoke(
        app,
        [
            "session",
            "delete",
            session.id,
            "--yes",
        ],
        env=environment,
    )

    assert result.exit_code == 0
    assert "会话已删除" in result.stdout
    assert store.list_sessions() == ()
