from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from openclaw_ultimate.config import Settings


def test_session_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.session_db_path == Path(".openclaw/sessions.db")
    assert settings.history_message_limit == 100


def test_session_history_limit_validation() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            history_message_limit=0,
        )
