from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum

from openclaw_ultimate.config import Settings
from openclaw_ultimate.integrations import (
    ComfyUIClient,
    McpServerRegistry,
    OpenClawCliClient,
    OpenClawComfyProfile,
    StdioMcpClient,
)
from openclaw_ultimate.model_cli import build_model_router
from openclaw_ultimate.models import (
    OllamaModelCatalog,
)
from openclaw_ultimate.rag import SQLiteKnowledgeStore


class ComponentState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ComponentDiagnostic:
    name: str
    state: ComponentState
    detail: str
    required: bool


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    state: ComponentState
    components: tuple[ComponentDiagnostic, ...]

    @property
    def ready(self) -> bool:
        return all(
            component.state == ComponentState.READY
            for component in self.components
            if component.required
        )


async def collect_diagnostics(
    settings: Settings,
) -> DiagnosticReport:
    """采集本地组件状态，不加载聊天模型或执行用户工具。"""

    components: list[ComponentDiagnostic] = []
    python_ready = sys.version_info.major == 3 and sys.version_info.minor == 12
    components.append(
        ComponentDiagnostic(
            name="python",
            state=(ComponentState.READY if python_ready else ComponentState.UNAVAILABLE),
            detail=(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
            required=True,
        )
    )
    workspace = settings.workspace_root.resolve()
    components.append(
        ComponentDiagnostic(
            name="workspace",
            state=(ComponentState.READY if workspace.is_dir() else ComponentState.UNAVAILABLE),
            detail=str(workspace),
            required=True,
        )
    )

    try:
        catalog = OllamaModelCatalog(
            base_url=settings.ollama_base_url,
            timeout=min(settings.model_timeout, 10.0),
        )
        models = await catalog.discover()
        routes = build_model_router(
            settings,
            models,
        ).select_all()
        components.append(
            ComponentDiagnostic(
                name="ollama",
                state=ComponentState.READY,
                detail=(f"{len(models)} installed models; {len(routes)} task routes"),
                required=True,
            )
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics must collect all components
        components.append(
            ComponentDiagnostic(
                name="ollama",
                state=ComponentState.UNAVAILABLE,
                detail=f"{type(exc).__name__}: {exc}",
                required=True,
            )
        )

    if settings.openclaw_enabled:
        try:
            client = OpenClawCliClient(
                cli_command=settings.openclaw_cli_command,
                gateway_url=settings.openclaw_gateway_url,
                agent_id=settings.openclaw_agent_id,
                model=settings.openclaw_model,
                timeout=settings.openclaw_timeout,
            )
            health = client.health()
            status = client.status()
            ready = health.live and health.ready and status.rpc_ok and status.config_valid
            components.append(
                ComponentDiagnostic(
                    name="openclaw",
                    state=(ComponentState.READY if ready else ComponentState.DEGRADED),
                    detail=(
                        f"{status.runtime_status or 'unknown'} / "
                        f"{status.service_state or 'unknown'} / "
                        f"{status.cli_version or 'unknown'}"
                    ),
                    required=True,
                )
            )
        except Exception as exc:  # noqa: BLE001
            components.append(
                ComponentDiagnostic(
                    name="openclaw",
                    state=ComponentState.UNAVAILABLE,
                    detail=f"{type(exc).__name__}: {exc}",
                    required=True,
                )
            )
    else:
        components.append(
            ComponentDiagnostic(
                name="openclaw",
                state=ComponentState.DISABLED,
                detail="disabled by configuration",
                required=False,
            )
        )

    if settings.comfyui_enabled:
        profile = (
            OpenClawComfyProfile.discover(settings.openclaw_config_path)
            if settings.comfyui_inherit_openclaw_config
            else None
        )

        if profile is None:
            components.append(
                ComponentDiagnostic(
                    name="comfyui",
                    state=ComponentState.DEGRADED,
                    detail="no reusable OpenClaw ComfyUI profile",
                    required=False,
                )
            )
        else:
            try:
                comfy_health = ComfyUIClient(profile=profile).health()
                components.append(
                    ComponentDiagnostic(
                        name="comfyui",
                        state=ComponentState.READY,
                        detail=(f"{comfy_health.device_count} device(s); {profile.base_url}"),
                        required=False,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                components.append(
                    ComponentDiagnostic(
                        name="comfyui",
                        state=ComponentState.UNAVAILABLE,
                        detail=f"{type(exc).__name__}: {exc}",
                        required=False,
                    )
                )

    if settings.knowledge_enabled:
        stats = SQLiteKnowledgeStore(settings.knowledge_db_path).stats()
        components.append(
            ComponentDiagnostic(
                name="knowledge",
                state=(ComponentState.READY if stats.document_count else ComponentState.DEGRADED),
                detail=(f"{stats.document_count} documents / {stats.chunk_count} chunks"),
                required=False,
            )
        )

    if settings.mcp_enabled and settings.mcp_servers_path.is_file():
        try:
            registry = McpServerRegistry.load(
                settings.mcp_servers_path,
                project_root=settings.workspace_root,
            )
            tool_count = 0
            for server_name in registry.names():
                with StdioMcpClient(
                    registry.get(server_name),
                    timeout=min(settings.mcp_timeout, 10.0),
                ) as mcp_client:
                    tool_count += len(mcp_client.list_tools())
            components.append(
                ComponentDiagnostic(
                    name="mcp",
                    state=ComponentState.READY,
                    detail=f"{len(registry)} server(s); {tool_count} tool(s)",
                    required=False,
                )
            )
        except Exception as exc:  # noqa: BLE001
            components.append(
                ComponentDiagnostic(
                    name="mcp",
                    state=ComponentState.DEGRADED,
                    detail=f"{type(exc).__name__}: {exc}",
                    required=False,
                )
            )
    else:
        components.append(
            ComponentDiagnostic(
                name="mcp",
                state=ComponentState.DISABLED,
                detail="disabled or no allowlist configuration",
                required=False,
            )
        )
    required_states = {component.state for component in components if component.required}

    if ComponentState.UNAVAILABLE in required_states:
        state = ComponentState.UNAVAILABLE
    elif ComponentState.DEGRADED in required_states:
        state = ComponentState.DEGRADED
    else:
        state = ComponentState.READY

    return DiagnosticReport(
        state=state,
        components=tuple(components),
    )
