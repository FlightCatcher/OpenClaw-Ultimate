from __future__ import annotations

import pytest
from pydantic import ValidationError

from openclaw_ultimate.config import Settings


def test_context_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.context_token_budget == 8192
    assert settings.context_response_reserve == 2048


def test_context_reserve_must_be_smaller() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            context_token_budget=1024,
            context_response_reserve=1024,
        )
