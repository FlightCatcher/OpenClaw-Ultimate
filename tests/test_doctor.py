from __future__ import annotations

import httpx

from openclaw_ultimate.config import Settings
from openclaw_ultimate.doctor import run_doctor


def test_doctor_passes_with_required_models(
    tmp_path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen3:8b"},
                    {"name": ("qwen3-embedding:0.6b")},
                ]
            },
        )

    settings = Settings(
        _env_file=None,
        workspace_root=tmp_path,
    )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert run_doctor(
            settings,
            client=client,
        )


def test_doctor_fails_when_model_is_missing(
    tmp_path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen3:8b"},
                ]
            },
        )

    settings = Settings(
        _env_file=None,
        workspace_root=tmp_path,
    )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert not run_doctor(
            settings,
            client=client,
        )
