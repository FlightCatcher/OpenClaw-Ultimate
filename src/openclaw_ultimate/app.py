from __future__ import annotations

import asyncio
import json
from hashlib import sha256

from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.core.runtime import Agent
from openclaw_ultimate.governance import RiskLevel, SQLiteGovernanceStore
from openclaw_ultimate.integrations import (
    ComfyUIClient,
    HomeAssistantClient,
    McpServerRegistry,
    OllamaVisionClient,
    OpenClawCliClient,
    OpenClawComfyProfile,
    QQBotClient,
    StdioMcpClient,
    WeComWebhookClient,
    WhisperCliClient,
)
from openclaw_ultimate.models import OpenAICompatibleModel
from openclaw_ultimate.rag import build_knowledge_base
from openclaw_ultimate.tools import (
    SafeCommandRunner,
    WorkspaceTools,
)


def add(a: float, b: float) -> float:
    """计算两个数字之和。"""

    return a + b


def build_default_agent(
    settings: Settings | None = None,
) -> Agent:
    """根据配置创建默认本地 Agent。"""

    current_settings = settings or load_settings()

    model = OpenAICompatibleModel(
        model=current_settings.ollama_model,
        base_url=current_settings.openai_base_url,
        api_key=current_settings.ollama_api_key,
        timeout=current_settings.model_timeout,
        temperature=current_settings.temperature,
    )

    agent = Agent(
        name="vela",
        model=model,
        system_prompt=current_settings.system_prompt,
        max_steps=current_settings.max_steps,
    )

    agent.tools.add(
        name="add",
        description="准确计算两个数字之和。",
        parameters={
            "type": "object",
            "properties": {
                "a": {
                    "type": "number",
                    "description": "第一个数字",
                },
                "b": {
                    "type": "number",
                    "description": "第二个数字",
                },
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        handler=add,
    )

    _register_workspace_tools(
        agent,
        current_settings,
    )
    _register_openclaw_tool(
        agent,
        current_settings,
    )
    _register_comfyui_tools(
        agent,
        current_settings,
    )
    _register_mcp_tools(
        agent,
        current_settings,
    )
    _register_knowledge_tool(
        agent,
        current_settings,
    )
    _register_media_tools(
        agent,
        current_settings,
    )
    _register_life_tools(
        agent,
        current_settings,
    )

    return agent


def _register_life_tools(agent: Agent, settings: Settings) -> None:
    governance = SQLiteGovernanceStore(settings.governance_db_path)

    if settings.home_assistant_enabled and settings.home_assistant_token is not None:
        home = HomeAssistantClient(
            base_url=settings.home_assistant_base_url,
            token=settings.home_assistant_token.get_secret_value(),
            timeout=settings.home_assistant_timeout,
        )
        allowed_domains = frozenset(
            domain.strip().casefold()
            for domain in settings.home_assistant_allowed_domains
            if domain.strip()
        )

        async def home_status() -> dict[str, object]:
            health = await asyncio.to_thread(home.health)
            return {"online": True, "message": str(health.get("message", "API running"))}

        async def home_list_entities(domain: str | None = None) -> dict[str, object]:
            entities = await asyncio.to_thread(home.list_states, domain)
            return {
                "count": len(entities),
                "entities": [
                    {
                        "entity_id": entity.entity_id,
                        "state": entity.state,
                        "friendly_name": entity.attributes.get("friendly_name"),
                        "last_changed": entity.last_changed,
                    }
                    for entity in entities
                ],
            }

        async def home_get_state(entity_id: str) -> dict[str, object]:
            entity = await asyncio.to_thread(home.get_state, entity_id)
            return {
                "entity_id": entity.entity_id,
                "state": entity.state,
                "attributes": entity.attributes,
                "last_changed": entity.last_changed,
            }

        async def home_call_service(
            domain: str,
            service: str,
            entity_id: str | None = None,
            data: dict[str, object] | None = None,
        ) -> dict[str, object]:
            clean_domain = domain.strip().casefold()
            if settings.home_assistant_read_only:
                raise PermissionError("Home Assistant control is configured as read-only.")
            if clean_domain not in allowed_domains:
                raise PermissionError(f"Home Assistant domain is not allowed: {clean_domain}")
            request = {
                "domain": clean_domain,
                "service": service.strip().casefold(),
                "entity_id": entity_id,
                "data": data or {},
            }
            fingerprint = sha256(
                json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:24]
            governance.require_confirmation(
                action=f"home.{clean_domain}.{request['service']}",
                description=(
                    f"Control Home Assistant entity {entity_id or '(service target)'} "
                    f"with {clean_domain}.{request['service']}"
                ),
                risk=RiskLevel.REVERSIBLE,
                resource_id=fingerprint,
            )
            changed = await asyncio.to_thread(
                home.call_service,
                domain=clean_domain,
                service=str(request["service"]),
                entity_id=entity_id,
                data=dict(data or {}),
            )
            return {
                "ok": True,
                "changed_entities": [item.entity_id for item in changed],
            }

        agent.tools.add(
            name="home_status",
            description="检查本地 Home Assistant 生活中枢是否在线。",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            handler=home_status,
        )
        agent.tools.add(
            name="home_list_entities",
            description="只读列出 Home Assistant 中的米家、Matter 或其他智能家居实体。",
            parameters={
                "type": "object",
                "properties": {"domain": {"type": "string"}},
                "additionalProperties": False,
            },
            handler=home_list_entities,
        )
        agent.tools.add(
            name="home_get_state",
            description="只读查询一个智能家居实体的当前状态和属性。",
            parameters={
                "type": "object",
                "properties": {"entity_id": {"type": "string"}},
                "required": ["entity_id"],
                "additionalProperties": False,
            },
            handler=home_get_state,
        )
        agent.tools.add(
            name="home_call_service",
            description=(
                "控制白名单内的智能家居设备。每一个具体操作都必须经过一次性用户确认。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "enum": sorted(allowed_domains)},
                    "service": {"type": "string"},
                    "entity_id": {"type": "string"},
                    "data": {"type": "object", "default": {}},
                },
                "required": ["domain", "service"],
                "additionalProperties": False,
            },
            handler=home_call_service,
        )

    if settings.wecom_enabled and settings.wecom_webhook_url is not None:
        wecom = WeComWebhookClient(
            webhook_url=settings.wecom_webhook_url.get_secret_value(),
            timeout=settings.life_connector_timeout,
        )

        async def send_wecom_message(content: str) -> dict[str, object]:
            clean_content = content.strip()
            fingerprint = sha256(clean_content.encode("utf-8")).hexdigest()[:24]
            governance.require_confirmation(
                action="message.wecom.send",
                description=f"Send a {len(clean_content)} character message to a WeCom group",
                risk=RiskLevel.HIGH,
                resource_id=fingerprint,
            )
            return await asyncio.to_thread(wecom.send_text, clean_content)

        agent.tools.add(
            name="send_wecom_message",
            description=(
                "通过官方企业微信群机器人发送文本通知。发送前必须获得一次性用户确认。"
            ),
            parameters={
                "type": "object",
                "properties": {"content": {"type": "string", "maxLength": 4000}},
                "required": ["content"],
                "additionalProperties": False,
            },
            handler=send_wecom_message,
        )

    if (
        settings.qq_bot_enabled
        and settings.qq_bot_app_id is not None
        and settings.qq_bot_client_secret is not None
    ):
        qq = QQBotClient(
            app_id=settings.qq_bot_app_id,
            client_secret=settings.qq_bot_client_secret.get_secret_value(),
            timeout=settings.life_connector_timeout,
        )

        async def send_qq_message(
            target_type: str,
            target_openid: str,
            content: str,
        ) -> dict[str, object]:
            request = {
                "target_type": target_type.strip().casefold(),
                "target_openid": target_openid.strip(),
                "content": content.strip(),
            }
            fingerprint = sha256(
                json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:24]
            governance.require_confirmation(
                action="message.qq.send",
                description=(
                    f"Send a {len(request['content'])} character QQ Bot message "
                    f"to {request['target_type']} {request['target_openid']}"
                ),
                risk=RiskLevel.HIGH,
                resource_id=fingerprint,
            )
            return await asyncio.to_thread(
                qq.send_text,
                target_type=request["target_type"],
                target_openid=request["target_openid"],
                content=request["content"],
            )

        agent.tools.add(
            name="send_qq_message",
            description=(
                "通过 QQ 开放平台官方机器人向已授权的用户或群发送文本。"
                "必须使用事件提供的 OpenID，且每次发送前都需用户确认。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target_type": {"type": "string", "enum": ["user", "group"]},
                    "target_openid": {"type": "string"},
                    "content": {"type": "string", "maxLength": 2000},
                },
                "required": ["target_type", "target_openid", "content"],
                "additionalProperties": False,
            },
            handler=send_qq_message,
        )


def _register_workspace_tools(
    agent: Agent,
    settings: Settings,
) -> None:
    workspace = WorkspaceTools(
        settings.workspace_root,
        max_read_bytes=(settings.workspace_max_read_bytes),
        max_results=settings.workspace_max_results,
    )

    agent.tools.add(
        name="list_files",
        description=("列出 Agent 工作区内指定目录的文件和子目录。"),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": ("相对于工作区的目录，默认是根目录"),
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": ("文件匹配模式，例如 *.py"),
                    "default": "*",
                },
            },
            "additionalProperties": False,
        },
        handler=workspace.list_files,
    )
    agent.tools.add(
        name="read_text_file",
        description=("读取 Agent 工作区内的 UTF-8 文本文件。"),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": ("相对于工作区的文件路径"),
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=workspace.read_text_file,
    )
    agent.tools.add(
        name="search_text",
        description=("递归搜索 Agent 工作区中的文本内容。"),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要查找的文本",
                },
                "path": {
                    "type": "string",
                    "description": ("相对于工作区的搜索起点"),
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": ("文件匹配模式，例如 *.py"),
                    "default": "*",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否区分大小写",
                    "default": False,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=workspace.search_text,
    )

    if not settings.enable_shell_tool:
        return

    runner = SafeCommandRunner(
        workspace,
        allowed_commands=(settings.shell_allowed_commands),
        timeout=settings.shell_timeout,
        max_output_characters=(settings.shell_max_output_characters),
        governance_store=SQLiteGovernanceStore(settings.governance_db_path),
    )
    agent.tools.add(
        name="run_command",
        description=("在 Agent 工作区内执行白名单命令。不支持管道、重定向或 Shell 表达式。"),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": ("可执行程序名称，必须在白名单中"),
                },
                "arguments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "命令参数列表",
                    "default": [],
                },
                "working_directory": {
                    "type": "string",
                    "description": ("相对于工作区的运行目录"),
                    "default": ".",
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handler=runner.run_command,
    )


def _register_openclaw_tool(
    agent: Agent,
    settings: Settings,
) -> None:
    if not settings.openclaw_enabled:
        return

    client = OpenClawCliClient(
        cli_command=settings.openclaw_cli_command,
        gateway_url=settings.openclaw_gateway_url,
        agent_id=settings.openclaw_agent_id,
        model=settings.openclaw_model,
        timeout=settings.openclaw_timeout,
    )

    async def ask_openclaw(
        message: str,
        session_key: str | None = None,
        model: str | None = None,
    ) -> dict[str, object]:
        result = await asyncio.to_thread(
            client.run_agent,
            message,
            session_key=session_key,
            model=model,
        )

        return {
            "ok": True,
            "run_id": result.run_id,
            "status": result.status,
            "text": result.text,
        }

    async def read_web_page(
        url: str,
    ) -> dict[str, object]:
        page = await asyncio.to_thread(
            client.read_web_page,
            url,
        )
        return {
            "ok": True,
            "title": page.title,
            "url": page.url,
            "snapshot": page.snapshot,
        }

    agent.tools.add(
        name="ask_openclaw",
        description=(
            "把任务委托给本机已运行的 OpenClaw Agent。"
            "OpenClaw 会使用其现有模型路由、插件和权限完成任务。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "需要 OpenClaw 完成的清晰任务",
                },
                "session_key": {
                    "type": "string",
                    "description": "可选的 OpenClaw 会话键",
                },
                "model": {
                    "type": "string",
                    "description": "可选的 provider/model 模型覆盖",
                },
            },
            "required": ["message"],
            "additionalProperties": False,
        },
        handler=ask_openclaw,
    )
    agent.tools.add(
        name="read_web_page",
        description=(
            "使用本机 OpenClaw Browser 打开公开网页并读取可见结构化内容。临时标签读取后自动关闭。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "完整的 HTTP 或 HTTPS 网页地址",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=read_web_page,
    )


def _register_comfyui_tools(
    agent: Agent,
    settings: Settings,
) -> None:
    if not settings.comfyui_enabled:
        return

    profile = _resolve_comfyui_profile(settings)

    if profile is None:
        return

    client = ComfyUIClient(profile=profile)

    async def comfyui_status() -> dict[str, object]:
        health = await asyncio.to_thread(client.health)
        return {
            "online": health.online,
            "operating_system": health.operating_system,
            "python_version": health.python_version,
            "device_count": health.device_count,
        }

    async def generate_image(prompt: str) -> dict[str, object]:
        result = await asyncio.to_thread(
            client.generate_image,
            prompt,
        )
        return {
            "prompt_id": result.prompt_id,
            "outputs": [
                {
                    "filename": output.filename,
                    "subfolder": output.subfolder,
                    "type": output.output_type,
                    "view_url": output.view_url,
                }
                for output in result.outputs
            ],
        }

    agent.tools.add(
        name="comfyui_status",
        description="检查本机 OpenClaw 共用的 ComfyUI 服务是否在线。",
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=comfyui_status,
    )
    agent.tools.add(
        name="generate_image",
        description=(
            "使用本机 OpenClaw 已配置的 ComfyUI 工作流生成图片。"
            "只接受正向提示词，不允许切换任意工作流。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "清晰、完整的图片生成提示词",
                },
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
        handler=generate_image,
    )


def _resolve_comfyui_profile(
    settings: Settings,
) -> OpenClawComfyProfile | None:
    explicit = (
        settings.comfyui_base_url,
        settings.comfyui_workflow_path,
        settings.comfyui_prompt_node_id,
        settings.comfyui_prompt_input_name,
        settings.comfyui_output_node_id,
    )

    if all(value is not None for value in explicit):
        assert settings.comfyui_workflow_path is not None
        assert settings.comfyui_base_url is not None
        assert settings.comfyui_prompt_node_id is not None
        assert settings.comfyui_prompt_input_name is not None
        assert settings.comfyui_output_node_id is not None
        return OpenClawComfyProfile(
            base_url=settings.comfyui_base_url.rstrip("/"),
            workflow_path=settings.comfyui_workflow_path,
            prompt_node_id=settings.comfyui_prompt_node_id,
            prompt_input_name=settings.comfyui_prompt_input_name,
            output_node_id=settings.comfyui_output_node_id,
            poll_interval_seconds=settings.comfyui_poll_interval,
            timeout_seconds=settings.comfyui_timeout,
        )

    if settings.comfyui_inherit_openclaw_config:
        return OpenClawComfyProfile.discover(
            settings.openclaw_config_path,
        )

    return None


def _register_mcp_tools(
    agent: Agent,
    settings: Settings,
) -> None:
    mcp_path = settings.mcp_servers_path.expanduser()
    if not mcp_path.is_absolute():
        mcp_path = settings.workspace_root.expanduser().resolve() / mcp_path

    if not settings.mcp_enabled or not mcp_path.is_file():
        return

    registry = McpServerRegistry.load(
        mcp_path,
        project_root=settings.workspace_root,
    )

    if not len(registry):
        return

    async def list_mcp_tools(server: str) -> dict[str, object]:
        config = registry.get(server)

        def run() -> tuple[dict[str, object], ...]:
            with StdioMcpClient(
                config,
                timeout=settings.mcp_timeout,
            ) as client:
                return tuple(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": dict(tool.input_schema),
                    }
                    for tool in client.list_tools()
                )

        tools = await asyncio.to_thread(run)
        return {
            "server": server,
            "tools": tools,
        }

    async def call_mcp_tool(
        server: str,
        tool: str,
        arguments: dict[str, object] | None = None,
    ) -> dict[str, object]:
        config = registry.get(server)

        def run() -> dict[str, object]:
            with StdioMcpClient(
                config,
                timeout=settings.mcp_timeout,
            ) as client:
                result = client.call_tool(
                    tool,
                    arguments or {},
                )
                return {
                    "server": server,
                    "tool": tool,
                    "is_error": result.is_error,
                    "content": result.content,
                    "structured_content": result.structured_content,
                }

        return await asyncio.to_thread(run)

    agent.tools.add(
        name="list_mcp_tools",
        description="列出本地白名单中指定 MCP 服务公开的工具。",
        parameters={
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "enum": list(registry.names()),
                }
            },
            "required": ["server"],
            "additionalProperties": False,
        },
        handler=list_mcp_tools,
    )
    agent.tools.add(
        name="call_mcp_tool",
        description=(
            "调用本地白名单 MCP 服务公开的工具。"
            "服务器命令来自配置文件，模型不能提供或修改可执行命令。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "enum": list(registry.names()),
                },
                "tool": {
                    "type": "string",
                },
                "arguments": {
                    "type": "object",
                    "default": {},
                },
            },
            "required": ["server", "tool"],
            "additionalProperties": False,
        },
        handler=call_mcp_tool,
    )


def _register_knowledge_tool(
    agent: Agent,
    settings: Settings,
) -> None:
    if not settings.knowledge_enabled:
        return

    knowledge = build_knowledge_base(settings)

    async def search_knowledge(
        query: str,
        limit: int | None = None,
    ) -> dict[str, object]:
        selected_limit = limit if limit is not None else settings.knowledge_search_limit
        hits = await knowledge.search(
            query,
            limit=selected_limit,
            minimum_score=(settings.knowledge_minimum_score),
        )
        return {
            "query": query,
            "results": [
                {
                    "score": round(hit.score, 4),
                    "citation": hit.chunk.citation,
                    "content": hit.chunk.content,
                }
                for hit in hits
            ],
            "context": knowledge.format_context(
                hits,
                max_characters=(settings.knowledge_max_context_characters),
            ),
        }

    agent.tools.add(
        name="search_knowledge",
        description=(
            "检索本机 OpenClaw 知识库，返回带文件路径和行号的来源。"
            "回答项目、OpenClaw、Ollama、ComfyUI 等技术问题前优先使用。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要查找的问题或关键词",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=search_knowledge,
    )


def _register_media_tools(
    agent: Agent,
    settings: Settings,
) -> None:
    if not settings.vision_enabled and not settings.whisper_enabled:
        return
    workspace = WorkspaceTools(
        settings.workspace_root,
        max_read_bytes=settings.workspace_max_read_bytes,
        max_results=settings.workspace_max_results,
    )
    if settings.vision_enabled:
        client = OllamaVisionClient(
            workspace=workspace,
            base_url=settings.ollama_base_url,
            model=settings.vision_model,
            timeout=settings.media_timeout,
            max_image_bytes=settings.vision_max_image_bytes,
        )

        async def analyze_image(
            path: str,
            prompt: str = "请描述这张图片，并准确识别其中可见的文字。",
        ) -> dict[str, str]:
            result = await asyncio.to_thread(
                client.analyze,
                path,
                prompt=prompt,
            )
            return {
                "model": result.model,
                "path": result.path,
                "text": result.text,
            }

        agent.tools.add(
            name="analyze_image",
            description="使用本机 Ollama 视觉模型分析工作区图片或执行 OCR。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "工作区内的图片路径",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "希望视觉模型回答的问题",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=analyze_image,
        )

    if settings.whisper_enabled and settings.whisper_model_path is not None:
        whisper = WhisperCliClient(
            workspace=workspace,
            executable=settings.whisper_executable,
            model_path=settings.whisper_model_path,
            timeout=settings.media_timeout,
        )

        async def transcribe_audio(path: str) -> dict[str, str]:
            result = await asyncio.to_thread(whisper.transcribe, path)
            return {
                "path": result.path,
                "text": result.text,
            }

        agent.tools.add(
            name="transcribe_audio",
            description="使用用户配置的本地 whisper.cpp 模型转录工作区音频。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "工作区内的音频路径",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=transcribe_audio,
        )
