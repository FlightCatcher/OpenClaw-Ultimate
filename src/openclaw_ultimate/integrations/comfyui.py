from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx


class ComfyUIError(RuntimeError):
    """ComfyUI 请求、工作流或响应无效。"""


class ComfyUIUnavailableError(ComfyUIError):
    """ComfyUI 服务当前不可用。"""


class ComfyUIWorkflowError(ComfyUIError):
    """配置的 ComfyUI 工作流无法安全执行。"""


@dataclass(frozen=True, slots=True)
class OpenClawComfyProfile:
    base_url: str
    workflow_path: Path
    prompt_node_id: str
    prompt_input_name: str
    output_node_id: str
    poll_interval_seconds: float
    timeout_seconds: float

    @classmethod
    def discover(
        cls,
        config_path: Path,
    ) -> OpenClawComfyProfile | None:
        """只读取 OpenClaw 配置中的 ComfyUI 非敏感运行字段。"""

        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        config = cls._nested_mapping(
            payload,
            "plugins",
            "entries",
            "comfy",
            "config",
        )
        image = config.get("image")

        if not isinstance(image, Mapping):
            return None

        base_url = config.get("baseUrl")
        workflow_path = image.get("workflowPath")
        prompt_node_id = image.get("promptNodeId")
        prompt_input_name = image.get("promptInputName")
        output_node_id = image.get("outputNodeId")

        required = (
            base_url,
            workflow_path,
            prompt_node_id,
            prompt_input_name,
            output_node_id,
        )

        if not all(isinstance(value, (str, int)) and str(value).strip() for value in required):
            return None

        poll_ms = cls._positive_number(image.get("pollIntervalMs"), default=1000.0)
        timeout_ms = cls._positive_number(image.get("timeoutMs"), default=600_000.0)

        return cls(
            base_url=str(base_url).rstrip("/"),
            workflow_path=Path(str(workflow_path)),
            prompt_node_id=str(prompt_node_id),
            prompt_input_name=str(prompt_input_name),
            output_node_id=str(output_node_id),
            poll_interval_seconds=poll_ms / 1000,
            timeout_seconds=timeout_ms / 1000,
        )

    @staticmethod
    def _nested_mapping(
        payload: Any,
        *keys: str,
    ) -> Mapping[str, Any]:
        current = payload

        for key in keys:
            if not isinstance(current, Mapping):
                return {}
            current = current.get(key)

        return current if isinstance(current, Mapping) else {}

    @staticmethod
    def _positive_number(
        value: Any,
        *,
        default: float,
    ) -> float:
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

        return default


@dataclass(frozen=True, slots=True)
class ComfyUIHealth:
    online: bool
    operating_system: str | None
    python_version: str | None
    device_count: int


@dataclass(frozen=True, slots=True)
class ComfyUIOutput:
    filename: str
    subfolder: str
    output_type: str
    view_url: str


@dataclass(frozen=True, slots=True)
class ComfyUIJobResult:
    prompt_id: str
    outputs: tuple[ComfyUIOutput, ...]


class ComfyUIClient:
    """调用本机 ComfyUI API，并限制为预先配置的工作流。"""

    def __init__(
        self,
        *,
        profile: OpenClawComfyProfile,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.profile = profile
        self._client = client
        self._sleeper = sleeper

    def health(self) -> ComfyUIHealth:
        payload = self._get_json("/system_stats")
        system = payload.get("system")
        devices = payload.get("devices")
        system_map = system if isinstance(system, Mapping) else {}
        device_list = devices if isinstance(devices, list) else []

        return ComfyUIHealth(
            online=True,
            operating_system=self._optional_text(system_map.get("os")),
            python_version=self._optional_text(system_map.get("python_version")),
            device_count=len(device_list),
        )

    def generate_image(
        self,
        prompt: str,
    ) -> ComfyUIJobResult:
        clean_prompt = prompt.strip()

        if not clean_prompt:
            raise ValueError("prompt cannot be empty.")

        workflow = self._load_workflow()
        node = workflow.get(self.profile.prompt_node_id)

        if not isinstance(node, dict):
            raise ComfyUIWorkflowError(f"Prompt node '{self.profile.prompt_node_id}' is missing.")

        inputs = node.get("inputs")

        if not isinstance(inputs, dict):
            raise ComfyUIWorkflowError(
                f"Prompt node '{self.profile.prompt_node_id}' has no input object."
            )

        inputs[self.profile.prompt_input_name] = clean_prompt
        payload = self._post_json(
            "/prompt",
            {
                "prompt": workflow,
                "client_id": f"ocu-{uuid4().hex}",
            },
        )
        prompt_id = self._optional_text(payload.get("prompt_id"))

        if not prompt_id:
            raise ComfyUIError("ComfyUI did not return a prompt_id.")

        return self._wait_for_outputs(prompt_id)

    def _load_workflow(self) -> dict[str, Any]:
        path = self.profile.workflow_path

        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            raise ComfyUIWorkflowError(f"Could not read workflow '{path}': {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ComfyUIWorkflowError(f"Workflow '{path}' is not valid JSON.") from exc

        if not isinstance(raw, dict):
            raise ComfyUIWorkflowError("ComfyUI workflow root must be an object.")

        return copy.deepcopy(raw)

    def _wait_for_outputs(
        self,
        prompt_id: str,
    ) -> ComfyUIJobResult:
        deadline = time.monotonic() + self.profile.timeout_seconds

        while time.monotonic() < deadline:
            payload = self._get_json(f"/history/{prompt_id}")
            record = payload.get(prompt_id)

            if isinstance(record, Mapping):
                outputs = self._parse_outputs(record)

                if outputs:
                    return ComfyUIJobResult(
                        prompt_id=prompt_id,
                        outputs=outputs,
                    )

                status = record.get("status")

                if isinstance(status, Mapping) and status.get("completed") is True:
                    raise ComfyUIError("ComfyUI completed without an image output.")

            self._sleeper(self.profile.poll_interval_seconds)

        raise TimeoutError(
            f"ComfyUI job '{prompt_id}' exceeded {self.profile.timeout_seconds:.0f} seconds."
        )

    def _parse_outputs(
        self,
        record: Mapping[str, Any],
    ) -> tuple[ComfyUIOutput, ...]:
        raw_outputs = record.get("outputs")

        if not isinstance(raw_outputs, Mapping):
            return ()

        output_node = raw_outputs.get(self.profile.output_node_id)

        if not isinstance(output_node, Mapping):
            return ()

        images = output_node.get("images")

        if not isinstance(images, list):
            return ()

        parsed: list[ComfyUIOutput] = []

        for item in images:
            if not isinstance(item, Mapping):
                continue

            filename = self._optional_text(item.get("filename"))

            if not filename:
                continue

            subfolder = self._optional_text(item.get("subfolder")) or ""
            output_type = self._optional_text(item.get("type")) or "output"
            query = urlencode(
                {
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": output_type,
                }
            )
            parsed.append(
                ComfyUIOutput(
                    filename=filename,
                    subfolder=subfolder,
                    output_type=output_type,
                    view_url=f"{self.profile.base_url}/view?{query}",
                )
            )

        return tuple(parsed)

    def _get_json(
        self,
        path: str,
    ) -> dict[str, Any]:
        return self._request_json(
            "GET",
            path,
        )

    def _post_json(
        self,
        path: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            path,
            payload=payload,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        owns_client = self._client is None
        client = self._client or httpx.Client()

        try:
            response = client.request(
                method,
                f"{self.profile.base_url}{path}",
                json=payload,
                timeout=min(self.profile.timeout_seconds, 30.0),
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ComfyUIUnavailableError(f"ComfyUI request failed: {exc}") from exc
        finally:
            if owns_client:
                client.close()

        if not isinstance(result, dict):
            raise ComfyUIError("ComfyUI response must be a JSON object.")

        return result

    @staticmethod
    def _optional_text(
        value: Any,
    ) -> str | None:
        return value if isinstance(value, str) and value else None
