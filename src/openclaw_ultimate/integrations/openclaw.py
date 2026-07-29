from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


class OpenClawIntegrationError(RuntimeError):
    """VELA 与本机 OpenClaw 集成失败。"""


class OpenClawUnavailableError(OpenClawIntegrationError):
    """OpenClaw CLI 或 Gateway 当前不可用。"""


class OpenClawCommandError(OpenClawIntegrationError):
    """OpenClaw CLI 返回了失败状态或无效数据。"""


@dataclass(frozen=True, slots=True)
class OpenClawGatewayHealth:
    live: bool
    ready: bool
    status: str
    failing: tuple[str, ...] = ()
    uptime_ms: int | None = None


@dataclass(frozen=True, slots=True)
class OpenClawGatewayStatus:
    cli_version: str | None
    gateway_version: str | None
    runtime_status: str | None
    service_state: str | None
    bind_host: str | None
    port: int | None
    rpc_ok: bool
    config_valid: bool


@dataclass(frozen=True, slots=True)
class OpenClawAgentResult:
    run_id: str
    status: str
    summary: str | None
    text: str
    payload_count: int


@dataclass(frozen=True, slots=True)
class OpenClawBrowserPage:
    target_id: str
    tab_id: str
    title: str
    url: str
    snapshot: str


CommandRunner = Callable[
    [Sequence[str], float],
    subprocess.CompletedProcess[str],
]


def _default_command_runner(
    command: Sequence[str],
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )


class OpenClawCliClient:
    """通过官方 OpenClaw CLI 连接现有 Gateway。

    CLI 会从 OpenClaw 自己的配置中读取本机认证信息，因此 VELA 不复制、
    不打印、也不持久化 Gateway 密钥。
    """

    def __init__(
        self,
        *,
        cli_command: str = "openclaw",
        gateway_url: str = "http://127.0.0.1:18789",
        agent_id: str = "main",
        model: str | None = None,
        timeout: float = 600.0,
        command_runner: CommandRunner | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not cli_command.strip():
            raise ValueError("cli_command cannot be empty.")

        if not gateway_url.strip():
            raise ValueError("gateway_url cannot be empty.")

        if not agent_id.strip():
            raise ValueError("agent_id cannot be empty.")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self.cli_command = cli_command.strip()
        self.gateway_url = gateway_url.rstrip("/")
        self.agent_id = agent_id.strip()
        self.model = model.strip() if model and model.strip() else None
        self.timeout = timeout
        self._command_runner = command_runner or _default_command_runner
        self._http_client = http_client

    def health(self) -> OpenClawGatewayHealth:
        """读取 Gateway 的存活和就绪探针。"""

        owns_client = self._http_client is None
        client = self._http_client or httpx.Client()

        try:
            live_response = client.get(
                f"{self.gateway_url}/healthz",
                timeout=min(self.timeout, 10.0),
            )
            ready_response = client.get(
                f"{self.gateway_url}/readyz",
                timeout=min(self.timeout, 10.0),
            )
            live_response.raise_for_status()
            ready_response.raise_for_status()
            live_payload = self._require_object(
                live_response.json(),
                source="Gateway liveness response",
            )
            ready_payload = self._require_object(
                ready_response.json(),
                source="Gateway readiness response",
            )
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise OpenClawUnavailableError(f"OpenClaw Gateway is unavailable: {exc}") from exc
        finally:
            if owns_client:
                client.close()

        raw_failing = ready_payload.get("failing", ())
        failing = tuple(str(item) for item in raw_failing) if isinstance(raw_failing, list) else ()
        raw_uptime = ready_payload.get("uptimeMs")

        return OpenClawGatewayHealth(
            live=bool(live_payload.get("ok")),
            ready=bool(ready_payload.get("ready")),
            status=str(live_payload.get("status", "unknown")),
            failing=failing,
            uptime_ms=raw_uptime if isinstance(raw_uptime, int) else None,
        )

    def status(self) -> OpenClawGatewayStatus:
        """通过 OpenClaw CLI 查询 Gateway 与配置状态。"""

        payload = self._run_json(
            ("gateway", "status", "--json"),
            timeout=min(self.timeout, 60.0),
        )
        cli = self._object_or_empty(payload.get("cli"))
        gateway = self._object_or_empty(payload.get("gateway"))
        service = self._object_or_empty(payload.get("service"))
        runtime = self._object_or_empty(service.get("runtime"))
        config_audit = self._object_or_empty(service.get("configAudit"))
        rpc = self._object_or_empty(payload.get("rpc"))

        port = gateway.get("port")

        return OpenClawGatewayStatus(
            cli_version=self._optional_text(cli.get("version")),
            gateway_version=self._optional_text(gateway.get("version")),
            runtime_status=self._optional_text(runtime.get("status")),
            service_state=self._optional_text(runtime.get("state")),
            bind_host=self._optional_text(gateway.get("bindHost")),
            port=port if isinstance(port, int) else None,
            rpc_ok=bool(rpc.get("ok")),
            config_valid=bool(config_audit.get("ok")),
        )

    def run_agent(
        self,
        message: str,
        *,
        session_key: str | None = None,
        model: str | None = None,
    ) -> OpenClawAgentResult:
        """让现有 OpenClaw Agent 完成一次真实运行。"""

        clean_message = message.strip()

        if not clean_message:
            raise ValueError("message cannot be empty.")

        message_path = self._write_temporary_message(clean_message)

        try:
            args = [
                "agent",
                "--agent",
                self.agent_id,
                "--message-file",
                str(message_path),
                "--json",
                "--timeout",
                str(max(1, int(self.timeout))),
            ]
            selected_model = model.strip() if model and model.strip() else self.model

            if selected_model:
                args.extend(("--model", selected_model))

            if session_key and session_key.strip():
                args.extend(("--session-key", session_key.strip()))

            payload = self._run_json(
                tuple(args),
                timeout=self.timeout + 30.0,
            )
        finally:
            message_path.unlink(missing_ok=True)

        status = self._optional_text(payload.get("status")) or "unknown"
        result = self._object_or_empty(payload.get("result"))
        raw_payloads = result.get("payloads", ())
        payloads = raw_payloads if isinstance(raw_payloads, list) else []
        texts = [
            item["text"]
            for item in payloads
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        text = "\n".join(part for part in texts if part).strip()

        if status != "ok":
            raise OpenClawCommandError(f"OpenClaw agent returned status '{status}'.")

        if not text:
            raise OpenClawCommandError("OpenClaw agent returned no text payload.")

        return OpenClawAgentResult(
            run_id=self._optional_text(payload.get("runId")) or "",
            status=status,
            summary=self._optional_text(payload.get("summary")),
            text=text,
            payload_count=len(payloads),
        )

    def read_web_page(
        self,
        url: str,
        *,
        max_snapshot_characters: int = 30_000,
    ) -> OpenClawBrowserPage:
        """通过 OpenClaw 官方 Browser CLI 读取公开网页并关闭临时标签。"""

        clean_url = url.strip()
        parsed = urlparse(clean_url)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute HTTP or HTTPS URL.")

        if max_snapshot_characters < 100:
            raise ValueError("max_snapshot_characters must be at least 100.")

        self._run_json(
            (
                "browser",
                "start",
                "--json",
                "--timeout",
                "30000",
            ),
            timeout=min(self.timeout, 45.0),
        )
        opened = self._run_json(
            (
                "browser",
                "open",
                clean_url,
                "--json",
                "--timeout",
                "30000",
            ),
            timeout=min(self.timeout, 45.0),
        )
        target_id = self._optional_text(opened.get("targetId")) or ""
        tab_id = self._optional_text(opened.get("tabId")) or ""

        try:
            snapshot_payload = self._run_json(
                (
                    "browser",
                    "snapshot",
                    "--json",
                    "--timeout",
                    "30000",
                ),
                timeout=min(self.timeout, 45.0),
            )
        finally:
            if tab_id:
                try:
                    self._run_json(
                        (
                            "browser",
                            "close",
                            tab_id,
                            "--json",
                            "--timeout",
                            "30000",
                        ),
                        timeout=min(self.timeout, 45.0),
                    )
                except OpenClawIntegrationError:
                    pass

        snapshot = self._optional_text(snapshot_payload.get("snapshot")) or ""

        if not snapshot:
            raise OpenClawCommandError("OpenClaw Browser returned an empty page snapshot.")

        return OpenClawBrowserPage(
            target_id=target_id,
            tab_id=tab_id,
            title=self._optional_text(opened.get("title")) or "",
            url=self._optional_text(snapshot_payload.get("url"))
            or self._optional_text(opened.get("url"))
            or clean_url,
            snapshot=snapshot[:max_snapshot_characters],
        )

    def _run_json(
        self,
        arguments: Sequence[str],
        *,
        timeout: float,
    ) -> dict[str, Any]:
        executable = self._resolve_cli()
        command = (executable, *arguments)

        try:
            result = self._command_runner(
                command,
                timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise OpenClawUnavailableError(f"Could not run OpenClaw CLI: {exc}") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[:1000]
            raise OpenClawCommandError(
                f"OpenClaw CLI failed with exit code {result.returncode}: {detail}"
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise OpenClawCommandError("OpenClaw CLI did not return valid JSON.") from exc

        return self._require_object(
            payload,
            source="OpenClaw CLI response",
        )

    def _resolve_cli(self) -> str:
        candidate = Path(self.cli_command)

        if candidate.is_absolute() and candidate.exists():
            return str(candidate)

        resolved = shutil.which(self.cli_command)

        if resolved:
            return resolved

        raise OpenClawUnavailableError(f"OpenClaw CLI was not found: {self.cli_command}")

    @staticmethod
    def _write_temporary_message(
        message: str,
    ) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            suffix=".txt",
            prefix="ocu-openclaw-",
            delete=False,
        ) as handle:
            handle.write(message)
            return Path(handle.name)

    @staticmethod
    def _require_object(
        value: Any,
        *,
        source: str,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise OpenClawCommandError(f"{source} must be a JSON object.")

        return value

    @staticmethod
    def _object_or_empty(
        value: Any,
    ) -> Mapping[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_text(
        value: Any,
    ) -> str | None:
        return value if isinstance(value, str) and value else None
