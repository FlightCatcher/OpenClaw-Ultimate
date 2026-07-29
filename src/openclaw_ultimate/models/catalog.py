from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx


class ModelCatalogError(RuntimeError):
    """模型目录无法读取或返回了无效数据。"""


class ModelCapability(StrEnum):
    CHAT = "chat"
    CODING = "coding"
    PLANNING = "planning"
    TOOL_CALLING = "tool_calling"
    VISION = "vision"
    EMBEDDING = "embedding"


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    provider: str
    name: str
    model_ref: str
    size_bytes: int
    family: str | None
    parameter_size: str | None
    quantization: str | None
    capabilities: frozenset[ModelCapability]

    def supports(
        self,
        required: frozenset[ModelCapability],
    ) -> bool:
        return required.issubset(self.capabilities)


class OllamaModelCatalog:
    """从本机 Ollama 读取实际已安装模型，不猜测下载状态。"""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url cannot be empty.")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client

    async def discover(
        self,
    ) -> tuple[ModelDescriptor, ...]:
        endpoint = f"{self.base_url}/api/tags"

        try:
            if self._client is not None:
                response = await self._client.get(
                    endpoint,
                    timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        endpoint,
                        timeout=self.timeout,
                    )

            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelCatalogError(f"Could not read the Ollama model catalog: {exc}") from exc

        return self.parse_payload(payload)

    @classmethod
    def parse_payload(
        cls,
        payload: Any,
    ) -> tuple[ModelDescriptor, ...]:
        if not isinstance(payload, dict):
            raise ModelCatalogError("Ollama catalog root must be an object.")

        raw_models = payload.get("models")

        if not isinstance(raw_models, list):
            raise ModelCatalogError("Ollama catalog has no model list.")

        models = [cls._parse_model(item) for item in raw_models if isinstance(item, dict)]
        return tuple(
            sorted(
                models,
                key=lambda item: item.name.casefold(),
            )
        )

    @classmethod
    def _parse_model(
        cls,
        raw: Mapping[str, Any],
    ) -> ModelDescriptor:
        name = raw.get("name")
        size = raw.get("size", 0)
        details = raw.get("details")

        if not isinstance(name, str) or not name.strip():
            raise ModelCatalogError("Ollama model has no valid name.")

        if not isinstance(size, int) or size < 0:
            raise ModelCatalogError(f"Ollama model '{name}' has an invalid size.")

        detail_map = details if isinstance(details, dict) else {}
        family = cls._optional_text(detail_map.get("family"))

        return ModelDescriptor(
            provider="ollama",
            name=name,
            model_ref=f"ollama/{name}",
            size_bytes=size,
            family=family,
            parameter_size=cls._optional_text(detail_map.get("parameter_size")),
            quantization=cls._optional_text(detail_map.get("quantization_level")),
            capabilities=cls.infer_capabilities(
                name=name,
                family=family,
                families=detail_map.get("families"),
            ),
        )

    @staticmethod
    def infer_capabilities(
        *,
        name: str,
        family: str | None,
        families: Any = None,
    ) -> frozenset[ModelCapability]:
        text = " ".join(
            (
                name,
                family or "",
                " ".join(families) if isinstance(families, list) else "",
            )
        ).casefold()

        if "embed" in text or "bert" in text:
            return frozenset({ModelCapability.EMBEDDING})

        capabilities = {ModelCapability.CHAT}

        if "vl" in text or "vision" in text or "clip" in text or "moondream" in text:
            capabilities.add(ModelCapability.VISION)

        if "coder" in text:
            capabilities.update(
                {
                    ModelCapability.CODING,
                    ModelCapability.PLANNING,
                }
            )

        if "qwen3" in text and ModelCapability.VISION not in capabilities:
            capabilities.update(
                {
                    ModelCapability.CODING,
                    ModelCapability.PLANNING,
                    ModelCapability.TOOL_CALLING,
                }
            )

        return frozenset(capabilities)

    @staticmethod
    def _optional_text(
        value: Any,
    ) -> str | None:
        return value if isinstance(value, str) and value else None
