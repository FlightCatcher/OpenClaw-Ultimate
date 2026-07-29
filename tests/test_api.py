from __future__ import annotations

import threading

import httpx
import pytest

from openclaw_ultimate.api import (
    ApiApplication,
    LocalApiServer,
)
from openclaw_ultimate.config import Settings
from openclaw_ultimate.diagnostics import (
    ComponentDiagnostic,
    ComponentState,
    DiagnosticReport,
)


def test_api_health_returns_structured_diagnostics(
    tmp_path,
) -> None:
    application = ApiApplication(
        Settings(
            _env_file=None,
            workspace_root=tmp_path,
            openclaw_enabled=False,
            comfyui_enabled=False,
            knowledge_enabled=False,
        ),
        diagnostic_provider=lambda _: DiagnosticReport(
            state=ComponentState.READY,
            components=(
                ComponentDiagnostic(
                    name="test",
                    state=ComponentState.READY,
                    detail="ok",
                    required=True,
                ),
            ),
        ),
    )

    response = application.dispatch(
        "GET",
        "/health",
    )

    assert response.status == 200
    assert response.payload["ok"] is True
    assert response.payload["components"][0]["name"] == "test"


def test_api_rejects_invalid_search_body(
    tmp_path,
) -> None:
    application = ApiApplication(
        Settings(
            _env_file=None,
            workspace_root=tmp_path,
            knowledge_enabled=False,
        )
    )

    response = application.dispatch(
        "POST",
        "/v1/knowledge/search",
        {"query": ""},
    )

    assert response.status == 400
    assert response.payload["ok"] is False


def test_local_api_server_serves_health_over_http(
    tmp_path,
) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=tmp_path,
        api_host="127.0.0.1",
        api_port=0,
        openclaw_enabled=False,
        comfyui_enabled=False,
        knowledge_enabled=False,
    )
    application = ApiApplication(
        settings,
        diagnostic_provider=lambda _: DiagnosticReport(
            state=ComponentState.READY,
            components=(
                ComponentDiagnostic(
                    name="test",
                    state=ComponentState.READY,
                    detail="ok",
                    required=True,
                ),
            ),
        ),
    )
    server = LocalApiServer(
        settings,
        application=application,
    )
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    host, port = server.address

    try:
        response = httpx.get(
            f"http://{host}:{port}/health",
            timeout=5,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_local_api_rejects_remote_bind(
    tmp_path,
) -> None:
    settings = Settings(
        _env_file=None,
        workspace_root=tmp_path,
        api_host="0.0.0.0",
        api_port=0,
        api_allow_remote=False,
    )

    with pytest.raises(
        ValueError,
        match="Remote API binding is disabled",
    ):
        LocalApiServer(settings)
