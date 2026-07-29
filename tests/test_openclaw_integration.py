from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence

import httpx
import pytest

from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.config import Settings
from openclaw_ultimate.integrations import (
    OpenClawCliClient,
    OpenClawCommandError,
)


class FakeRunner:
    def __init__(
        self,
        payload: dict[str, object],
        *,
        returncode: int = 0,
        stderr: str = "",
    ) -> None:
        self.payload = payload
        self.returncode = returncode
        self.stderr = stderr
        self.commands: list[tuple[str, ...]] = []
        self.message_text: str | None = None

    def __call__(
        self,
        command: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        rendered = tuple(command)
        self.commands.append(rendered)

        if "--message-file" in rendered:
            index = rendered.index("--message-file")
            with open(rendered[index + 1], encoding="utf-8") as handle:
                self.message_text = handle.read()

        return subprocess.CompletedProcess(
            args=list(rendered),
            returncode=self.returncode,
            stdout=json.dumps(self.payload),
            stderr=self.stderr,
        )


def test_gateway_health_uses_local_probes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(
                200,
                json={"ok": True, "status": "live"},
            )

        return httpx.Response(
            200,
            json={
                "ready": True,
                "failing": [],
                "uptimeMs": 1234,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenClawCliClient(
            cli_command="python",
            http_client=http_client,
        )
        health = client.health()

    assert health.live
    assert health.ready
    assert health.status == "live"
    assert health.uptime_ms == 1234


def test_gateway_status_parses_cli_json() -> None:
    runner = FakeRunner(
        {
            "cli": {"version": "2026.7.1-2"},
            "service": {
                "runtime": {
                    "status": "running",
                    "state": "Ready",
                },
                "configAudit": {"ok": True},
            },
            "gateway": {
                "version": "2026.7.1-2",
                "bindHost": "127.0.0.1",
                "port": 18789,
            },
            "rpc": {"ok": True},
        }
    )
    client = OpenClawCliClient(
        cli_command="python",
        command_runner=runner,
    )

    status = client.status()

    assert status.cli_version == "2026.7.1-2"
    assert status.runtime_status == "running"
    assert status.service_state == "Ready"
    assert status.port == 18789
    assert status.rpc_ok
    assert status.config_valid
    assert runner.commands[0][1:] == (
        "gateway",
        "status",
        "--json",
    )


def test_run_agent_uses_message_file_and_parses_payload() -> None:
    runner = FakeRunner(
        {
            "runId": "run-123",
            "status": "ok",
            "summary": "completed",
            "result": {
                "payloads": [
                    {"text": "OpenClaw 已完成任务。"},
                ]
            },
        }
    )
    client = OpenClawCliClient(
        cli_command="python",
        agent_id="main",
        model="ollama/qwen3:8b",
        command_runner=runner,
    )

    result = client.run_agent(
        "检查项目",
        session_key="ocu-test",
    )

    command = runner.commands[0]
    assert runner.message_text == "检查项目"
    assert "--message-file" in command
    assert "--message" not in command
    assert command[command.index("--agent") + 1] == "main"
    assert command[command.index("--model") + 1] == "ollama/qwen3:8b"
    assert command[command.index("--session-key") + 1] == "ocu-test"
    assert result.run_id == "run-123"
    assert result.text == "OpenClaw 已完成任务。"
    assert result.payload_count == 1


def test_run_agent_rejects_failed_status() -> None:
    client = OpenClawCliClient(
        cli_command="python",
        command_runner=FakeRunner(
            {
                "status": "error",
                "result": {"payloads": []},
            }
        ),
    )

    with pytest.raises(OpenClawCommandError, match="status 'error'"):
        client.run_agent("test")


def test_read_web_page_uses_browser_cli_and_closes_tab() -> None:
    commands: list[tuple[str, ...]] = []

    def runner(
        command: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        rendered = tuple(command)
        commands.append(rendered)
        action = rendered[2]

        if action == "open":
            payload = {
                "targetId": "target-1",
                "tabId": "t1",
                "title": "Example Domain",
                "url": "https://example.com/",
            }
        elif action == "snapshot":
            payload = {
                "url": "https://example.com/",
                "snapshot": '- heading "Example Domain"',
            }
        else:
            payload = {"ok": True}

        return subprocess.CompletedProcess(
            args=list(rendered),
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    client = OpenClawCliClient(
        cli_command="python",
        command_runner=runner,
    )

    page = client.read_web_page("https://example.com")

    assert page.title == "Example Domain"
    assert page.snapshot == '- heading "Example Domain"'
    assert [command[2] for command in commands] == [
        "start",
        "open",
        "snapshot",
        "close",
    ]
    assert commands[-1][3] == "t1"


def test_default_agent_registers_openclaw_tool() -> None:
    settings = Settings(
        _env_file=None,
        openclaw_enabled=True,
    )

    agent = build_default_agent(settings)

    assert "ask_openclaw" in agent.tools
    assert "read_web_page" in agent.tools


def test_default_agent_can_disable_openclaw_tool() -> None:
    settings = Settings(
        _env_file=None,
        openclaw_enabled=False,
    )

    agent = build_default_agent(settings)

    assert "ask_openclaw" not in agent.tools
    assert "read_web_page" not in agent.tools
