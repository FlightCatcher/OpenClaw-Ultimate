from __future__ import annotations

import pytest
from pydantic import ValidationError

from openclaw_ultimate.config import Settings


def test_openai_base_url_appends_v1() -> None:
    settings = Settings(
        _env_file=None,
        ollama_base_url="http://127.0.0.1:11434/",
    )

    assert settings.openai_base_url == "http://127.0.0.1:11434/v1"


def test_openai_base_url_preserves_existing_v1() -> None:
    settings = Settings(
        _env_file=None,
        ollama_base_url="http://localhost:1234/v1",
    )

    assert settings.openai_base_url == "http://localhost:1234/v1"


def test_settings_reject_invalid_max_steps() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            max_steps=0,
        )


def test_settings_reject_invalid_temperature() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            temperature=3,
        )
