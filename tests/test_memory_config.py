from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from openclaw_ultimate.config import Settings


def test_memory_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.memory_enabled is True
    assert settings.memory_db_path == Path(".openclaw/memory.db")
    assert settings.embedding_model == ("qwen3-embedding:0.6b")
    assert settings.memory_recall_limit == 5


def test_memory_similarity_threshold_validation() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            memory_similarity_threshold=2,
        )
