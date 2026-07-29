from pathlib import Path

import pytest
from pydantic import ValidationError

from openclaw_ultimate.config import Settings


def test_planner_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.planner_db_path == Path(".openclaw/plans.db")
    assert settings.planner_max_steps == 12


def test_planner_max_steps_is_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            planner_max_steps=0,
        )
