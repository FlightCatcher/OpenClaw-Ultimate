from __future__ import annotations

import asyncio

import httpx
import pytest

from openclaw_ultimate.models.catalog import (
    ModelCapability,
    ModelDescriptor,
    OllamaModelCatalog,
)
from openclaw_ultimate.models.router import (
    ModelRouter,
    NoModelRouteError,
    TaskKind,
)


def _model(
    name: str,
    size: int,
    *capabilities: ModelCapability,
) -> ModelDescriptor:
    return ModelDescriptor(
        provider="ollama",
        name=name,
        model_ref=f"ollama/{name}",
        size_bytes=size,
        family=None,
        parameter_size=None,
        quantization=None,
        capabilities=frozenset(capabilities),
    )


def test_catalog_discovers_installed_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "qwen3:8b",
                        "size": 5_225_388_164,
                        "details": {
                            "family": "qwen3",
                            "families": ["qwen3"],
                            "parameter_size": "8.2B",
                            "quantization_level": "Q4_K_M",
                        },
                    },
                    {
                        "name": "qwen3-embedding:0.6b",
                        "size": 639_150_858,
                        "details": {
                            "family": "qwen3",
                            "families": ["qwen3"],
                        },
                    },
                ]
            },
        )

    async def run_test():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await OllamaModelCatalog(
                client=client,
            ).discover()

    models = asyncio.run(run_test())
    by_name = {model.name: model for model in models}

    assert ModelCapability.TOOL_CALLING in by_name["qwen3:8b"].capabilities
    assert by_name["qwen3-embedding:0.6b"].capabilities == frozenset({ModelCapability.EMBEDDING})


def test_router_prefers_configured_task_model() -> None:
    gib = 1024**3
    models = (
        _model(
            "qwen3:8b",
            5 * gib,
            ModelCapability.CHAT,
            ModelCapability.CODING,
            ModelCapability.PLANNING,
            ModelCapability.TOOL_CALLING,
        ),
        _model(
            "qwen2.5-coder:7b",
            4 * gib,
            ModelCapability.CHAT,
            ModelCapability.CODING,
            ModelCapability.PLANNING,
        ),
    )
    router = ModelRouter(
        models,
        max_resident_bytes=6 * gib,
        preferences={
            TaskKind.CODING: (
                "qwen2.5-coder:7b",
                "qwen3:8b",
            )
        },
    )

    route = router.select(TaskKind.CODING)

    assert route.model.name == "qwen2.5-coder:7b"


def test_router_enforces_resident_memory_budget() -> None:
    gib = 1024**3
    router = ModelRouter(
        (
            _model(
                "vision-large",
                10 * gib,
                ModelCapability.CHAT,
                ModelCapability.VISION,
            ),
        ),
        max_resident_bytes=6 * gib,
    )

    with pytest.raises(
        NoModelRouteError,
        match="resident-memory",
    ):
        router.select(TaskKind.VISION)
