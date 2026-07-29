from __future__ import annotations

import json
from pathlib import Path

import httpx

from openclaw_ultimate.integrations.comfyui import (
    ComfyUIClient,
    OpenClawComfyProfile,
)


def test_discovers_comfyui_profile_from_openclaw_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "gateway": {"token": "must-not-be-returned"},
                "plugins": {
                    "entries": {
                        "comfy": {
                            "config": {
                                "baseUrl": "http://127.0.0.1:8188",
                                "image": {
                                    "workflowPath": "workflow.json",
                                    "promptNodeId": "6",
                                    "promptInputName": "text",
                                    "outputNodeId": "9",
                                    "pollIntervalMs": 500,
                                    "timeoutMs": 30_000,
                                },
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    profile = OpenClawComfyProfile.discover(config_path)

    assert profile is not None
    assert profile.base_url == "http://127.0.0.1:8188"
    assert profile.workflow_path == Path("workflow.json")
    assert profile.poll_interval_seconds == 0.5
    assert profile.timeout_seconds == 30
    assert not hasattr(profile, "token")


def test_comfyui_health_parses_system_stats() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/system_stats"
        return httpx.Response(
            200,
            json={
                "system": {
                    "os": "win32",
                    "python_version": "3.12",
                },
                "devices": [{}, {}],
            },
        )

    profile = _profile(Path("unused.json"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        health = ComfyUIClient(
            profile=profile,
            client=http_client,
        ).health()

    assert health.online is True
    assert health.operating_system == "win32"
    assert health.device_count == 2


def test_comfyui_generates_image_with_configured_workflow(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "6": {
                    "inputs": {
                        "text": "old prompt",
                    }
                },
                "9": {"inputs": {}},
            }
        ),
        encoding="utf-8",
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            assert payload["prompt"]["6"]["inputs"]["text"] == "new prompt"
            return httpx.Response(200, json={"prompt_id": "job-1"})

        assert request.url.path == "/history/job-1"
        return httpx.Response(
            200,
            json={
                "job-1": {
                    "outputs": {
                        "9": {
                            "images": [
                                {
                                    "filename": "result.png",
                                    "subfolder": "ocu",
                                    "type": "output",
                                }
                            ]
                        }
                    }
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ComfyUIClient(
            profile=_profile(workflow_path),
            client=http_client,
            sleeper=lambda _: None,
        ).generate_image("new prompt")

    assert result.prompt_id == "job-1"
    assert result.outputs[0].filename == "result.png"
    assert "filename=result.png" in result.outputs[0].view_url
    assert len(requests) == 2


def _profile(
    workflow_path: Path,
) -> OpenClawComfyProfile:
    return OpenClawComfyProfile(
        base_url="http://127.0.0.1:8188",
        workflow_path=workflow_path,
        prompt_node_id="6",
        prompt_input_name="text",
        output_node_id="9",
        poll_interval_seconds=0.01,
        timeout_seconds=1,
    )
