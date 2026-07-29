from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit

from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.bridge import handle_request
from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.core.runtime import AgentRuntime
from openclaw_ultimate.diagnostics import (
    DiagnosticReport,
    collect_diagnostics,
)
from openclaw_ultimate.rag import (
    SQLiteKnowledgeStore,
    build_knowledge_base,
)


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status: int
    payload: Mapping[str, Any]


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

    def dispatch(
        self,
        method: str,
        target: str,
        body: Mapping[str, Any] | None = None,
    ) -> ApiResponse:
        path = urlsplit(target).path.rstrip("/") or "/"
        payload = dict(body or {})

        try:
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
            and parts[3] in {"run", "reflect"}
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

                raw = json.dumps(
                    response.payload,
                    ensure_ascii=False,
                    default=str,
                ).encode("utf-8")
                self.send_response(int(response.status))
                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8",
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
                except (BrokenPipeError, ConnectionAbortedError):
                    pass

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
