from __future__ import annotations

import pytest
from pydantic import ValidationError

from openclaw_ultimate.config import Settings


def test_workspace_tool_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.enable_shell_tool is False
    assert settings.workspace_max_read_bytes == 1_000_000
    assert settings.workspace_max_results == 200
    assert settings.shell_allowed_commands == (
        "git",
        "uv",
        "python",
        "pytest",
    )
    assert settings.shell_timeout == 30


def test_workspace_tool_limits_are_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            workspace_max_read_bytes=0,
        )

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            shell_timeout=0,
        )
