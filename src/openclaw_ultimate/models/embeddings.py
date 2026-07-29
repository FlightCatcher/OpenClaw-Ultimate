from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import httpx

from openclaw_ultimate.models.openai_compatible import (
    ModelRequestError,
    ModelResponseError,
)


class EmbeddingClient(Protocol):
    """向量模型适配器必须实现的接口。"""

    async def embed(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]: ...


class OpenAICompatibleEmbeddingModel:
    """兼容 OpenAI ``/embeddings`` 接口的异步客户端。"""

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434/v1",
        api_key: str | None = None,
        timeout: float = 60.0,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("model cannot be empty.")

        if not base_url.strip():
            raise ValueError("base_url cannot be empty.")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = dict(extra_headers or {})
        self.extra_body = dict(extra_body or {})
        self._client = client

    async def embed(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        items = tuple(texts)

        if not items:
            return ()

        if any(not isinstance(text, str) or not text.strip() for text in items):
            raise ValueError("Embedding input cannot contain empty text.")

        payload: dict[str, Any] = {
            "model": self.model,
            "input": list(items),
            **self.extra_body,
        }
        endpoint = f"{self.base_url}/embeddings"

        try:
            if self._client is not None:
                response = await self._client.post(
                    endpoint,
                    json=payload,
                    headers=self._build_headers(),
                    timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=self._build_headers(),
                        timeout=self.timeout,
                    )

            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:1000]
            raise ModelRequestError(
                f"Embedding request returned HTTP {exc.response.status_code}: {body}"
            ) from exc
        except httpx.RequestError as exc:
            raise ModelRequestError(f"Could not connect to embedding endpoint: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ModelResponseError("Embedding response was not valid JSON.") from exc

        return self._parse_response(
            data,
            expected_count=len(items),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            **self.extra_headers,
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    @staticmethod
    def _parse_response(
        data: Any,
        *,
        expected_count: int,
    ) -> tuple[tuple[float, ...], ...]:
        if not isinstance(data, dict):
            raise ModelResponseError("Embedding response root must be an object.")

        raw_items = data.get("data")

        if not isinstance(raw_items, list):
            raise ModelResponseError("Embedding response data must be a list.")

        ordered: list[tuple[int, tuple[float, ...]]] = []

        for fallback_index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                raise ModelResponseError("Embedding response item must be an object.")

            raw_embedding = raw_item.get("embedding")

            if not isinstance(raw_embedding, list) or not raw_embedding:
                raise ModelResponseError("Embedding response item has no vector.")

            try:
                vector = tuple(float(value) for value in raw_embedding)
            except (TypeError, ValueError) as exc:
                raise ModelResponseError("Embedding vector must contain numbers.") from exc

            raw_index = raw_item.get("index", fallback_index)

            if not isinstance(raw_index, int):
                raise ModelResponseError("Embedding response index must be an integer.")

            ordered.append((raw_index, vector))

        ordered.sort(key=lambda item: item[0])
        vectors = tuple(vector for _, vector in ordered)

        if len(vectors) != expected_count:
            raise ModelResponseError("Embedding response count does not match the input count.")

        dimensions = {len(vector) for vector in vectors}

        if len(dimensions) != 1:
            raise ModelResponseError("Embedding vectors must have the same dimensions.")

        return vectors
