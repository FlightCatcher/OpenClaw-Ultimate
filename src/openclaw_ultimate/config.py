from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OpenClaw-Ultimate 全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OCU_",
        extra="ignore",
    )

    app_name: str = "OpenClaw Ultimate"
    log_level: str = "INFO"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ollama_api_key: str | None = None

    model_timeout: float = 300.0
    temperature: float = 0.2
    max_steps: int = 8

    system_prompt: str = (
        "你是 OpenClaw-Ultimate 的本地 AI 助手。"
        "请使用准确、清晰的中文回答。"
        "当存在合适工具时，应优先使用工具获得可靠结果。"
    )

    enable_shell_tool: bool = False
    workspace_root: Path = Field(default_factory=Path.cwd)

    @property
    def openai_base_url(self) -> str:
        """返回 OpenAI-Compatible API 基础地址。"""

        base_url = self.ollama_base_url.rstrip("/")

        if base_url.endswith("/v1"):
            return base_url

        return f"{base_url}/v1"

    @field_validator("model_timeout")
    @classmethod
    def validate_model_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("model_timeout must be greater than zero.")

        return value

    @field_validator("max_steps")
    @classmethod
    def validate_max_steps(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_steps must be at least 1.")

        return value

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if not 0 <= value <= 2:
            raise ValueError("temperature must be between 0 and 2.")

        return value


def load_settings() -> Settings:
    return Settings()
