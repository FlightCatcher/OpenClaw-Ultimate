from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from openclaw_ultimate import cli
from openclaw_ultimate.memory import (
    MemoryRecord,
    SQLiteMemoryStore,
)

runner = CliRunner()


def memory_environment(
    db_path: Path,
) -> dict[str, str]:
    return {
        "OCU_MEMORY_DB_PATH": str(db_path),
    }


def test_memory_list_and_delete(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "memory.db"
    environment = memory_environment(db_path)
    store = SQLiteMemoryStore(db_path)
    memory = store.add(
        content="用户喜欢航空",
        embedding=(1.0, 0.0),
    )

    list_result = runner.invoke(
        cli.app,
        ["memory", "list"],
        env=environment,
    )

    assert list_result.exit_code == 0
    assert "用户喜欢航空" in list_result.stdout
    assert memory.id[:12] in list_result.stdout

    delete_result = runner.invoke(
        cli.app,
        [
            "memory",
            "delete",
            memory.id,
            "--yes",
        ],
        env=environment,
    )

    assert delete_result.exit_code == 0
    assert "长期记忆已删除" in delete_result.stdout
    assert store.list() == ()


def test_memory_remember_command(
    monkeypatch,
) -> None:
    class FakeLongTermMemory:
        async def remember(
            self,
            content: str,
        ) -> MemoryRecord:
            return MemoryRecord(
                id="memory-1",
                content=content,
                embedding=(1.0,),
                source_session_id=None,
                created_at="now",
                updated_at="now",
            )

    monkeypatch.setattr(
        cli,
        "_build_long_term_memory",
        lambda settings: FakeLongTermMemory(),
    )

    result = runner.invoke(
        cli.app,
        [
            "memory",
            "remember",
            "用户喜欢航空",
        ],
    )

    assert result.exit_code == 0
    assert "长期记忆已保存" in result.stdout
    assert "memory-1" in result.stdout
