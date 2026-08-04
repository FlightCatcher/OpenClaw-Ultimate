from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OpenClaw-Ultimate 全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OCU_",
        extra="ignore",
    )

    app_name: str = "VELA"
    log_level: str = "INFO"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ollama_api_key: str | None = None

    model_timeout: float = 300.0
    temperature: float = 0.2
    max_steps: int = 8

    system_prompt: str = (
        "你是 VELA（维澜），一个由 OpenClaw-Ultimate 提供兼容层的本地 AI 助手。"
        "请使用准确、清晰的中文回答。"
        "当存在合适工具时，应优先使用工具获得可靠结果。"
    )

    enable_shell_tool: bool = False
    workspace_root: Path = Field(default_factory=Path.cwd)
    workspace_max_read_bytes: int = 1_000_000
    workspace_max_results: int = 200
    shell_allowed_commands: tuple[str, ...] = (
        "git",
        "uv",
        "python",
        "pytest",
    )
    shell_timeout: float = 30.0
    shell_max_output_characters: int = 20_000

    session_db_path: Path = Path(".openclaw/sessions.db")
    history_message_limit: int = 100

    context_token_budget: int = 8192
    context_response_reserve: int = 2048

    memory_enabled: bool = True
    memory_db_path: Path = Path(".openclaw/memory.db")
    embedding_model: str = "qwen3-embedding:0.6b"
    memory_recall_limit: int = 5
    memory_similarity_threshold: float = 0.35
    memory_max_context_characters: int = 2000

    planner_db_path: Path = Path(".openclaw/plans.db")
    planner_max_steps: int = 12

    openclaw_enabled: bool = True
    openclaw_cli_command: str = "openclaw"
    openclaw_gateway_url: str = "http://127.0.0.1:18789"
    openclaw_agent_id: str = "main"
    openclaw_model: str | None = "ollama/qwen3:8b"
    openclaw_timeout: float = 600.0

    gpu_vram_gb: float = 8.0
    model_resident_budget_gb: float = 6.5
    model_route_chat: tuple[str, ...] = ("qwen3:8b",)
    model_route_coding: tuple[str, ...] = (
        "qwen2.5-coder:7b",
        "qwen3:8b",
    )
    model_route_planning: tuple[str, ...] = (
        "qwen3:8b",
        "qwen2.5-coder:7b",
    )
    model_route_tool_calling: tuple[str, ...] = ("qwen3:8b",)
    model_route_vision: tuple[str, ...] = (
        "qwen3-vl:8b",
        "qwen2.5vl:3b",
        "moondream:latest",
    )
    model_route_embedding: tuple[str, ...] = (
        "qwen3-embedding:0.6b",
        "nomic-embed-text:latest",
    )

    comfyui_enabled: bool = True
    comfyui_inherit_openclaw_config: bool = True
    comfyui_base_url: str | None = None
    comfyui_workflow_path: Path | None = None
    comfyui_prompt_node_id: str | None = None
    comfyui_prompt_input_name: str | None = None
    comfyui_output_node_id: str | None = None
    comfyui_poll_interval: float = 1.0
    comfyui_timeout: float = 600.0
    openclaw_config_path: Path = Field(
        default_factory=lambda: Path.home() / ".openclaw" / "openclaw.json"
    )

    mcp_enabled: bool = True
    mcp_servers_path: Path = Path("configs/mcp_servers.local.json")
    mcp_timeout: float = 30.0

    knowledge_enabled: bool = True
    knowledge_root: Path = Path("E:/OpenClaw-Knowledge/library")
    knowledge_db_path: Path = Path(".openclaw/knowledge.db")
    knowledge_chunk_characters: int = 1200
    knowledge_chunk_overlap: int = 200
    knowledge_max_file_bytes: int = 1_000_000
    knowledge_embedding_batch_size: int = 16
    knowledge_search_limit: int = 5
    knowledge_minimum_score: float = 0.2
    knowledge_max_context_characters: int = 5000

    vision_enabled: bool = True
    vision_model: str = "qwen3-vl:8b"
    vision_max_image_bytes: int = 20_000_000
    whisper_enabled: bool = False
    whisper_executable: str = "whisper-cli"
    whisper_model_path: Path | None = None
    media_timeout: float = 600.0

    # Life hub. Home Assistant is the local normalization layer for Xiaomi Home,
    # Matter, and other supported smart-home ecosystems. All state-changing calls
    # remain disabled until explicitly enabled and individually confirmed.
    home_assistant_enabled: bool = False
    home_assistant_base_url: str = "http://homeassistant.local:8123"
    home_assistant_token: SecretStr | None = None
    home_assistant_timeout: float = 10.0
    home_assistant_read_only: bool = True
    home_assistant_allowed_domains: tuple[str, ...] = (
        "light",
        "switch",
        "fan",
        "climate",
        "cover",
        "vacuum",
        "media_player",
        "scene",
        "script",
    )

    # Personal WeChat does not expose a general-purpose bot API. VELA supports
    # only the official outbound WeCom group-robot webhook.
    wecom_enabled: bool = False
    wecom_webhook_url: SecretStr | None = None
    qq_bot_enabled: bool = False
    qq_bot_app_id: str | None = None
    qq_bot_client_secret: SecretStr | None = None
    life_connector_timeout: float = 10.0

    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_allow_remote: bool = False
    api_max_body_bytes: int = 1_000_000
    governance_db_path: Path = Path(".openclaw/governance.db")

    @property
    def openai_base_url(self) -> str:
        """返回 OpenAI-Compatible API 基础地址。"""

        base_url = self.ollama_base_url.rstrip("/")

        if base_url.endswith("/v1"):
            return base_url

        return f"{base_url}/v1"

    @field_validator(
        "model_timeout",
        "openclaw_timeout",
        "comfyui_poll_interval",
        "comfyui_timeout",
        "mcp_timeout",
        "home_assistant_timeout",
        "life_connector_timeout",
    )
    @classmethod
    def validate_model_timeout(
        cls,
        value: float,
    ) -> float:
        if value <= 0:
            raise ValueError("model_timeout must be greater than zero.")

        return value

    @field_validator(
        "openclaw_cli_command",
        "openclaw_gateway_url",
        "openclaw_agent_id",
    )
    @classmethod
    def validate_non_empty_openclaw_settings(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("OpenClaw settings cannot be empty.")

        return cleaned

    @field_validator("openclaw_model")
    @classmethod
    def validate_openclaw_model(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None

    @field_validator(
        "comfyui_base_url",
        "comfyui_prompt_node_id",
        "comfyui_prompt_input_name",
        "comfyui_output_node_id",
    )
    @classmethod
    def validate_optional_comfyui_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None

    @field_validator(
        "gpu_vram_gb",
        "model_resident_budget_gb",
    )
    @classmethod
    def validate_positive_model_memory(
        cls,
        value: float,
    ) -> float:
        if value <= 0:
            raise ValueError("Model memory values must be greater than zero.")

        return value

    @field_validator("max_steps")
    @classmethod
    def validate_max_steps(
        cls,
        value: int,
    ) -> int:
        if value < 1:
            raise ValueError("max_steps must be at least 1.")

        return value

    @field_validator("temperature")
    @classmethod
    def validate_temperature(
        cls,
        value: float,
    ) -> float:
        if not 0 <= value <= 2:
            raise ValueError("temperature must be between 0 and 2.")

        return value

    @field_validator("history_message_limit")
    @classmethod
    def validate_history_message_limit(
        cls,
        value: int,
    ) -> int:
        if value < 1:
            raise ValueError("history_message_limit must be at least 1.")

        return value

    @field_validator("context_token_budget")
    @classmethod
    def validate_context_token_budget(
        cls,
        value: int,
    ) -> int:
        if value < 256:
            raise ValueError("context_token_budget must be at least 256.")

        return value

    @field_validator(
        "memory_recall_limit",
        "memory_max_context_characters",
        "workspace_max_read_bytes",
        "workspace_max_results",
        "shell_max_output_characters",
        "planner_max_steps",
        "knowledge_chunk_characters",
        "knowledge_max_file_bytes",
        "knowledge_embedding_batch_size",
        "knowledge_search_limit",
        "knowledge_max_context_characters",
        "api_max_body_bytes",
    )
    @classmethod
    def validate_positive_memory_limits(
        cls,
        value: int,
    ) -> int:
        if value < 1:
            raise ValueError("Memory limits must be at least 1.")

        return value

    @field_validator("api_port")
    @classmethod
    def validate_api_port(
        cls,
        value: int,
    ) -> int:
        if not 0 <= value <= 65535:
            raise ValueError("api_port must be between 0 and 65535.")

        return value

    @field_validator("api_host")
    @classmethod
    def validate_api_host(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("api_host cannot be empty.")

        return cleaned

    @field_validator("shell_timeout")
    @classmethod
    def validate_shell_timeout(
        cls,
        value: float,
    ) -> float:
        if value <= 0:
            raise ValueError("shell_timeout must be greater than zero.")

        return value

    @field_validator("shell_allowed_commands")
    @classmethod
    def validate_shell_allowed_commands(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        cleaned = tuple(command.strip() for command in value if command.strip())

        if len(cleaned) != len(value):
            raise ValueError("shell_allowed_commands cannot contain empty names.")

        return cleaned

    @field_validator("memory_similarity_threshold")
    @classmethod
    def validate_memory_similarity_threshold(
        cls,
        value: float,
    ) -> float:
        if not -1 <= value <= 1:
            raise ValueError("memory_similarity_threshold must be between -1 and 1.")

        return value

    @field_validator("knowledge_minimum_score")
    @classmethod
    def validate_knowledge_minimum_score(
        cls,
        value: float,
    ) -> float:
        if not 0 <= value <= 1:
            raise ValueError("knowledge_minimum_score must be between 0 and 1.")

        return value

    @field_validator("knowledge_chunk_overlap")
    @classmethod
    def validate_knowledge_chunk_overlap(
        cls,
        value: int,
    ) -> int:
        if value < 0:
            raise ValueError("knowledge_chunk_overlap cannot be negative.")

        return value

    @field_validator("context_response_reserve")
    @classmethod
    def validate_context_response_reserve(
        cls,
        value: int,
    ) -> int:
        if value < 0:
            raise ValueError("context_response_reserve cannot be negative.")

        return value

    @model_validator(mode="after")
    def validate_context_window(
        self,
    ) -> Settings:
        if self.context_response_reserve >= self.context_token_budget:
            raise ValueError("context_response_reserve must be smaller than context_token_budget.")

        if self.model_resident_budget_gb > self.gpu_vram_gb:
            raise ValueError("model_resident_budget_gb cannot exceed gpu_vram_gb.")

        if self.knowledge_chunk_overlap >= self.knowledge_chunk_characters:
            raise ValueError(
                "knowledge_chunk_overlap must be smaller than knowledge_chunk_characters."
            )

        return self


def load_settings() -> Settings:
    return Settings()
