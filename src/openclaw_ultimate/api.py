from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.branding import (
    LEGACY_NAME,
    PRODUCT_CHINESE_NAME,
    PRODUCT_FULL_NAME,
    PRODUCT_NAME,
    TAGLINE,
    VERSION,
)
from openclaw_ultimate.bridge import handle_request
from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.core.runtime import AgentRuntime
from openclaw_ultimate.diagnostics import (
    DiagnosticReport,
    collect_diagnostics,
)
from openclaw_ultimate.governance import (
    ConfirmationRequired,
    ConfirmationStatus,
    PlanControlState,
    RiskLevel,
    SQLiteGovernanceStore,
)
from openclaw_ultimate.integrations import (
    McpServerRegistry,
    OllamaVisionClient,
    StdioMcpClient,
    WhisperCliClient,
)
from openclaw_ultimate.memory import LongTermMemory, SQLiteMemoryStore
from openclaw_ultimate.models import OpenAICompatibleEmbeddingModel
from openclaw_ultimate.planner import PlanStatus, SQLitePlanStore
from openclaw_ultimate.rag import (
    SQLiteKnowledgeStore,
    build_knowledge_base,
)
from openclaw_ultimate.tools import WorkspaceTools

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status: int
    payload: Mapping[str, Any] | str | bytes
    content_type: str = "application/json; charset=utf-8"


DiagnosticProvider = Callable[
    [Settings],
    DiagnosticReport,
]


class ApiApplication:
    """不依赖 Web 框架的本地 JSON API 应用。"""

    def __init__(
        self,
        settings: Settings,
        *,
        diagnostic_provider: DiagnosticProvider | None = None,
    ) -> None:
        self.settings = settings
        self._diagnostic_provider = diagnostic_provider
        self.governance = SQLiteGovernanceStore(settings.governance_db_path)
        self.ui_root = Path(__file__).with_name("ui")

    def dispatch(
        self,
        method: str,
        target: str,
        body: Mapping[str, Any] | None = None,
    ) -> ApiResponse:
        path = urlsplit(target).path.rstrip("/") or "/"
        payload = dict(body or {})

        try:
            static_response = self._static_response(method, path)
            if static_response is not None:
                return static_response

            if method == "GET" and path == "/v1/meta":
                return self._ok(
                    {
                        "name": PRODUCT_NAME,
                        "chinese_name": PRODUCT_CHINESE_NAME,
                        "full_name": PRODUCT_FULL_NAME,
                        "legacy_name": LEGACY_NAME,
                        "version": VERSION,
                        "tagline": TAGLINE,
                        "api": "v1",
                    }
                )

            if method == "GET" and path in {
                "/health",
                "/v1/status",
            }:
                report = self._diagnostics()
                return ApiResponse(
                    status=(HTTPStatus.OK if report.ready else HTTPStatus.SERVICE_UNAVAILABLE),
                    payload={
                        "ok": report.ready,
                        "state": report.state.value,
                        "components": [
                            {
                                **asdict(component),
                                "state": component.state.value,
                            }
                            for component in report.components
                        ],
                    },
                )

            if method == "GET" and path == "/v1/plans":
                plans = SQLitePlanStore(self.settings.planner_db_path).list(
                    limit=self._bounded_int(
                        payload.get("limit", 100),
                        minimum=1,
                        maximum=500,
                    )
                )
                return self._ok(
                    {
                        "plans": [asdict(plan) for plan in plans],
                        "count": len(plans),
                    }
                )

            if method == "GET" and path == "/v1/knowledge/status":
                stats = SQLiteKnowledgeStore(self.settings.knowledge_db_path).stats()
                return self._ok(asdict(stats))

            if method == "POST" and path == "/v1/knowledge/search":
                query = self._required_text(
                    payload,
                    "query",
                )
                limit = self._bounded_int(
                    payload.get(
                        "limit",
                        self.settings.knowledge_search_limit,
                    ),
                    minimum=1,
                    maximum=20,
                )
                knowledge = build_knowledge_base(self.settings)
                hits = asyncio.run(
                    knowledge.search(
                        query,
                        limit=limit,
                        minimum_score=(self.settings.knowledge_minimum_score),
                    )
                )
                return self._ok(
                    {
                        "query": query,
                        "results": [
                            {
                                "score": hit.score,
                                "citation": hit.chunk.citation,
                                "content": hit.chunk.content,
                            }
                            for hit in hits
                        ],
                    }
                )

            if method == "POST" and path == "/v1/knowledge/index":
                index_report = asyncio.run(build_knowledge_base(self.settings).index())
                return self._ok(asdict(index_report))

            if method == "GET" and path == "/v1/memories":
                store = SQLiteMemoryStore(self.settings.memory_db_path)
                memories = store.list(
                    limit=self._bounded_int(
                        payload.get("limit", 100),
                        minimum=1,
                        maximum=500,
                    ),
                    include_archived=bool(payload.get("include_archived", False)),
                )
                return self._ok(
                    {
                        "memories": [self._serialize_memory(item) for item in memories],
                        "count": len(memories),
                    }
                )

            if method == "POST" and path == "/v1/memories":
                memory = asyncio.run(
                    self._memory().remember(
                        self._required_text(payload, "content"),
                        memory_type=str(payload.get("memory_type", "fact")),
                        importance=float(payload.get("importance", 0.5)),
                        sensitivity=str(payload.get("sensitivity", "normal")),
                        expires_at=self._optional_text(payload.get("expires_at")),
                    )
                )
                return self._ok(self._serialize_memory(memory))

            memory_id = self._parse_resource_route(path, "memories")
            if method == "DELETE" and memory_id is not None:
                self.governance.require_confirmation(
                    action="memory.delete",
                    description="Permanently delete a long-term memory.",
                    risk=RiskLevel.HIGH,
                    resource_id=memory_id,
                )
                SQLiteMemoryStore(self.settings.memory_db_path).delete(memory_id)
                return self._ok({"deleted": memory_id})

            if method == "GET" and path == "/v1/audit":
                limit = self._bounded_int(
                    payload.get("limit", 100),
                    minimum=1,
                    maximum=500,
                )
                return self._ok(
                    {"events": [asdict(event) for event in self.governance.list_audit(limit=limit)]}
                )

            if method == "GET" and path == "/v1/confirmations":
                status_value = payload.get("status")
                status = ConfirmationStatus(str(status_value)) if status_value is not None else None
                return self._ok(
                    {
                        "confirmations": [
                            asdict(item)
                            for item in self.governance.list_confirmations(
                                status=status,
                                limit=200,
                            )
                        ]
                    }
                )

            confirmation_route = self._parse_confirmation_route(path)
            if method == "POST" and confirmation_route is not None:
                confirmation_id, decision = confirmation_route
                resolved = self.governance.resolve_confirmation(
                    confirmation_id,
                    approve=decision == "approve",
                )
                return self._ok(asdict(resolved))

            if method == "GET" and path == "/v1/mcp/status":
                return self._ok(self._mcp_status())

            if method == "POST" and path == "/v1/mcp/test":
                server = self._required_text(payload, "server")
                registry = McpServerRegistry.load(
                    self.settings.mcp_servers_path,
                    project_root=self.settings.workspace_root,
                )
                with StdioMcpClient(
                    registry.get(server),
                    timeout=self.settings.mcp_timeout,
                ) as client:
                    tools = client.list_tools()
                    echo_result = client.call_tool(
                        "echo",
                        {"text": "VELA_MCP_OK"},
                    )
                return self._ok(
                    {
                        "server": server,
                        "tools": [asdict(tool) for tool in tools],
                        "probe": echo_result.structured_content,
                    }
                )

            if method == "POST" and path == "/v1/media/image":
                workspace = WorkspaceTools(self.settings.workspace_root)
                analysis = asyncio.run(
                    asyncio.to_thread(
                        OllamaVisionClient(
                            workspace=workspace,
                            base_url=self.settings.ollama_base_url,
                            model=self.settings.vision_model,
                            timeout=self.settings.media_timeout,
                            max_image_bytes=self.settings.vision_max_image_bytes,
                        ).analyze,
                        self._required_text(payload, "path"),
                        prompt=str(
                            payload.get(
                                "prompt",
                                "请描述这张图片，并准确识别其中可见的文字。",
                            )
                        ),
                    )
                )
                return self._ok(asdict(analysis))

            if method == "POST" and path == "/v1/media/transcribe":
                if not self.settings.whisper_enabled or self.settings.whisper_model_path is None:
                    raise ValueError("Local Whisper is not configured.")
                workspace = WorkspaceTools(self.settings.workspace_root)
                transcript = asyncio.run(
                    asyncio.to_thread(
                        WhisperCliClient(
                            workspace=workspace,
                            executable=self.settings.whisper_executable,
                            model_path=self.settings.whisper_model_path,
                            timeout=self.settings.media_timeout,
                        ).transcribe,
                        self._required_text(payload, "path"),
                    )
                )
                return self._ok(asdict(transcript))

            if method == "POST" and path == "/v1/chat":
                message = self._required_text(
                    payload,
                    "message",
                )
                agent = build_default_agent(self.settings)
                chat_result = asyncio.run(
                    AgentRuntime().run(
                        agent,
                        message,
                    )
                )
                return self._ok(
                    {
                        "output": chat_result.output,
                        "steps": chat_result.steps,
                    }
                )

            if method == "POST" and path == "/v1/plans":
                bridge_result = asyncio.run(
                    handle_request(
                        {
                            "action": "plan_create",
                            "goal": self._required_text(
                                payload,
                                "goal",
                            ),
                        },
                        settings=self.settings,
                    )
                )
                return self._ok(bridge_result)

            plan_route = self._parse_plan_route(path)

            if plan_route is not None:
                plan_id, operation = plan_route
                if method == "POST" and operation in {
                    "pause",
                    "resume",
                    "cancel",
                }:
                    return self._control_plan(plan_id, operation)
                action = {
                    ("GET", "show"): "plan_show",
                    ("POST", "run"): "plan_run",
                    ("POST", "reflect"): "plan_reflect",
                }.get((method, operation))

                if action is not None:
                    plan_result = asyncio.run(
                        handle_request(
                            {
                                "action": action,
                                "plan_id": plan_id,
                            },
                            settings=self.settings,
                        )
                    )
                    return self._ok(plan_result)

            return ApiResponse(
                status=HTTPStatus.NOT_FOUND,
                payload={
                    "ok": False,
                    "error": {
                        "type": "NotFound",
                        "message": f"Unknown endpoint: {method} {path}",
                    },
                },
            )
        except ConfirmationRequired as exc:
            return ApiResponse(
                status=HTTPStatus.CONFLICT,
                payload={
                    "ok": False,
                    "error": {
                        "type": "ConfirmationRequired",
                        "message": str(exc),
                        "confirmation": asdict(exc.request),
                    },
                },
            )
        except (TypeError, ValueError, KeyError) as exc:
            return ApiResponse(
                status=HTTPStatus.BAD_REQUEST,
                payload={
                    "ok": False,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001 - API boundary returns structured errors
            return ApiResponse(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                payload={
                    "ok": False,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                },
            )

    def _diagnostics(self) -> DiagnosticReport:
        if self._diagnostic_provider is not None:
            return self._diagnostic_provider(self.settings)

        return asyncio.run(collect_diagnostics(self.settings))

    def _static_response(
        self,
        method: str,
        path: str,
    ) -> ApiResponse | None:
        if method != "GET":
            return None
        relative = {
            "/": "index.html",
            "/index.html": "index.html",
            "/assets/app.js": "app.js",
            "/assets/styles.css": "styles.css",
        }.get(path)
        if relative is None:
            return None
        target = (self.ui_root / relative).resolve()
        if self.ui_root.resolve() not in target.parents:
            return None
        try:
            raw = target.read_bytes()
        except OSError:
            return ApiResponse(
                status=HTTPStatus.NOT_FOUND,
                payload={"ok": False, "error": {"type": "NotFound", "message": path}},
            )
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"
        return ApiResponse(
            status=HTTPStatus.OK,
            payload=raw,
            content_type=content_type,
        )

    def _memory(self) -> LongTermMemory:
        return LongTermMemory(
            store=SQLiteMemoryStore(self.settings.memory_db_path),
            embedding_model=OpenAICompatibleEmbeddingModel(
                model=self.settings.embedding_model,
                base_url=self.settings.openai_base_url,
                api_key=self.settings.ollama_api_key,
                timeout=self.settings.model_timeout,
            ),
        )

    @staticmethod
    def _serialize_memory(memory: Any) -> dict[str, Any]:
        return {
            "id": memory.id,
            "content": memory.content,
            "source_session_id": memory.source_session_id,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "memory_type": memory.memory_type,
            "importance": memory.importance,
            "sensitivity": memory.sensitivity,
            "expires_at": memory.expires_at,
            "archived": memory.archived,
            "last_accessed_at": memory.last_accessed_at,
        }

    def _mcp_status(self) -> dict[str, Any]:
        if not self.settings.mcp_enabled:
            return {"enabled": False, "servers": []}
        registry = McpServerRegistry.load(
            self.settings.mcp_servers_path,
            project_root=self.settings.workspace_root,
        )
        servers = []
        for name in registry.names():
            with StdioMcpClient(
                registry.get(name),
                timeout=self.settings.mcp_timeout,
            ) as client:
                tools = client.list_tools()
            servers.append(
                {
                    "name": name,
                    "tools": [asdict(tool) for tool in tools],
                }
            )
        return {"enabled": True, "servers": servers}

    def _control_plan(
        self,
        plan_id: str,
        operation: str,
    ) -> ApiResponse:
        store = SQLitePlanStore(self.settings.planner_db_path)
        plan = store.get(plan_id)
        if operation == "pause":
            self.governance.set_plan_control(plan_id, PlanControlState.PAUSE)
            if plan.status == PlanStatus.READY:
                plan = plan.with_status(PlanStatus.PAUSED)
                store.save(plan)
        elif operation == "resume":
            if plan.status != PlanStatus.PAUSED:
                raise ValueError("Only a paused plan can be resumed.")
            self.governance.set_plan_control(plan_id, PlanControlState.RUN)
            plan = plan.with_status(PlanStatus.READY)
            store.save(plan)
        elif operation == "cancel":
            self.governance.set_plan_control(plan_id, PlanControlState.CANCEL)
            if plan.status != PlanStatus.RUNNING:
                plan = plan.with_status(PlanStatus.CANCELLED)
                store.save(plan)
        else:
            raise ValueError(f"Unknown plan control operation: {operation}")
        return self._ok({"plan": asdict(plan), "control": operation})

    @staticmethod
    def _ok(
        data: Mapping[str, Any],
    ) -> ApiResponse:
        return ApiResponse(
            status=HTTPStatus.OK,
            payload={
                "ok": True,
                "data": data,
            },
        )

    @staticmethod
    def _required_text(
        payload: Mapping[str, Any],
        key: str,
    ) -> str:
        value = payload.get(key)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Field '{key}' must be non-empty text.")

        return value.strip()

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("Optional text value must be a string.")
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _bounded_int(
        value: Any,
        *,
        minimum: int,
        maximum: int,
    ) -> int:
        if not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"Integer value must be between {minimum} and {maximum}.")

        return value

    @staticmethod
    def _parse_plan_route(
        path: str,
    ) -> tuple[str, str] | None:
        parts = path.strip("/").split("/")

        if len(parts) == 3 and parts[:2] == [
            "v1",
            "plans",
        ]:
            return parts[2], "show"

        if (
            len(parts) == 4
            and parts[:2]
            == [
                "v1",
                "plans",
            ]
            and parts[3]
            in {
                "run",
                "reflect",
                "pause",
                "resume",
                "cancel",
            }
        ):
            return parts[2], parts[3]

        return None

    @staticmethod
    def _parse_resource_route(
        path: str,
        resource: str,
    ) -> str | None:
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["v1", resource]:
            return parts[2]
        return None

    @staticmethod
    def _parse_confirmation_route(path: str) -> tuple[str, str] | None:
        parts = path.strip("/").split("/")
        if (
            len(parts) == 4
            and parts[:2] == ["v1", "confirmations"]
            and parts[3] in {"approve", "reject"}
        ):
            return parts[2], parts[3]
        return None


class LocalApiServer:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        application: ApiApplication | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.application = application or ApiApplication(self.settings)
        self._validate_bind()
        handler = self._build_handler()
        self.server = ThreadingHTTPServer(
            (
                self.settings.api_host,
                self.settings.api_port,
            ),
            handler,
        )

    @property
    def address(self) -> tuple[str, int]:
        host, port = self.server.server_address[:2]
        return str(host), int(port)

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def _validate_bind(self) -> None:
        host = self.settings.api_host

        try:
            is_loopback = ip_address(host).is_loopback
        except ValueError:
            is_loopback = host.casefold() == "localhost"

        if not is_loopback and not self.settings.api_allow_remote:
            raise ValueError(
                "Remote API binding is disabled. Use 127.0.0.1 or explicitly enable api_allow_remote."
            )

    def _build_handler(
        self,
    ) -> type[BaseHTTPRequestHandler]:
        application = self.application
        max_body_bytes = self.settings.api_max_body_bytes

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._dispatch("GET")

            def do_POST(self) -> None:
                self._dispatch("POST")

            def do_DELETE(self) -> None:
                self._dispatch("DELETE")

            def _dispatch(
                self,
                method: str,
            ) -> None:
                try:
                    body = self._read_json_body(max_body_bytes)
                    response = application.dispatch(
                        method,
                        self.path,
                        body,
                    )
                except Exception as exc:  # noqa: BLE001
                    response = ApiResponse(
                        status=HTTPStatus.BAD_REQUEST,
                        payload={
                            "ok": False,
                            "error": {
                                "type": type(exc).__name__,
                                "message": str(exc),
                            },
                        },
                    )

                if isinstance(response.payload, bytes):
                    raw = response.payload
                elif isinstance(response.payload, str):
                    raw = response.payload.encode("utf-8")
                else:
                    raw = json.dumps(
                        response.payload,
                        ensure_ascii=False,
                        default=str,
                    ).encode("utf-8")
                self.send_response(int(response.status))
                self.send_header(
                    "Content-Type",
                    response.content_type,
                )
                self.send_header(
                    "Content-Length",
                    str(len(raw)),
                )
                self.send_header(
                    "Cache-Control",
                    "no-store",
                )
                self.end_headers()

                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    return

                # Auditing is best-effort at the HTTP boundary. It happens
                # after the response so a busy local database can never make
                # the UI wait for bytes that are already ready.
                try:
                    application.governance.audit(
                        category="api",
                        action=f"{method} {urlsplit(self.path).path}",
                        outcome=str(int(response.status)),
                        actor="local-ui",
                    )
                except Exception:
                    logger.exception("Could not write API audit event")

            def log_message(
                self,
                format: str,
                *args: object,
            ) -> None:
                del format, args

            def _read_json_body(
                self,
                limit: int,
            ) -> Mapping[str, Any]:
                raw_length = self.headers.get(
                    "Content-Length",
                    "0",
                )

                try:
                    length = int(raw_length)
                except ValueError as exc:
                    raise ValueError("Invalid Content-Length.") from exc

                if length > limit:
                    raise ValueError("Request body exceeds the configured limit.")

                if length == 0:
                    return {}

                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))

                if not isinstance(payload, dict):
                    raise TypeError("JSON request body must be an object.")

                return payload

        return Handler
