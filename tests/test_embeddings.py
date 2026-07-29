from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from openclaw_ultimate.models import (
    ModelResponseError,
    OpenAICompatibleEmbeddingModel,
)


def test_embedding_model_serializes_and_parses_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        captured["authorization"] = request.headers.get("Authorization")

        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {
                        "object": "embedding",
                        "index": 1,
                        "embedding": [0.0, 1.0],
                    },
                    {
                        "object": "embedding",
                        "index": 0,
                        "embedding": [1.0, 0.0],
                    },
                ],
            },
        )

    async def run_test() -> tuple[tuple[float, ...], ...]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            model = OpenAICompatibleEmbeddingModel(
                model="embedding-model",
                base_url="http://testserver/v1",
                api_key="test-key",
                client=client,
            )
            return await model.embed(("航空", "人工智能"))

    vectors = asyncio.run(run_test())

    assert vectors == (
        (1.0, 0.0),
        (0.0, 1.0),
    )
    assert captured["url"] == ("http://testserver/v1/embeddings")
    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"] == {
        "model": "embedding-model",
        "input": ["航空", "人工智能"],
    }


def test_embedding_model_rejects_wrong_count() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": 0,
                        "embedding": [1, 2],
                    }
                ]
            },
        )

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            model = OpenAICompatibleEmbeddingModel(
                model="embedding-model",
                client=client,
            )
            await model.embed(("one", "two"))

    with pytest.raises(
        ModelResponseError,
        match="count",
    ):
        asyncio.run(run_test())


def test_embedding_model_accepts_empty_batch() -> None:
    model = OpenAICompatibleEmbeddingModel(model="embedding-model")

    assert asyncio.run(model.embed(())) == ()
